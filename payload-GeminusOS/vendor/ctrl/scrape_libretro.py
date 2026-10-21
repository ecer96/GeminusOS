#!/usr/bin/env python3
"""
scrape_libretro.py - Scraper de caratulas basado en libretro-thumbnails.

Fuente: https://thumbnails.libretro.com  (repositorio publico, sin API key)

Descarga caratulas, capturas, titulos y logos de los ROMs y los guarda en la
misma estructura que ya busca el launcher (art.c):

  <dir>/media/box2d/<nombre>.png              (caratula)      Named_Boxarts
  <dir>/media/screenshot/<nombre>-image.png   (captura)       Named_Snaps
  <dir>/media/titlescreen/<nombre>-image.png  (pantalla titulo)Named_Titles
  <dir>/media/wheel/<nombre>-marquee.png      (logo/marquee)  Named_Logos

Ademas de las imagenes, guarda los metadatos de texto que el launcher lee
(roms.c -> apply_meta_files) en:

  <dir>/media/metadata/<nombre>.meta     (clave=valor, una por linea)
      genre=...
      year=...
      developer=...
      desc=...

Fuentes de metadatos (todas sin coste de ancho de banda apreciable):
  - libretro-database/metadat: genero, desarrollador/editorial y ano (por CRC
    o por nombre normalizado). Se descarga una vez por sistema y se cachea.
  - gamelist.xml local (si existe): descripcion y campos que falten.
  - ScreenScraper (solo si hay screenscraper.cfg): sinopsis. Reutiliza el
    .meta existente para no repetir peticiones.

Los .meta se generan SIEMPRE, aunque --types solo pida imagenes (y al reves).

Uso:
  scrape_libretro.py <rom_dir>            # una plataforma (ej: gba)
  scrape_libretro.py --all                # todas las plataformas conocidas
  scrape_libretro.py <rom_dir> --rom /ruta/al/juego.gba
  scrape_libretro.py <rom_dir> --types box,snap

Opciones:
  --force            re-descarga aunque el archivo ya exista
  --no-meta          no genera/actualiza los .meta
  --roms-root DIR    raiz de ROMs (por defecto /mnt/sdcard/roms)
  --status FILE      archivo de progreso (por defecto /tmp/geminus_scraper.status)
"""

import os, sys, time, argparse, urllib.request, urllib.parse, urllib.error, re, zlib

BASE = "https://thumbnails.libretro.com/"
UA = {"User-Agent": "GeminusOS-scraper/1.0"}

# libretro-database: metadatos de texto (genero, desarrollador, editorial, ano)
METADAT_BASE = "https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/"
METADAT_CACHE = "/tmp/geminus_libretro_metadat"
METADAT_FIELDS = (
    ("genre",       "genre"),
    ("developer",   "developer"),
    ("publisher",   "developer"),   # solo si no hay developer
    ("releaseyear", "year"),
)
SS_CFG = "/mnt/sdcard/GeminusOS/screenscraper.cfg"

# rom_dir -> carpeta de sistema en libretro-thumbnails
SYSTEMS = {
    "gb":            "Nintendo - Game Boy",
    "gbc":           "Nintendo - Game Boy Color",
    "gba":           "Nintendo - Game Boy Advance",
    "nes":           "Nintendo - Nintendo Entertainment System",
    "snes":          "Nintendo - Super Nintendo Entertainment System",
    "genesis":       "Sega - Mega Drive - Genesis",
    "segacd":        "Sega - Mega-CD - Sega CD",
    "sega32x":       "Sega - 32X",
    "mastersystem":  "Sega - Master System - Mark III",
    "gamegear":      "Sega - Game Gear",
    "n64":           "Nintendo - Nintendo 64",
    "psx":           "Sony - PlayStation",
    "nds":           "Nintendo - Nintendo DS",
    "psp":           "Sony - PlayStation Portable",
    "dreamcast":     "Sega - Dreamcast",
    "saturn":        "Sega - Saturn",
    "atari2600":     "Atari - 2600",
    "atari5200":     "Atari - 5200",
    "atari7800":     "Atari - 7800",
    "atari800":      "Atari - 8-bit",
    "atarilynx":     "Atari - Lynx",
    "atarist":       "Atari - ST",
    "c64":           "Commodore - 64",
    "vic20":         "Commodore - VIC-20",
    "amiga":         "Commodore - Amiga",
    "neogeo":        "SNK - Neo Geo",
    "ngp":           "SNK - Neo Geo Pocket",
    "msx":           "Microsoft - MSX",
    "pcengine":      "NEC - PC Engine - TurboGrafx 16",
    "pcenginecd":    "NEC - PC Engine CD - TurboGrafx-CD",
    "wonderswan":    "Bandai - WonderSwan",
    "virtualboy":    "Nintendo - Virtual Boy",
    "pokemini":      "Nintendo - Pokemon Mini",
    "gameandwatch":  "Nintendo - Game and Watch",
    "scummvm":       "ScummVM",
    "dos":           "DOS",
    "cps1":          "FBNeo - Arcade Games",
    "cps2":          "FBNeo - Arcade Games",
    "cps3":          "FBNeo - Arcade Games",
    "fbneo":         "FBNeo - Arcade Games",
    "mame":          "MAME",
    "neocd":         "SNK - Neo Geo CD",
}

# tipo -> (carpeta libretro, subcarpeta destino, sufijo destino)
TYPES = {
    "box":   ("Named_Boxarts", "box2d",       ""),
    "snap":  ("Named_Snaps",   "screenshot",  "-image"),
    "title": ("Named_Titles",  "titlescreen", "-image"),
    "logo":  ("Named_Logos",   "wheel",       "-marquee"),
}

# Extensiones consideradas ROM (union de platforms.c, sin imagenes)
EXTS = {
    "nds", "zip", "7z", "iso", "cso", "prx", "pbp", "chd", "cdi", "gdi",
    "cue", "bin", "m3u", "rar", "pak", "p8",
    "gb", "gbc", "gba", "nes", "smc", "sfc", "md", "smd", "gen", "32x",
    "sms", "gg", "n64", "v64", "z64", "rom",
    "a26", "a52", "a78", "atr", "lnx", "st", "msa", "stx", "ipf",
    "d64", "d71", "d80", "tap", "prg", "crt",
    "adf", "uae", "dms", "adz", "lha", "hdf", "hdz",
    "ngp", "ngc", "dsk", "cas", "pce", "toc", "ws", "wsc", "vb", "min",
    "gw", "scummvm", "dosz", "com", "bat", "exe", "ldb", "sh",
    "ons", "nt", "nt2", "nt3", "dat",
}

SKIP_TOKENS = ("(track ", "[track ", "(disc ", "[disc ", "(disk ", "[disk ")


# ---------------------------------------------------------------- status ---

class Status:
    def __init__(self, path, provider="libretro"):
        self.path = path
        self.provider = provider
        self.state = "RUNNING"
        self.total = 0
        self.done = 0
        self.ok = 0
        self.fail = 0
        self.meta = 0
        self.last = ""
        self.msg = ""
        self.tmp = path + ".tmp"
        self.write()

    def write(self):
        try:
            with open(self.tmp, "w") as f:
                f.write("PROVIDER %s\n" % self.provider)
                f.write("STATE %s\n" % self.state)
                f.write("TOTAL %d\n" % self.total)
                f.write("DONE %d\n" % self.done)
                f.write("OK %d\n" % self.ok)
                f.write("FAIL %d\n" % self.fail)
                f.write("META %d\n" % self.meta)
                f.write("LAST %s\n" % self.last.replace("\n", " "))
                f.write("MSG %s\n" % self.msg.replace("\n", " "))
            os.replace(self.tmp, self.path)
        except Exception:
            pass


# ------------------------------------------------------------- matching ----

def norm(s):
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_dir_cache = {}

def list_dir(system, folder):
    """Devuelve (exact, normalized): nombre exacto y mapa normalizado -> archivo."""
    key = (system, folder)
    if key in _dir_cache:
        return _dir_cache[key]
    url = BASE + urllib.parse.quote(system) + "/" + folder + "/"
    exact, normalized = {}, {}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
        for href in re.findall(r'<a href="([^"]+)">', html):
            fn = urllib.parse.unquote(href)
            if fn.lower().endswith(".png"):
                stem = fn[:-4]
                exact.setdefault(stem.lower(), fn)
                normalized.setdefault(norm(stem), fn)
    except Exception as e:
        sys.stderr.write("[libretro] listado %s: %s\n" % (url, e))
    _dir_cache[key] = (exact, normalized)
    return _dir_cache[key]


def find_remote(index, rom_base):
    exact, normalized = index
    return exact.get(rom_base.lower()) or normalized.get(norm(rom_base))


def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        data = r.read()
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)


# ---------------------------------------------------------------- roms -----

def find_roms(root, rom_dir):
    out = []
    base = os.path.join(root, rom_dir)
    if not os.path.isdir(base):
        return out
    seen = set()
    for dp, _dns, fns in os.walk(base):
        for fn in fns:
            if fn.startswith("."):
                continue
            ext = os.path.splitext(fn)[1][1:].lower()
            if ext not in EXTS:
                continue
            low = fn.lower()
            if any(t in low for t in SKIP_TOKENS):
                continue
            name = os.path.splitext(fn)[0]
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            out.append((name, os.path.join(dp, fn)))
    out.sort(key=lambda x: x[0].lower())
    return out


# ------------------------------------------------------------- metadata ----

def _clean(v):
    """Una sola linea, sin saltos ni espacios repetidos."""
    return re.sub(r"\s+", " ", str(v or "")).strip()


_dat_cache = {}
_ss_cache = {}


def _dat_index(system, field):
    """Devuelve ((crc->valor), (nombre_normalizado->valor)) de un .dat.

    Los .dat de libretro-database son clrmamepro: cada bloque `game (...)` trae
    un `comment` (nombre No-Intro), el campo pedido y el `crc` del ROM.
    Se descargan una sola vez y se cachean en /tmp.
    """
    key = (system, field)
    if key in _dat_cache:
        return _dat_cache[key]

    url = METADAT_BASE + urllib.parse.quote(field) + "/" + urllib.parse.quote(system) + ".dat"
    local = os.path.join(METADAT_CACHE, field, system + ".dat")
    text = None
    try:
        os.makedirs(os.path.dirname(local), exist_ok=True)
        if not os.path.exists(local):
            tmp = local + ".part"
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                data = r.read()
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, local)
        with open(local, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        sys.stderr.write("[libretro] metadat %s/%s: %s\n" % (field, system, e))
        _dat_cache[key] = ({}, {})
        return _dat_cache[key]

    by_crc, by_name = {}, {}

    def commit(cur):
        if not cur:
            return
        val = _clean(cur.get("field"))
        if val:
            if cur.get("crc"):
                by_crc.setdefault(cur["crc"], val)
            if cur.get("name"):
                by_name.setdefault(norm(cur["name"]), val)

    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("game") and s.endswith("("):
            commit(cur)
            cur = {}
            continue
        if cur is None:
            continue
        if s.startswith(")"):
            commit(cur)
            cur = None
            continue
        mc = re.search(r"crc\s+([0-9A-Fa-f]{8})", s)
        if mc and not cur.get("crc"):
            cur["crc"] = mc.group(1).upper()
        mv = re.match(r'%s\s+"(.*)"' % re.escape(field), s)
        if mv and not cur.get("field"):
            cur["field"] = mv.group(1)
        mn = re.match(r'comment\s+"(.*)"', s)
        if mn and not cur.get("name"):
            cur["name"] = mn.group(1)
    commit(cur)

    _dat_cache[key] = (by_crc, by_name)
    return _dat_cache[key]


def rom_crc(path, max_size=64 * 1024 * 1024):
    """CRC32 igual que el que usa ScreenScraper (None si es demasiado grande)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if not size or size > max_size:
        return None
    c = 0
    try:
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                c = zlib.crc32(b, c)
    except OSError:
        return None
    return "%08X" % (c & 0xFFFFFFFF)


def libretro_meta(name, rom_path, system):
    """Genero, ano y desarrollador desde libretro-database/metadat."""
    out = {}
    crc = rom_crc(rom_path)
    nkey = norm(name)
    for field, key in METADAT_FIELDS:
        by_crc, by_name = _dat_index(system, field)
        val = (by_crc.get(crc) if crc else None) or by_name.get(nkey)
        if val and not out.get(key):
            out[key] = val
    return out


def gamelist_meta(rom_dir, name):
    """Metadatos de un gamelist.xml local (EmulationStation/RetroPie)."""
    out = {}
    path = os.path.join(rom_dir, "gamelist.xml")
    if not os.path.exists(path):
        return out
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse(path).getroot()
    except Exception as e:
        sys.stderr.write("[libretro] gamelist %s: %s\n" % (path, e))
        return out

    target = name.lower()
    for g in root.findall("game"):
        p = g.findtext("path") or ""
        base = os.path.splitext(os.path.basename(p))[0]
        if base.lower() != target:
            continue
        for tag, key in (("genre", "genre"), ("developer", "developer"),
                         ("publisher", "developer"), ("releasedate", "year"),
                         ("year", "year"), ("desc", "desc")):
            v = _clean(g.findtext(tag))
            if v and not out.get(key):
                out[key] = v[:4] if key == "year" else v
        break
    return out


def ss_client():
    """Cliente de ScreenScraper solo si hay credenciales (para la sinopsis)."""
    if not os.path.exists(SS_CFG):
        return None
    try:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location(
            "geminus_screenscraper", os.path.join(here, "scrape_screenscraper.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ss = mod.SS(mod.read_cfg())
        return ss if ss.ready() else None
    except Exception as e:
        sys.stderr.write("[libretro] screenscraper no disponible: %s\n" % e)
        return None


def ss_meta(ss, plat, name, rom_path, want):
    """Pide a ScreenScraper solo los campos que faltan (normalmente desc)."""
    if not ss or not want:
        return {}
    try:
        sid = _ss_cache.get(plat)
        if sid is None:
            sid = ss.system_id(plat)
            _ss_cache[plat] = sid
        if not sid:
            return {}
        jeu = ss.game(sid, rom_path, name)
        if not jeu:
            return {}
        genre, year, dev, desc = ss.meta(jeu)
        allv = {"genre": genre, "year": year, "developer": dev, "desc": desc}
        return {k: allv[k] for k in want if allv.get(k)}
    except Exception as e:
        sys.stderr.write("[libretro] ss-meta %s: %s\n" % (name, e))
        return {}


META_KEYS = ("genre", "year", "developer", "desc")


def read_meta(path):
    d = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\r\n")
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), _clean(v)
                if v:
                    d[k] = v
    except Exception:
        pass
    return d


def write_meta(rom_dir, name, values, force=False):
    """Escribe/mezcla media/metadata/<nombre>.meta (formato clave=valor)."""
    values = {k: _clean(v) for k, v in values.items() if _clean(v)}
    path = os.path.join(rom_dir, "media", "metadata", name + ".meta")
    merged = {} if force else read_meta(path)
    for k in META_KEYS:
        v = values.get(k)
        if v and not merged.get(k):
            merged[k] = v
    if not merged:
        return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            for k in META_KEYS:
                if merged.get(k):
                    f.write("%s=%s\n" % (k, merged[k]))
        os.replace(tmp, path)
        return True
    except Exception as e:
        sys.stderr.write("[libretro] meta err %s: %s\n" % (name, e))
        return False


def scrape_metadata(name, rom_path, system, plat, ss):
    """Junta metadatos de todas las fuentes disponibles y guarda el .meta."""
    rom_dir = os.path.dirname(rom_path)
    existing = read_meta(os.path.join(rom_dir, "media", "metadata", name + ".meta"))

    vals = {}
    for src in (libretro_meta(name, rom_path, system), gamelist_meta(rom_dir, name)):
        for k, v in src.items():
            if v and k not in vals:
                vals[k] = v

    # La sinopsis no existe en libretro-database: si falta, se pide a
    # ScreenScraper (solo cuando hay credenciales). El .meta previo evita
    # repetir la peticion en cada pasada.
    if not vals.get("desc") and not existing.get("desc"):
        for k, v in ss_meta(ss, plat, name, rom_path, ("genre", "year", "developer", "desc")).items():
            if k not in vals:
                vals[k] = v

    return write_meta(rom_dir, name, vals)


# ----------------------------------------------------------------- main ----

def scrape_rom(name, rom_path, system, types, force, st, plat=None, meta=True, ss=None):
    st.last = name
    rom_dir = os.path.dirname(rom_path)
    got = 0

    # Los metadatos se generan SIEMPRE, independientemente de --types.
    if meta:
        try:
            if scrape_metadata(name, rom_path, system, plat or "", ss):
                st.meta += 1
        except Exception as e:
            sys.stderr.write("[libretro] meta %s: %s\n" % (name, e))

    for t in types:
        folder, subdir, suffix = TYPES[t]
        ext = "png"
        # respeta jpg existente si ya esta
        dest_dir = os.path.join(rom_dir, "media", subdir)
        dest = os.path.join(dest_dir, name + suffix + "." + ext)
        alt = os.path.join(dest_dir, name + suffix + ".jpg")
        if not force and (os.path.exists(dest) or os.path.exists(alt)):
            continue
        index = list_dir(system, folder)
        if not index[1]:
            continue
        remote = find_remote(index, name)
        if not remote:
            continue
        url = BASE + urllib.parse.quote(system) + "/" + folder + "/" + urllib.parse.quote(remote)
        try:
            download(url, dest)
            st.ok += 1
            got += 1
            sys.stderr.write("[libretro] OK  %-16s %s\n" % (t, name))
        except Exception as e:
            st.fail += 1
            sys.stderr.write("[libretro] ERR %-16s %s: %s\n" % (t, name, e))
    return got


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("platform", nargs="?", help="carpeta de plataforma (ej: gba)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--rom")
    ap.add_argument("--types", default="box,snap,title,logo")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-meta", action="store_true",
                    help="no generar los .meta de metadatos")
    ap.add_argument("--no-desc", action="store_true",
                    help="no pedir sinopsis a ScreenScraper")
    ap.add_argument("--roms-root", default="/mnt/sdcard/roms")
    ap.add_argument("--status", default="/tmp/geminus_scraper.status")
    args = ap.parse_args()

    types = [t for t in args.types.split(",") if t in TYPES]
    if not types:
        types = ["box"]
    do_meta = not args.no_meta
    ss = None if (args.no_desc or not do_meta) else ss_client()

    st = Status(args.status)
    st.msg = "Preparando"
    st.write()

    platforms = []
    if args.all:
        platforms = [d for d in SYSTEMS if os.path.isdir(os.path.join(args.roms_root, d))]
    elif args.platform:
        platforms = [args.platform]
    else:
        st.state = "ERROR"; st.msg = "sin plataforma"; st.write()
        return 2

    # Recolectar trabajos
    jobs = []
    if args.rom:
        name = os.path.splitext(os.path.basename(args.rom))[0]
        jobs.append((args.platform, name, args.rom))
    else:
        for plat in platforms:
            for name, path in find_roms(args.roms_root, plat):
                jobs.append((plat, name, path))

    st.total = len(jobs)
    st.write()
    sys.stderr.write("[libretro] %d ROMs, tipos=%s, metadatos=%s, plataformas=%s\n"
                     % (len(jobs), ",".join(types), "si" if do_meta else "no", platforms))

    t0 = time.time()
    for i, (plat, name, path) in enumerate(jobs):
        system = SYSTEMS.get(plat)
        if not system:
            continue
        scrape_rom(name, path, system, types, args.force, st,
                   plat=plat, meta=do_meta, ss=ss)
        st.done = i + 1
        if st.done % 5 == 0 or st.done == st.total:
            st.write()

    st.state = "DONE"
    st.msg = "%d imagenes, %d metadatos en %.0fs" % (st.ok, st.meta, time.time() - t0)
    st.write()
    sys.stderr.write("[libretro] FIN %d OK, %d fallos, %d metadatos en %.0fs\n"
                     % (st.ok, st.fail, st.meta, time.time() - t0))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
