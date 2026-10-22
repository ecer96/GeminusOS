#!/usr/bin/env python3
"""
ra_sync.py — Sincroniza RetroAchievements a /mnt/data/geminus_ra.tsv

Formato del TSV: <awarded>\t<total>\t<path_completo_al_rom>

Requiere: /mnt/sdcard/GeminusOS/retroachievements.cfg con user y key.
"""
import os, re, json, hashlib, urllib.request, urllib.parse, sys, time

CFG     = "/mnt/sdcard/GeminusOS/retroachievements.cfg"
OUT     = "/mnt/data/geminus_ra.tsv"
HASHES  = "/mnt/data/geminus_ra_hashes.json"
ROOTS   = ["/mnt/sdcard/roms"]

# Mapa carpeta rom -> id de consola en RetroAchievements
# Fuente: https://retroachievements.org/API (console IDs)
CONSOLES = {
    "gb":           4,
    "gbc":          6,
    "gba":          5,
    "nes":          7,
    "snes":         3,
    "genesis":      1,
    "megadrive":    1,
    "n64":          2,
    "psx":          12,
    "nds":          18,
    "mastersystem": 11,
    "gamegear":     15,
    "pcengine":     8,
    "dreamcast":    40,
    "saturn":       39,
    "psp":          41,
}

# Consolas cuyo hash de archivo completo suele coincidir con RA
HASHABLE = {4, 6, 5, 11, 15, 8}

EXTS = {".gb", ".gbc", ".gba", ".sms", ".gg", ".pce", ".nes", ".sfc", ".smc",
        ".n64", ".z64", ".v64", ".md", ".gen", ".bin", ".nds",
        ".zip", ".7z", ".chd", ".cue", ".iso", ".gdi", ".cdi"}

# --- Leer credenciales -------------------------------------------------

def read_cfg():
    try:
        cfg = dict(l.strip().split("=", 1) for l in open(CFG) if "=" in l and not l.startswith("#"))
    except Exception:
        return None, None
    return cfg.get("user", "").strip(), cfg.get("key", "").strip()

# --- API ---------------------------------------------------------------

def api(ep, **q):
    q.update(u=USER, y=KEY)
    url = "https://retroachievements.org/API/%s?%s" % (ep, urllib.parse.urlencode(q))
    req = urllib.request.Request(url, headers={"User-Agent": "GeminusOS-ra/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def norm(s):
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

# --- MD5 con caché -----------------------------------------------------

def load_hashes():
    try:
        return json.load(open(HASHES))
    except Exception:
        return {}

hc = load_hashes()

def md5(p):
    st = os.stat(p)
    k = "%d:%d" % (st.st_mtime, st.st_size)
    if p in hc and hc[p][0] == k:
        return hc[p][1]
    if st.st_size > 64 * 1024 * 1024:
        return None
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    hc[p] = [k, h.hexdigest()]
    return hc[p][1]

# --- Main --------------------------------------------------------------

def main():
    global USER, KEY
    USER, KEY = read_cfg()
    if not USER or not KEY:
        print("[ra_sync] sin credenciales en %s" % CFG, file=sys.stderr)
        return 1

    t0 = time.time()
    errors = 0
    print("[ra_sync] user=%s" % USER, file=sys.stderr)

    # 1) Progreso del usuario (GameID -> awarded)
    awarded = {}
    off = 0
    while True:
        try:
            d = api("API_GetUserCompletionProgress.php", u=USER, c=500, o=off)
        except Exception as e:
            print("[ra_sync] error progress: %s" % e, file=sys.stderr)
            errors += 1
            break
        for g in d.get("Results", []):
            awarded[g["GameID"]] = g.get("NumAwarded", 0)
        off += 500
        if off >= d.get("Total", 0):
            break

    print("[ra_sync] progreso: %d juegos" % len(awarded), file=sys.stderr)

    # 2) Lista de juegos por consola, cacheando hashes
    lines = []
    for cid in sorted(set(CONSOLES.values())):
        try:
            games = api("API_GetGameList.php", i=cid, f=1, h=1)
        except Exception as e:
            print("[ra_sync] error gamelist cid=%d: %s" % (cid, e), file=sys.stderr)
            errors += 1
            continue

        by_hash  = {}
        by_title = {}
        for g in games:
            for h in g.get("Hashes", []):
                by_hash[h.lower()] = g
            by_title.setdefault(norm(g["Title"]), g)

        for rd, c in CONSOLES.items():
            if c != cid:
                continue
            for root in ROOTS:
                for variant in (rd, rd.upper()):
                    d = os.path.join(root, variant)
                    if not os.path.isdir(d):
                        continue
                    for fn in os.listdir(d):
                        base, ext = os.path.splitext(fn)
                        if ext.lower() not in EXTS:
                            continue
                        p = os.path.join(d, fn)
                        g = None
                        if cid in HASHABLE:
                            try:
                                h = md5(p)
                                if h:
                                    g = by_hash.get(h)
                            except Exception:
                                pass
                        if not g:
                            g = by_title.get(norm(base))
                        if g and g.get("NumAchievements", 0) > 0:
                            lines.append("%d\t%d\t%d\t%s" % (
                                awarded.get(g["ID"], 0),
                                g["NumAchievements"],
                                g["ID"],
                                p))

    # 3) Guardar
    # Nunca vaciar una lista válida por un fallo de red: si no hay resultados
    # y hubo errores, se conserva el TSV anterior.
    if not lines and errors:
        print("[ra_sync] red no disponible (%d errores); se conserva el TSV anterior"
              % errors, file=sys.stderr)
        return 1

    try:
        json.dump(hc, open(HASHES, "w"))
    except Exception:
        pass

    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, OUT)

    print("[ra_sync] %d juegos con logros (%d hashes cacheados) en %.1fs"
          % (len(lines), len(hc), time.time() - t0), file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
