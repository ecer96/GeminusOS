#!/usr/bin/env python3
"""
scrape_screenscraper.py - Scraper de ScreenScraper.fr para GeminusOS.

Usa la API oficial v2 (https://api.screenscraper.fr/api2). ScreenScraper exige
credenciales de desarrollador, que van incluidas con la aplicacion (el usuario
final no las ve ni las configura):

  /mnt/vendor/ctrl/apps/screenscraper.dev   (devid, devpassword, softname)

La cuenta del usuario se guarda en:

  /mnt/sdcard/GeminusOS/screenscraper.cfg

Formato (clave=valor):
  ssid=tu_usuario
  sspassword=tu_clave
  # opcional:
  region=wor,us,eu,ss,jp,fr,de,es,it
  systemeid=75            # fuerza un id de sistema concreto

Descarga y guarda en la estructura que busca el launcher (art.c):
  media/box2d/<nombre>.<ext>        (box-2D)
  media/screenshot/<nombre>-image.<ext>   (ss)
  media/titlescreen/<nombre>-image.<ext>  (sstitle)
  media/wheel/<nombre>-marquee.<ext>      (wheel)
  media/fanart/<nombre>-fanart.<ext>      (fanart)
  media/cartridge/<nombre>-cartridge.<ext>(support-2D)
  media/metadata/<nombre>.meta            (genre/year/developer/desc)

Los .meta se generan siempre, aunque --types solo pida imagenes.

Uso:
  scrape_screenscraper.py <rom_dir>
  scrape_screenscraper.py --all
  scrape_screenscraper.py <rom_dir> --rom /ruta/juego.gba
  scrape_screenscraper.py <rom_dir> --types box,snap
"""

import os, sys, time, argparse, urllib.request, urllib.parse, urllib.error, re, json, zlib

API = "https://api.screenscraper.fr/api2/"
DEV_CFG = "/mnt/vendor/ctrl/apps/screenscraper.dev"
CFG = "/mnt/sdcard/GeminusOS/screenscraper.cfg"
UA = {"User-Agent": "GeminusOS-scraper/1.0"}

# tipo destino -> tipos SS por prioridad
TYPE_MAP = {
    "box":   (["box-2D", "box-3D"],           "box2d",       ""),
    "snap":  (["ss", "screenshot"],           "screenshot",  "-image"),
    "title": (["sstitle", "title"],           "titlescreen", "-image"),
    "logo":  (["wheel", "wheel-hd", "wheel-tilt", "marquee"], "wheel", "-marquee"),
    "fanart":(["fanart"],                     "fanart",      "-fanart"),
    "cart":  (["support-2D", "cartridge"],    "cartridge",   "-cartridge"),
}

# rom_dir -> posibles nombres de sistema en ScreenScraper
SYSTEM_NAMES = {
    "gb":           ["Game Boy"],
    "gbc":          ["Game Boy Color"],
    "gba":          ["Game Boy Advance"],
    "nes":          ["Nintendo Entertainment System", "NES", "Famicom"],
    "snes":         ["Super Nintendo", "Super Famicom", "SNES"],
    "genesis":      ["Megadrive", "Mega Drive", "Genesis"],
    "segacd":       ["Mega-CD", "Sega CD", "Mega CD"],
    "sega32x":      ["32X", "Sega 32X"],
    "mastersystem": ["Master System", "Mark III"],
    "gamegear":     ["Game Gear"],
    "n64":          ["Nintendo 64", "N64"],
    "psx":          ["PlayStation", "PSX"],
    "nds":          ["Nintendo DS", "NDS"],
    "psp":          ["PlayStation Portable", "PSP"],
    "dreamcast":    ["Dreamcast"],
    "saturn":       ["Saturn"],
    "atari2600":    ["Atari 2600"],
    "atari5200":    ["Atari 5200"],
    "atari7800":    ["Atari 7800"],
    "atari800":     ["Atari 8-bit", "Atari 800"],
    "atarilynx":    ["Atari Lynx", "Lynx"],
    "atarist":      ["Atari ST"],
    "c64":          ["Commodore 64", "C64"],
    "vic20":        ["VIC-20", "Commodore VIC-20"],
    "amiga":        ["Amiga"],
    "neogeo":       ["Neo-Geo", "Neo Geo"],
    "ngp":          ["Neo Geo Pocket", "Neo Geo Pocket Color"],
    "msx":          ["MSX"],
    "pcengine":     ["PC Engine", "TurboGrafx-16", "TurboGrafx"],
    "pcenginecd":   ["PC Engine CD", "TurboGrafx-CD", "TurboGrafx CD"],
    "wonderswan":   ["WonderSwan"],
    "virtualboy":   ["Virtual Boy"],
    "pokemini":     ["Pokemon Mini"],
    "gameandwatch": ["Game & Watch", "Game and Watch"],
    "scummvm":      ["ScummVM"],
    "dos":          ["DOS"],
    "cps1":         ["CP System", "CPS1"],
    "cps2":         ["CP System II", "CPS2"],
    "cps3":         ["CP System III", "CPS3"],
    "fbneo":        ["FinalBurn Neo", "FBNeo"],
    "mame":         ["MAME"],
    "neocd":        ["Neo-Geo CD", "Neo Geo CD"],
}

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
    def __init__(self, path, provider="screenscraper"):
        self.path = path
        self.provider = provider
        self.state = "RUNNING"
        self.total = 0
        self.done = 0
        self.ok = 0
        self.fail = 0
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
                f.write("LAST %s\n" % self.last.replace("\n", " "))
                f.write("MSG %s\n" % self.msg.replace("\n", " "))
            os.replace(self.tmp, self.path)
        except Exception:
            pass


# ------------------------------------------------------------------ api ----

def read_cfg(path=None):
    cfg = {}
    try:
        with open(path or CFG) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    except Exception:
        pass
    return cfg


class SS:
    def __init__(self, cfg):
        self.cfg = cfg
        self.devid = cfg.get("devid", "")
        self.devpassword = cfg.get("devpassword", "")
        self.softname = cfg.get("softname", "GeminusOS")
        self.ssid = cfg.get("ssid", "")
        self.sspassword = cfg.get("sspassword", "")
        self.regions = [r.strip().lower() for r in
                        cfg.get("region", "wor,us,eu,ss,jp,fr,de,es,it").split(",") if r.strip()]
        self.systems = None
        self.last_req = 0.0

    def ready(self):
        return bool(self.devid and self.devpassword)

    def _get(self, endpoint, **params):
        # respeta un minimo entre peticiones (limite de la API)
        dt = time.time() - self.last_req
        if dt < 1.0:
            time.sleep(1.0 - dt)
        p = dict(params)
        p.update(devid=self.devid, devpassword=self.devpassword,
                 softname=self.softname, output="json")
        if self.ssid:
            p["ssid"] = self.ssid
        if self.sspassword:
            p["sspassword"] = self.sspassword
        url = API + endpoint + "?" + urllib.parse.urlencode(p)
        self.last_req = time.time()
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return json.load(r)

    def load_systems(self):
        if self.systems is not None:
            return self.systems
        self.systems = []
        try:
            d = self._get("systemesListe.php")
            for s in d.get("response", {}).get("systemes", []):
                noms = s.get("noms", {})
                labels = [str(v) for k, v in noms.items() if k.startswith("nom")]
                self.systems.append((str(s.get("id", "")), labels))
        except Exception as e:
            sys.stderr.write("[ss] systemesListe: %s\n" % e)
        return self.systems

    def system_id(self, rom_dir):
        forced = self.cfg.get("systemeid", "").strip()
        if forced.isdigit():
            return forced
        cands = SYSTEM_NAMES.get(rom_dir)
        if not cands:
            return None
        for sid, labels in self.load_systems():
            for c in cands:
                cl = c.lower()
                for l in labels:
                    if cl == l.lower() or cl in l.lower():
                        return sid
        sys.stderr.write("[ss] sistema no resuelto para %s\n" % rom_dir)
        return None

    def game(self, system_id, rom_path, rom_name):
        try:
            size = os.path.getsize(rom_path)
        except OSError:
            size = 0
        crc = None
        if size and size <= 64 * 1024 * 1024:
            c = 0
            try:
                with open(rom_path, "rb") as f:
                    for b in iter(lambda: f.read(1 << 20), b""):
                        c = zlib.crc32(b, c)
                crc = "%08X" % (c & 0xFFFFFFFF)
            except OSError:
                crc = None
        params = {"systemeid": system_id, "romtype": "rom",
                  "romnom": os.path.basename(rom_path)}
        if size:
            params["romtaille"] = size
        if crc:
            params["crc"] = crc
        d = self._get("jeuInfos.php", **params)
        return d.get("response", {}).get("jeu")

    @staticmethod
    def _loc(v):
        if isinstance(v, dict):
            if v.get("text"):
                return str(v["text"])
            noms = v.get("noms", {})
            for k in ("nom_eu", "nom_us", "nom_wor", "nom_en", "nom_jp"):
                if noms.get(k):
                    return str(noms[k])
            for k in noms:
                if noms[k]:
                    return str(noms[k])
            return ""
        if isinstance(v, list):
            for it in v:
                r = SS._loc(it)
                if r:
                    return r
            return ""
        return str(v) if v else ""

    @staticmethod
    def meta(jeu):
        """Devuelve (genre, year, dev, desc) saneados a una sola linea."""
        def one(v):
            return re.sub(r"\s+", " ", str(v or "")).strip()

        genre = one(SS._loc(jeu.get("genres") or jeu.get("genre")))
        d = SS._loc(jeu.get("dates") or jeu.get("date"))
        year = ""
        m = re.match(r"(\d{4})", str(d)) if d else None
        if m:
            year = m.group(1)
        dev = one(SS._loc(jeu.get("developpeur") or jeu.get("developer") or jeu.get("editeur")))
        desc = ""
        syn = jeu.get("synopsis")
        if isinstance(syn, list) and syn:
            pick = None
            for s in syn:
                if s.get("langue") == "es":
                    pick = s
                    break
            if not pick:
                for s in syn:
                    if s.get("langue") in ("en", "wor", "us"):
                        pick = s
                        break
            if not pick:
                pick = syn[0]
            desc = one(pick.get("text", ""))
        elif syn:
            desc = one(syn)
        return genre, year, dev, desc

    def pick_media(self, jeu, types):
        medias = jeu.get("medias", []) if jeu else []
        for t in types:
            best = None
            for m in medias:
                if m.get("type") != t:
                    continue
                reg = str(m.get("region", "")).lower()
                try:
                    rank = self.regions.index(reg)
                except ValueError:
                    rank = len(self.regions) + 5
                url = m.get("url") or m.get("url_php") or ""
                if not url:
                    continue
                if best is None or rank < best[0]:
                    best = (rank, url, m.get("format", "png"))
            if best:
                return best[1], best[2]
        return None, None


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


def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        data = r.read()
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)


# ----------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("platform", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--rom")
    ap.add_argument("--types", default="box,snap,title,logo")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--roms-root", default="/mnt/sdcard/roms")
    ap.add_argument("--status", default="/tmp/geminus_scraper.status")
    args = ap.parse_args()

    types = [t for t in args.types.split(",") if t in TYPE_MAP]
    if not types:
        types = ["box"]

    st = Status(args.status)
    # Credenciales de la aplicacion + cuenta del usuario.
    cfg = read_cfg(DEV_CFG)
    cfg.update(read_cfg(CFG))
    ss = SS(cfg)

    if not ss.ready():
        st.state = "ERROR"
        st.msg = "ScreenScraper no esta configurado"
        st.write()
        sys.stderr.write("[ss] %s\n" % st.msg)
        return 2

    platforms = []
    if args.all:
        platforms = [d for d in SYSTEM_NAMES if os.path.isdir(os.path.join(args.roms_root, d))]
    elif args.platform:
        platforms = [args.platform]
    else:
        st.state = "ERROR"; st.msg = "sin plataforma"; st.write()
        return 2

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
    sys.stderr.write("[ss] %d ROMs, tipos=%s, plataformas=%s\n"
                     % (len(jobs), ",".join(types), platforms))

    t0 = time.time()
    sysid_cache = {}
    for i, (plat, name, path) in enumerate(jobs):
        st.last = name
        if plat not in sysid_cache:
            sysid_cache[plat] = ss.system_id(plat)
        sid = sysid_cache[plat]
        if not sid:
            st.done = i + 1
            continue
        try:
            jeu = ss.game(sid, path, name)
        except urllib.error.HTTPError as e:
            st.fail += 1
            sys.stderr.write("[ss] HTTP %s %s\n" % (e.code, name))
            jeu = None
        except Exception as e:
            st.fail += 1
            sys.stderr.write("[ss] ERR %s: %s\n" % (name, e))
            jeu = None

        if jeu:
            rom_dir = os.path.dirname(path)
            # Metadatos: SIEMPRE, aunque --types solo pida imagenes.
            try:
                genre, year, dev, desc = ss.meta(jeu)
                if genre or year or dev or desc:
                    mdir = os.path.join(rom_dir, "media", "metadata")
                    os.makedirs(mdir, exist_ok=True)
                    with open(os.path.join(mdir, name + ".meta"), "w") as mf:
                        if genre: mf.write("genre=%s\n" % genre)
                        if year:  mf.write("year=%s\n" % year)
                        if dev:   mf.write("developer=%s\n" % dev)
                        if desc:  mf.write("desc=%s\n" % desc)
            except Exception as e:
                sys.stderr.write("[ss] meta err %s: %s\n" % (name, e))
            for t in types:
                ss_types, subdir, suffix = TYPE_MAP[t]
                url, fmt = ss.pick_media(jeu, ss_types)
                if not url:
                    continue
                ext = (fmt or "png").lower()
                dest = os.path.join(rom_dir, "media", subdir, name + suffix + "." + ext)
                if not args.force and os.path.exists(dest):
                    continue
                try:
                    download(url, dest)
                    st.ok += 1
                    sys.stderr.write("[ss] OK  %-16s %s\n" % (t, name))
                except Exception as e:
                    st.fail += 1
                    sys.stderr.write("[ss] DL-ERR %s %s: %s\n" % (t, name, e))
        st.done = i + 1
        if st.done % 5 == 0 or st.done == st.total:
            st.write()

    st.state = "DONE"
    st.msg = "%d imagenes en %.0fs" % (st.ok, time.time() - t0)
    st.write()
    sys.stderr.write("[ss] FIN %d OK, %d fallos en %.0fs\n"
                     % (st.ok, st.fail, time.time() - t0))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
