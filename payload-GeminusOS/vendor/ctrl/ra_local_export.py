#!/usr/bin/env python3
"""
ra_local_export.py - Prepara un juego de NDS para logros LOCALES con DraStic.

Descarga la definicion completa (incluidas las condiciones reales) usando el
endpoint de emulador de RetroAchievements y genera:
  scripts/<rom>.lua        -> snapshot de RAM para el daemon
  geminus_ach/<rom>.defs   -> id + MemAddr
  geminus_ach/<rom>.titles -> id + titulo
  geminus_ach/<rom>.meta   -> id, titulo, descripcion, puntos, badge
  geminus_ach/<rom>.addrs  -> direcciones necesarias

No envia ningun desbloqueo a RetroAchievements.
"""
import argparse
import difflib
import hashlib
import hmac
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

CFG = "/mnt/sdcard/GeminusOS/retroachievements.cfg"
API = "https://retroachievements.org/API/"
DOREQ = "https://retroachievements.org/dorequest.php"
BADGE = "https://media.retroachievements.org/Badge/%s.png"
DATA_DIR = "/mnt/data/geminus_ach"
SCRIPTS_DIR = "/mnt/vendor/deep/drastic64/scripts"
RA_TSV = "/mnt/data/geminus_ra.tsv"
KEY_FILE = "/mnt/vendor/ctrl/ach.key"
HERE = os.path.dirname(os.path.abspath(__file__))
SNAP_TEMPLATE = os.path.join(HERE, "ra_local_snapshot.lua")
UA = {"User-Agent": "GeminusOS-ach/1.0"}
CONSOLES = {"nds": 18}

SIZE_BYTES = {"H": 1, " ": 2, "X": 4, "W": 3, "G": 4, "I": 2, "J": 3,
              "L": 1, "U": 1, "K": 1, "M": 1, "N": 1, "O": 1, "P": 1,
              "Q": 1, "R": 1, "S": 1, "T": 1}


def read_cfg():
    d = {}
    try:
        with open(CFG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    d[k.strip()] = v.strip()
    except OSError:
        pass
    return d


def get_json(url, **q):
    url = url + "?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                timeout=40) as r:
        return json.load(r)


def api(ep, user, key, **q):
    q.update(u=user, y=key)
    return get_json(API + ep, **q)


def ra_login(user, password):
    d = get_json(DOREQ, r="login", u=user, p=password)
    if not d.get("Success") or not d.get("Token"):
        raise RuntimeError("login rechazado")
    return d["Token"]


def ra_patch(user, token, gid):
    d = get_json(DOREQ, r="patch", u=user, t=token, g=gid)
    if not d.get("Success") or "PatchData" not in d:
        raise RuntimeError("sin PatchData")
    return d["PatchData"]


def norm(s):
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# Nombres que RetroAchievements usa de forma distinta al nombre del ROM.
# Solo se aplican cuando la diferencia es de titulo, nunca para "adivinar"
# juegos parecidos.
TITLE_ALIASES = {
    "dk jungle climber": "donkey kong jungle climber",
    "professor layton and pandoras box": "professor layton and the diabolical box",
    "professor layton and pandora s box": "professor layton and the diabolical box",
    "professor laytons london life hack": "professor layton s london life",
}

# Etiquetas de sets auxiliares. Nunca se eligen si existe el juego base.
AUX_RE = re.compile(
    r"(?:^~[^~]+~\s*|\[(?:subset|hack|demo|prototype|homebrew)[^\]]*\])",
    re.I)


def norm_title(s):
    """Normaliza un titulo para compararlo sin depender de region o puntuacion."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.sub(r"^(?:~[^~]+~\s*)+", "", s.strip())
    s = s.replace("&", " and ")
    s = re.sub(r",\s*(?:the|a|an)\s*$", "", s, flags=re.I)
    s = re.sub(r"^(?:the|a|an)\s+", "", s.strip(), flags=re.I)
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return TITLE_ALIASES.get(s, s)


STOP_WORDS = {"the", "a", "an", "of", "and", "version", "edition", "nintendo", "ds"}


def title_tokens(s):
    return {t for t in norm_title(s).split() if t not in STOP_WORDS}


def _token_covered(tok, other):
    if tok in other:
        return True
    if tok.isdigit():
        return False
    for o in other:
        if o.isdigit():
            continue
        if min(len(tok), len(o)) >= 3 and (o.startswith(tok) or tok.startswith(o)):
            return True
        if difflib.SequenceMatcher(None, tok, o).ratio() >= 0.84:
            return True
    return False


def titles_match(a, b):
    """True solo si los dos titulos describen el mismo juego.

    La cobertura simetrica de tokens evita los falsos positivos tipicos de
    usar substring: por ejemplo, "N+" contiene la letra n que aparece en casi
    cualquier titulo, pero sus tokens no cubren los del otro juego.
    """
    A, B = title_tokens(a), title_tokens(b)
    if not A or not B:
        return False
    if A == B:
        return True
    # Los numeros (2, 3...) son parte importante del titulo. No permitimos
    # confundir "Devil Survivor" con "Devil Survivor 2" o "Zoo Tycoon" con
    # "Zoo Tycoon 2".
    if {x for x in A if x.isdigit()} != {x for x in B if x.isdigit()}:
        return False
    if not all(_token_covered(x, B) for x in A):
        return False
    if not all(_token_covered(x, A) for x in B):
        return False
    return difflib.SequenceMatcher(None, norm_title(a), norm_title(b)).ratio() >= 0.86


def _is_aux_title(title):
    return bool(re.search(r"~[^~]+~|\[(?:subset|hack|demo|prototype|homebrew)",
                          str(title or ""), re.I))


def _game_candidates(games, rom_title):
    """Devuelve (juego, titulo, es_aux) ordenados por calidad de coincidencia."""
    out = []
    for g in games:
        # Algunos juegos agrupan dos versiones en un solo titulo: "A | B".
        for part in re.split(r"\s*\|\s*", str(g.get("Title", ""))):
            if not titles_match(rom_title, part):
                continue
            score = difflib.SequenceMatcher(
                None, norm_title(rom_title), norm_title(part)).ratio()
            out.append((score, _is_aux_title(part), int(g["ID"]), part))
    out.sort(key=lambda x: (x[1], -x[0], x[2]))
    return out


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def gid_from_tsv(rom):
    """El TSV de ra_sync ya trae el GameID: awarded, total, gid, ruta."""
    try:
        with open(RA_TSV, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) >= 4 and parts[3] == rom:
                    return int(parts[2])
    except OSError:
        pass
    return None


def find_game_id(rom, user, key):
    gid = gid_from_tsv(rom)
    if gid:
        return gid

    games = api("API_GetGameList.php", user, key, i=CONSOLES["nds"], f=1, h=1)
    rom_title = os.path.splitext(os.path.basename(rom))[0]
    candidates = _game_candidates(games, rom_title)

    # Los sets "[Subset ...]" son ampliaciones de un juego base. No se usan
    # como sustituto del set principal: eso hacia que varios juegos distintos
    # compartieran logros. Si no hay set base, se trata como "sin logros".
    base = [c for c in candidates if not c[1]]
    if not base:
        raise RuntimeError("juego no encontrado en RA")

    # Si hay varias coincidencias, solo aceptamos una claramente mejor. Un
    # empate entre IDs distintos es ambiguo y es preferible no inventar datos.
    top_score = base[0][0]
    top = [c for c in base if abs(c[0] - top_score) < 0.015]
    ids = {c[2] for c in top}
    if len(ids) > 1:
        raise RuntimeError("varias coincidencias ambiguas en RA: %s" %
                           ", ".join("%s (%s)" % (c[3], c[2]) for c in top))
    return base[0][2]


def extract_addrs(memaddr):
    """Devuelve [(ra_addr, code)] de una condicion MemAddr."""
    out = {}
    text = memaddr
    # 16-bit: "0x 1234"
    for m in re.finditer(r"0x ([0-9a-fA-F]+)", text):
        a = int(m.group(1), 16)
        out.setdefault(a, " ")
    # resto: "0xH1234", "0xX1234", ...
    for m in re.finditer(r"0x([hHxXwWgGiIjJlLuUkKmMnNoOpPqQrRsStT]?)([0-9a-fA-F]+)", text):
        code = m.group(1) or " "
        a = int(m.group(2), 16)
        if code not in SIZE_BYTES:
            code = " "
        out.setdefault(a, code)
    return list(out.items())


def collect_addrs(achievements):
    addrs = {}
    for a in achievements:
        for ra, code in extract_addrs(a.get("MemAddr", "")):
            if ra in addrs:
                if SIZE_BYTES.get(code, 1) > SIZE_BYTES.get(addrs[ra], 1):
                    addrs[ra] = code
            else:
                addrs[ra] = code
    return addrs


def lua_num(v):
    return "0x%X" % v


def build_lua(addrs):
    tpl = open(SNAP_TEMPLATE, encoding="utf-8").read()
    rows = []
    for ra in sorted(addrs):
        real = ra if ra >= 0x02000000 else ra + 0x02000000
        rows.append(" {a=%s, r=%s}," % (lua_num(ra), lua_num(real)))
    return tpl.replace("--__ADDRS__", "\n".join(rows))


def load_key():
    try:
        with open(KEY_FILE, "rb") as f:
            k = f.read()
        if len(k) >= 16:
            return k
    except OSError:
        pass
    k = os.urandom(32)
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    tmp = KEY_FILE + ".tmp"
    try:
        os.unlink(tmp)
    except OSError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, k)
    finally:
        os.close(fd)
    os.replace(tmp, KEY_FILE)
    return k


def sign_files(base, script):
    """Firma .defs/.meta/.addrs/.lua con HMAC-SHA256 y clave del dispositivo."""
    key = load_key()
    files = [
        (base + ".defs", os.path.join(DATA_DIR, base + ".defs")),
        (base + ".meta", os.path.join(DATA_DIR, base + ".meta")),
        (base + ".addrs", os.path.join(DATA_DIR, base + ".addrs")),
        (os.path.basename(script), script),
    ]
    h = hmac.new(key, digestmod=hashlib.sha256)
    for name, path in files:
        if not os.path.isfile(path):
            raise RuntimeError("falta %s para firmar" % path)
        h.update(name.encode("utf-8") + b"\0")
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        h.update(b"\0")
    sig = h.hexdigest()
    dest = os.path.join(DATA_DIR, base + ".sig")
    with open(dest, "w", encoding="ascii") as f:
        f.write(sig + "\n")
    os.chmod(dest, 0o600)
    return sig


def purge_local(base, scripts_dir):
    """Elimina solo los datos generados de un juego (no toca ROMs ni saves)."""
    for ext in (".defs", ".meta", ".titles", ".addrs", ".json", ".sig"):
        try:
            os.remove(os.path.join(DATA_DIR, base + ext))
        except OSError:
            pass
    if scripts_dir:
        try:
            os.remove(os.path.join(scripts_dir, base + ".lua"))
        except OSError:
            pass
    for nd in ("/mnt/vendor/deep/nnddss/User/scripts",
               "/mnt/vendor/deep/nnddss/scripts"):
        try:
            os.remove(os.path.join(nd, base + ".lua"))
        except OSError:
            pass


def other_game_with_id(base, gid, title):
    """Busca otro ROM que ya use este GameID con un titulo distinto."""
    try:
        names = os.listdir(DATA_DIR)
    except OSError:
        return None
    for name in names:
        if not name.endswith(".json"):
            continue
        other = name[:-5]
        if other == base:
            continue
        try:
            with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if int(d.get("game_id") or 0) != int(gid):
            continue
        if titles_match(d.get("title", ""), title):
            continue
        return other, d.get("title", "")
    return None


def secure_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        os.chmod(DATA_DIR, 0o700)
        for name in os.listdir(DATA_DIR):
            p = os.path.join(DATA_DIR, name)
            if os.path.isfile(p):
                os.chmod(p, 0o600)
        bdir = os.path.join(DATA_DIR, "badges")
        if os.path.isdir(bdir):
            os.chmod(bdir, 0o700)
            for name in os.listdir(bdir):
                p = os.path.join(bdir, name)
                if os.path.isfile(p):
                    os.chmod(p, 0o600)
    except OSError:
        pass


def main():
    os.umask(0o077)
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--game-id", type=int)
    ap.add_argument("--scripts-dir", default=SCRIPTS_DIR)
    ap.add_argument("--no-badges", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--auto", action="store_true",
                    help="modo lanzamiento: marca juegos sin logros")
    ap.add_argument("--token", help="token de sesion ya obtenido (evita login)")
    ap.add_argument("--sign-only", action="store_true",
                    help="solo firma los ficheros ya exportados")
    args = ap.parse_args()

    if not os.path.isfile(args.rom):
        print("ERROR: no existe %s" % args.rom)
        return 1

    base = os.path.splitext(os.path.basename(args.rom))[0]
    script = os.path.join(args.scripts_dir, base + ".lua")

    if args.sign_only:
        try:
            sig = sign_files(base, script)
        except Exception as e:
            print("ERROR: no se pudo firmar: %s" % e)
            return 1
        secure_data()
        print("Firma: %s/%s.sig (%s)" % (DATA_DIR, base, sig[:16]))
        return 0

    none_marker = os.path.join(DATA_DIR, base + ".none")
    if args.auto and os.path.exists(none_marker):
        print("Sin logros (marcado): %s" % none_marker)
        return 2

    cfg = read_cfg()
    user = cfg.get("user", "")
    key = cfg.get("key", "")
    password = cfg.get("pass", "")
    if not user or not key or not password:
        print("ERROR: faltan user/key/pass en %s" % CFG)
        return 1

    try:
        gid = args.game_id or find_game_id(args.rom, user, key)
    except Exception as e:
        if args.auto and "no encontrado" in str(e):
            purge_local(base, args.scripts_dir)
            open(none_marker, "w").close()
            os.chmod(none_marker, 0o600)
            print("Sin logros en RetroAchievements para este juego")
            return 2
        print("ERROR: no se pudo identificar el juego: %s" % e)
        return 1

    token = args.token or ra_login(user, password)
    patch = ra_patch(user, token, gid)
    title = patch.get("Title", "") or os.path.basename(args.rom)
    other = other_game_with_id(base, gid, title)
    if other:
        print("ERROR: el GameID %d (%s) ya pertenece a otro juego: %s" %
              (gid, title, other[0]))
        return 1
    achs = patch.get("Achievements") or []
    if isinstance(achs, dict):
        achs = list(achs.values())
    # Los [VOID] son marcadores internos de RA, no logros que deban
    # entregarse al jugador. Tampoco se incluyen los avisos tecnicos.
    achs = [a for a in achs if a.get("MemAddr") and
            not a.get("Title", "").startswith("Warning:") and
            not a.get("Title", "").startswith("[VOID]")]
    if not achs:
        print("ERROR: no hay logros con condiciones")
        if args.auto:
            purge_local(base, args.scripts_dir)
            open(none_marker, "w").close()
            os.chmod(none_marker, 0o600)
            return 2
        return 1

    addrs = collect_addrs(achs)
    if not addrs:
        print("ERROR: no se pudieron extraer direcciones")
        return 1

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, base + ".defs"), "w", encoding="utf-8") as f:
        for a in achs:
            f.write("%s\t%s\n" % (a.get("ID"), a.get("MemAddr")))
    with open(os.path.join(DATA_DIR, base + ".titles"), "w", encoding="utf-8") as f:
        for a in achs:
            f.write("%s\t%s\n" % (a.get("ID"), a.get("Title", "")))
    def clean(v):
        return str(v or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")
    with open(os.path.join(DATA_DIR, base + ".meta"), "w", encoding="utf-8") as f:
        for a in achs:
            f.write("%s\t%s\t%s\t%s\t%s\n" % (
                a.get("ID"), clean(a.get("Title")), clean(a.get("Description")),
                clean(a.get("Points")), clean(a.get("BadgeName"))))
    with open(os.path.join(DATA_DIR, base + ".addrs"), "w", encoding="utf-8") as f:
        for ra in sorted(addrs):
            f.write("%d\t%s\n" % (ra, addrs[ra]))
    with open(os.path.join(DATA_DIR, base + ".json"), "w", encoding="utf-8") as f:
        json.dump({"game_id": gid, "title": title,
                   "rom": os.path.basename(args.rom),
                   "achievements": achs},
                  f, ensure_ascii=False, indent=1)

    if not args.no_badges:
        os.makedirs(os.path.join(DATA_DIR, "badges"), exist_ok=True)
        for a in achs:
            name = a.get("BadgeName", "")
            if not name:
                continue
            dest = os.path.join(DATA_DIR, "badges", name + ".png")
            if os.path.exists(dest):
                continue
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(BADGE % name, headers=UA),
                        timeout=30) as r:
                    open(dest, "wb").write(r.read())
            except Exception:
                pass

    os.makedirs(args.scripts_dir, exist_ok=True)
    if os.path.exists(script) and not args.force:
        print("ERROR: ya existe %s (usa --force)" % script)
        return 1
    with open(script, "w", encoding="utf-8") as f:
        f.write(build_lua(addrs))
    os.chmod(script, 0o600)

    try:
        os.remove(none_marker)
    except OSError:
        pass

    try:
        sig = sign_files(base, script)
    except Exception as e:
        print("ERROR: no se pudo firmar los datos: %s" % e)
        return 1
    secure_data()

    print("Juego: %s (ID %d)" % (title, gid))
    print("Firma: %s.sig" % base)
    print("Logros: %d" % len(achs))
    print("Direcciones: %d" % len(addrs))
    print("Script: %s" % script)
    print("Defs: %s/%s.defs" % (DATA_DIR, base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
