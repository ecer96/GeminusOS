#!/usr/bin/env python3
"""
ra_local_export.py - Exporta los logros de RetroAchievements de un ROM de NDS
a un script Lua local para DraStic.

No envia ningun desbloqueo a RetroAchievements. Solo descarga la definicion
(titulo, descripcion, badge y MemAddr) y genera:

  <scripts_dir>/<nombre_del_rom>.lua

Uso:
  python3 ra_local_export.py "/mnt/sdcard/roms/nds/Juego.nds"
  python3 ra_local_export.py Juego.nds --game-id 1234
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request

CFG = "/mnt/sdcard/GeminusOS/retroachievements.cfg"
BASE = "https://retroachievements.org/API/"
BADGE = "https://media.retroachievements.org/Badge/%s.png"
DATA_DIR = "/mnt/data/geminus_ach"
SCRIPTS_DIR = "/mnt/vendor/deep/drastic64/scripts"
RUNTIME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ra_local_runtime.lua")
UA = {"User-Agent": "GeminusOS-ach/1.0"}

CONSOLES = {"nds": 18}


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


def api(ep, user, key, **q):
    q.update(u=user, y=key)
    url = BASE + ep + "?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                timeout=40) as r:
        return json.load(r)


def norm(s):
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def find_game(rom, user, key, game_id=None):
    if game_id:
        d = api("API_GetGameExtended.php", user, key, i=game_id)
        return int(game_id), d

    console = CONSOLES["nds"]
    h = md5_file(rom)
    games = api("API_GetGameList.php", user, key, i=console, f=1, h=1)
    for g in games:
        hashes = [str(x).lower() for x in (g.get("Hashes") or [])]
        if h.lower() in hashes:
            gid = int(g["ID"])
            return gid, api("API_GetGameExtended.php", user, key, i=gid)

    wanted = norm(os.path.splitext(os.path.basename(rom))[0])
    best = None
    for g in games:
        n = norm(g.get("Title", ""))
        if n == wanted:
            best = g
            break
        if not best and (wanted in n or n in wanted):
            best = g
    if not best:
        raise RuntimeError("no encontre el juego en RA (hash %s)" % h[:10])
    gid = int(best["ID"])
    return gid, api("API_GetGameExtended.php", user, key, i=gid)


def lua_str(s):
    s = str(s or "")
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "") + '"'


def download_badge(name):
    if not name:
        return False
    os.makedirs(os.path.join(DATA_DIR, "badges"), exist_ok=True)
    dest = os.path.join(DATA_DIR, "badges", name + ".png")
    if os.path.exists(dest):
        return True
    try:
        with urllib.request.urlopen(urllib.request.Request(BADGE % name, headers=UA),
                                    timeout=30) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def build_lua(game, game_id, achievements):
    rows = []
    for a in achievements:
        mem = a.get("MemAddr") or a.get("memaddr") or ""
        if not mem:
            continue
        rows.append(" {id=%d, game=%s, title=%s, desc=%s, points=%s, badge=%s, mem=%s}," % (
            int(a.get("ID", 0)),
            lua_str(game),
            lua_str(a.get("Title", "")),
            lua_str(a.get("Description", "")),
            lua_str(a.get("Points", "")),
            lua_str(a.get("BadgeName", "")),
            lua_str(mem),
        ))
    rt = open(RUNTIME, encoding="utf-8").read()
    return rt.replace("--__ACH__", "\n".join(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--game-id", type=int)
    ap.add_argument("--scripts-dir", default=SCRIPTS_DIR)
    ap.add_argument("--no-badges", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.rom):
        print("ERROR: no existe %s" % args.rom)
        return 1

    cfg = read_cfg()
    user = cfg.get("user", "")
    key = cfg.get("key", "")
    if not user or not key:
        print("ERROR: faltan user/key en %s" % CFG)
        return 1

    try:
        gid, data = find_game(args.rom, user, key, args.game_id)
    except Exception as e:  # noqa: BLE001
        print("ERROR: %s" % e)
        return 1

    title = data.get("Title", "") or os.path.basename(args.rom)
    achs = data.get("Achievements") or {}
    if isinstance(achs, dict):
        achs = list(achs.values())
    with_mem = [a for a in achs if (a.get("MemAddr") or a.get("memaddr"))]
    if not with_mem:
        print("ERROR: la API no devolvio MemAddr para este juego")
        return 1

    os.makedirs(DATA_DIR, exist_ok=True)
    meta = {
        "game_id": gid,
        "title": title,
        "rom": os.path.abspath(args.rom),
        "achievements": achs,
    }
    with open(os.path.join(DATA_DIR, "%d.json" % gid), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    if not args.no_badges:
        for a in with_mem:
            download_badge(a.get("BadgeName", ""))

    lua = build_lua(title, gid, with_mem)
    os.makedirs(args.scripts_dir, exist_ok=True)
    script = os.path.join(args.scripts_dir,
                          os.path.splitext(os.path.basename(args.rom))[0] + ".lua")
    if os.path.exists(script) and not args.force:
        print("ERROR: ya existe %s (usa --force)" % script)
        return 1
    with open(script, "w", encoding="utf-8") as f:
        f.write(lua)

    print("Juego: %s (ID %d)" % (title, gid))
    print("Logros con condiciones: %d/%d" % (len(with_mem), len(achs)))
    print("Script: %s" % script)
    return 0


if __name__ == "__main__":
    sys.exit(main())
