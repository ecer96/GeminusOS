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
import hashlib
import hmac
import json
import os
import re
import sys
import time
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
    h = md5_file(rom)
    games = api("API_GetGameList.php", user, key, i=CONSOLES["nds"], f=1, h=1)
    for g in games:
        if h.lower() in [str(x).lower() for x in (g.get("Hashes") or [])]:
            return int(g["ID"])
    wanted = norm(os.path.splitext(os.path.basename(rom))[0])
    best = None
    for g in games:
        n = norm(g.get("Title", ""))
        if n == wanted:
            return int(g["ID"])
        if not best and (wanted in n or n in wanted):
            best = g
    if best:
        return int(best["ID"])
    raise RuntimeError("juego no encontrado en RA")


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
            open(none_marker, "w").close()
            os.chmod(none_marker, 0o600)
            print("Sin logros en RetroAchievements para este juego")
            return 2
        print("ERROR: no se pudo identificar el juego: %s" % e)
        return 1

    token = args.token or ra_login(user, password)
    patch = ra_patch(user, token, gid)
    title = patch.get("Title", "") or os.path.basename(args.rom)
    achs = patch.get("Achievements") or []
    if isinstance(achs, dict):
        achs = list(achs.values())
    achs = [a for a in achs if a.get("MemAddr") and not a.get("Title", "").startswith("Warning:")]
    if not achs:
        print("ERROR: no hay logros con condiciones")
        if args.auto:
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
        json.dump({"game_id": gid, "title": title, "achievements": achs},
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
