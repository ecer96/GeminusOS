#!/usr/bin/env python3
"""
scrape_thegamesdb.py - Scraper gratuito de TheGamesDB.

Fuente: https://thegamesdb.net (API v1). La clave de API es gratuita: se
registra una cuenta en https://api.thegamesdb.net/key.php y se pega en

  /mnt/sdcard/GeminusOS/thegamesdb.cfg

  apikey=TU_CLAVE

Descarga caratula, captura, logo y fanart y los guarda en la misma estructura
que art.c:

  media/box2d/<nombre>.<ext>
  media/screenshot/<nombre>-image.<ext>
  media/titlescreen/<nombre>-image.<ext>
  media/wheel/<nombre>-marquee.<ext>
  media/fanart/<nombre>-fanart.<ext>
  media/metadata/<nombre>.meta   (genre/year/developer/desc)

Uso:
  scrape_thegamesdb.py <rom_dir>
  scrape_thegamesdb.py --all
  scrape_thegamesdb.py <rom_dir> --rom /ruta/juego.gba
  scrape_thegamesdb.py <rom_dir> --types box,snap
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_libretro import Status, find_roms, norm, write_meta  # noqa: E402

API = "https://api.thegamesdb.net/v1"
CFG = "/mnt/sdcard/GeminusOS/thegamesdb.cfg"
CACHE = "/tmp/geminus_tgdb_platforms.json"
UA = {"User-Agent": "GeminusOS-scraper/1.0"}

# rom_dir -> nombres posibles de plataforma en TheGamesDB
SYSTEM_NAMES = {
    "gb":           ["Game Boy"],
    "gbc":          ["Game Boy Color"],
    "gba":          ["Game Boy Advance"],
    "nes":          ["Nintendo Entertainment System", "Famicom"],
    "snes":         ["Super Nintendo", "Super Famicom"],
    "genesis":      ["Genesis", "Mega Drive"],
    "segacd":       ["Sega CD", "Mega-CD"],
    "sega32x":      ["32X"],
    "mastersystem": ["Master System"],
    "gamegear":     ["Game Gear"],
    "n64":          ["Nintendo 64"],
    "psx":          ["PlayStation"],
    "nds":          ["Nintendo DS"],
    "psp":          ["PlayStation Portable"],
    "dreamcast":    ["Dreamcast"],
    "saturn":       ["Saturn"],
    "atari2600":    ["Atari 2600"],
    "atari5200":    ["Atari 5200"],
    "atari7800":    ["Atari 7800"],
    "atari800":     ["Atari 8-bit", "Atari 800"],
    "atarilynx":    ["Atari Lynx", "Lynx"],
    "atarist":      ["Atari ST"],
    "c64":          ["Commodore 64"],
    "vic20":        ["VIC-20"],
    "amiga":        ["Amiga"],
    "neogeo":       ["Neo Geo"],
    "ngp":          ["Neo Geo Pocket"],
    "msx":          ["MSX"],
    "pcengine":     ["TurboGrafx-16", "PC Engine"],
    "pcenginecd":   ["TurboGrafx-CD"],
    "wonderswan":   ["WonderSwan"],
    "virtualboy":   ["Virtual Boy"],
    "gameandwatch": ["Game & Watch"],
    "scummvm":      ["ScummVM"],
    "dos":          ["DOS"],
    "cps1":         ["Arcade"],
    "cps2":         ["Arcade"],
    "cps3":         ["Arcade"],
    "fbneo":        ["Arcade"],
    "mame":         ["Arcade"],
}

TYPE_MAP = {
    "box":   ("boxart",    "box2d",      ""),
    "snap":  ("screenshot", "screenshot", "-image"),
    "title": ("titlescreen", "titlescreen", "-image"),
    "logo":  ("clearlogo", "wheel",      "-marquee"),
    "fanart": ("fanart",   "fanart",     "-fanart"),
}


def read_cfg():
    cfg = {}
    try:
        with open(CFG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    except OSError:
        pass
    return cfg


def api_get(apikey, endpoint, **params):
    p = dict(params)
    p["apikey"] = apikey
    url = API + endpoint + "?" + urllib.parse.urlencode(p)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
            raise
    return {}


def load_platforms(apikey):
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        pass
    data = api_get(apikey, "/Platforms", fields="name")
    plats = data.get("data", {}).get("platforms", {})
    out = {}
    for pid, p in plats.items():
        out[str(pid)] = p.get("name", "")
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(out, f)
    except OSError:
        pass
    return out


def platform_id(platforms, rom_dir):
    cands = SYSTEM_NAMES.get(rom_dir)
    if not cands:
        return None
    best = None
    for pid, pname in platforms.items():
        n = pname.lower()
        for c in cands:
            cl = c.lower()
            if cl == n:
                score = 3
            elif cl in n:
                score = 2
            elif n in cl:
                score = 1
            else:
                continue
            if best is None or score > best[0] or (score == best[0] and len(n) < len(best[2])):
                best = (score, pid, n)
    return best[1] if best else None


def pick_game(games, pid):
    if pid:
        for g in games:
            if str(g.get("platform")) == str(pid):
                return g
    return games[0] if games else None


def save_image(base_url, filename, dest):
    if not filename:
        return False
    if os.path.exists(dest):
        return False
    url = base_url + urllib.parse.quote(filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=60) as r:
            data = r.read()
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
        return True
    except Exception as e:
        sys.stderr.write("[tgdb] imagen %s: %s\n" % (url, e))
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def _map_names(payload, key):
    """Extrae {id: nombre} de /Genres, /Developers o /Publishers."""
    node = payload.get("data", {}) if isinstance(payload, dict) else {}
    for k in (key, key[:-1] if key.endswith("s") else key):
        tbl = node.get(k)
        if isinstance(tbl, dict):
            out = {}
            for kk, vv in tbl.items():
                if isinstance(vv, dict):
                    out[str(kk)] = vv.get("name") or vv.get("genre") or ""
                elif isinstance(vv, str):
                    out[str(kk)] = vv
            if out:
                return out
        elif isinstance(tbl, list):
            out = {}
            for vv in tbl:
                if isinstance(vv, dict):
                    out[str(vv.get("id"))] = vv.get("name", "")
            if out:
                return out
    return {}


MAP_CACHE = "/tmp/geminus_tgdb_maps.json"


def load_name_maps(apikey):
    try:
        with open(MAP_CACHE, encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("apikey") == apikey and cached.get("genres"):
            return cached
    except (OSError, ValueError):
        pass

    maps = {"apikey": apikey, "genres": {}, "developers": {}, "publishers": {}}
    for key, endpoint in (("genres", "/Genres"),
                          ("developers", "/Developers"),
                          ("publishers", "/Publishers")):
        try:
            maps[key] = _map_names(api_get(apikey, endpoint), key)
        except Exception as e:  # noqa: BLE001 - sin mapa se omite el campo
            sys.stderr.write("[tgdb] mapa %s: %s\n" % (key, e))
    try:
        with open(MAP_CACHE, "w", encoding="utf-8") as f:
            json.dump(maps, f)
    except OSError:
        pass
    return maps


def _resolve(maps, inline, key, ids):
    if not isinstance(ids, list):
        return []
    table = {}
    if isinstance(inline, dict):
        table.update(inline)
    table.update(maps.get(key, {}) or {})
    return [table.get(str(i), "") for i in ids if table.get(str(i))]


def meta_from_game(g, maps=None, inline=None):
    maps = maps or {}
    inline = inline or {}
    vals = {}
    rel = g.get("release_date") or ""
    m = re.match(r"(\d{4})", str(rel))
    if m:
        vals["year"] = m.group(1)
    genres = _resolve(maps, inline.get("genres"), "genres", g.get("genres"))
    if genres:
        vals["genre"] = ", ".join(genres)
    names = _resolve(maps, inline.get("developers"), "developers", g.get("developers"))
    if not names:
        names = _resolve(maps, inline.get("publishers"), "publishers", g.get("publishers"))
    if names:
        vals["developer"] = ", ".join(names)
    if g.get("overview"):
        vals["desc"] = g["overview"]
    return vals


def scrape(rom_dir, rom_filter, types, force, st, root="/mnt/sdcard/roms", all_plats=False):
    cfg = read_cfg()
    apikey = cfg.get("apikey", "")
    if not apikey:
        st.state = "ERROR"
        st.msg = "TheGamesDB: falta la API key (gratis en thegamesdb.net)"
        st.write()
        sys.stderr.write("[tgdb] %s\n" % st.msg)
        return 2

    platforms = load_platforms(apikey)
    name_maps = load_name_maps(apikey)
    plat_dirs = ([d for d in SYSTEM_NAMES if os.path.isdir(os.path.join(root, d))]
                 if all_plats else [rom_dir])
    roms = []
    for d in plat_dirs:
        for name, path in find_roms(root, d):
            roms.append((d, name, path))
    if rom_filter:
        roms = [r for r in roms if os.path.abspath(r[2]) == os.path.abspath(rom_filter)]
    st.total = len(roms)
    st.write()

    for d, name, path in roms:
        st.last = name
        st.done += 1
        try:
            pid = platform_id(platforms, d)
            search = norm(name) or name
            data = api_get(apikey, "/Games/ByGameName", name=search,
                           fields="overview,developers,publishers,genres,release_date,platform",
                           include="boxart")
            games = data.get("data", {}).get("games", [])
            if not games:
                st.fail += 1
                st.write()
                time.sleep(1)
                continue
            g = pick_game(games, pid)
            gid = str(g.get("id"))
            base_url = (data.get("include", {}).get("boxart", {})
                            .get("base_url", {}).get("original", ""))
            boxart = (data.get("include", {}).get("boxart", {})
                          .get("data", {}).get(gid, []))

            got = 0
            for t in types:
                if t not in TYPE_MAP:
                    continue
                btype, folder, suffix = TYPE_MAP[t]
                entries = [b for b in boxart if b.get("type") == btype]
                if t == "box":
                    entries.sort(key=lambda b: 0 if b.get("side") == "front" else 1)
                if not entries:
                    continue
                fn = entries[0].get("filename", "")
                ext = os.path.splitext(fn)[1] or ".jpg"
                dest = os.path.join(os.path.dirname(path), "media", folder,
                                    name + suffix + ext)
                if save_image(base_url, fn, dest):
                    got += 1

            if write_meta(os.path.dirname(path), name,
                          meta_from_game(g, name_maps,
                                         data.get("data", {})), force):
                st.meta += 1
            st.ok += 1
            st.write()
        except Exception as e:
            st.fail += 1
            st.msg = str(e)
            st.write()
            sys.stderr.write("[tgdb] %s: %s\n" % (name, e))
        time.sleep(1.2)

    st.state = "DONE"
    st.msg = "%d imagenes, %d metadatos" % (st.ok, st.meta)
    st.write()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("platform", nargs="?", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--rom")
    ap.add_argument("--types", default="box,snap,title,logo,fanart")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--roms-root", default="/mnt/sdcard/roms")
    ap.add_argument("--status", default="/tmp/geminus_scraper.status")
    args = ap.parse_args()

    types = [t for t in args.types.split(",") if t]
    st = Status(args.status, "thegamesdb")
    try:
        return scrape(args.platform, args.rom, types, args.force, st,
                      args.roms_root, args.all)
    except Exception as e:
        st.state = "ERROR"
        st.msg = str(e)
        st.write()
        return 2


if __name__ == "__main__":
    sys.exit(main())
