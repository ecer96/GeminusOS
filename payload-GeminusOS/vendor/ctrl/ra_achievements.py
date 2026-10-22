#!/usr/bin/env python3
"""
ra_achievements.py <game_id>

Descarga la lista de logros de un juego de RetroAchievements
+ los badges PNG de cada logro (cacheados).

- Lista:  /mnt/data/geminus_ra_achievements/<game_id>.json
- Badges: /mnt/data/geminus_ra_badges/<badge>.png
"""
import os, sys, json, urllib.request, urllib.parse

CFG       = "/mnt/sdcard/GeminusOS/retroachievements.cfg"
OUT_DIR   = "/mnt/data/geminus_ra_achievements"
BADGE_DIR = "/mnt/data/geminus_ra_badges"
BADGE_URL = "https://media.retroachievements.org/Badge/%s.png"

def read_cfg():
    try:
        cfg = dict(l.strip().split("=", 1) for l in open(CFG) if "=" in l and not l.startswith("#"))
    except Exception:
        return None, None
    return cfg.get("user", "").strip(), cfg.get("key", "").strip()

def api(ep, **q):
    q.update(z=USER, y=KEY)
    url = "https://retroachievements.org/API/%s?%s" % (ep, urllib.parse.urlencode(q))
    req = urllib.request.Request(url, headers={"User-Agent": "GeminusOS-ra/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def download_badge(badge):
    """Descarga el badge si no existe. Devuelve 1 si OK."""
    if not badge:
        return 0
    path = os.path.join(BADGE_DIR, "%s.png" % badge)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return 1
    try:
        url = BADGE_URL % badge
        req = urllib.request.Request(url, headers={"User-Agent": "GeminusOS-ra/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        if not data:
            return 0
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return 1
    except Exception as e:
        print("  badge %s: %s" % (badge, e), file=sys.stderr)
        return 0

def main():
    global USER, KEY
    if len(sys.argv) != 2:
        print("Uso: %s <game_id>" % sys.argv[0], file=sys.stderr)
        return 1

    try:
        game_id = int(sys.argv[1])
    except ValueError:
        print("game_id invalido", file=sys.stderr)
        return 1

    USER, KEY = read_cfg()
    if not USER or not KEY:
        print("Sin credenciales", file=sys.stderr)
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BADGE_DIR, exist_ok=True)

    try:
        d = api("API_GetGameInfoAndUserProgress.php", g=game_id, u=USER)
    except Exception as e:
        print("Error API: %s" % e, file=sys.stderr)
        return 1

    achs = d.get("Achievements", {})
    lista = []
    descargados = 0
    for k, a in achs.items():
        badge = a.get("BadgeName", "")
        if badge and download_badge(badge):
            descargados += 1
        lista.append({
            "id":     a.get("ID", 0),
            "title":  a.get("Title", ""),
            "desc":   a.get("Description", ""),
            "points": int(a.get("Points", 0)),
            "earned": bool(a.get("DateEarned", "")),
            "date":   a.get("DateEarned", ""),
            "badge":  badge,
            "order":  int(a.get("DisplayOrder", 0)),
        })
    lista.sort(key=lambda x: x["order"])

    out = {
        "game_id":     game_id,
        "title":       d.get("Title", ""),
        "console":     d.get("ConsoleName", ""),
        "total":       int(d.get("NumAchievements", 0)),
        "awarded":     int(d.get("NumAwardedToUser", 0)),
        "points_hard": int(d.get("PointsTotal", 0)),
        "points_user": int(d.get("UserTotalPoints", 0)),
        "achievements": lista,
    }

    path = os.path.join(OUT_DIR, "%d.json" % game_id)
    with open(path + ".tmp", "w") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(path + ".tmp", path)

    print("OK: %d logros, %d badges descargados -> %s" % (len(lista), descargados, path),
          file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
