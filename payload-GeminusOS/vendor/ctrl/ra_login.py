#!/usr/bin/env python3
"""
ra_login.py - Valida usuario/contraseña de RetroAchievements y configura
RetroArch para los logros dentro del juego.

- Llama a API_Login.php con usuario y contraseña.
- Guarda la clave API devuelta en /mnt/sdcard/GeminusOS/retroachievements.cfg.
- Escribe cheevos_enable/cheevos_username/cheevos_password en los
  retroarch.cfg que existan.
- Lanza ra_sync.py para refrescar los logros del launcher.
"""
import glob
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

CFG = "/mnt/sdcard/GeminusOS/retroachievements.cfg"
UA = {"User-Agent": "GeminusOS-ra/1.0"}

RA_DIRS = [
    "/.config/retroarch",
    "/root/.config/retroarch",
    "/mnt/data/.config/retroarch",
    os.path.expanduser("~/.config/retroarch"),
]


def log(msg):
    print(msg, flush=True)


def read_cfg():
    d = {}
    try:
        with open(CFG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    except OSError:
        pass
    return d


def write_cfg(d):
    tmp = CFG + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("# RetroAchievements: usuario y contraseña de retroachievements.org\n")
            f.write("user=%s\n" % d.get("user", ""))
            f.write("pass=%s\n" % d.get("pass", ""))
            f.write("key=%s\n" % d.get("key", ""))
        os.replace(tmp, CFG)
    except OSError as e:
        log("no se pudo guardar la config: %s" % e)


def api_login(user, password):
    url = "https://retroachievements.org/API/API_Login.php?" + urllib.parse.urlencode(
        {"u": user, "p": password})
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if not data.get("Success"):
        raise RuntimeError("credenciales rechazadas")
    token = data.get("Token") or data.get("APIKey") or data.get("ApiKey") or ""
    if not token:
        raise RuntimeError("la API no devolvió clave")
    return token


def ra_quote(v):
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def set_kv(path, key, value):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return False

    pat = re.compile(r"^\s*" + re.escape(key) + r"\s*=")
    out = []
    found = False
    for line in lines:
        if pat.match(line):
            out.append("%s = %s\n" % (key, value))
            found = True
        else:
            out.append(line)
    if not found:
        out.append("%s = %s\n" % (key, value))

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out)
        return True
    except OSError:
        return False


def configure_retroarch(user, password):
    seen = set()
    files = []
    for d in RA_DIRS:
        real = os.path.realpath(d)
        if real in seen or not os.path.isdir(real):
            continue
        seen.add(real)
        files.append(os.path.join(real, "retroarch.cfg"))
        files.extend(glob.glob(os.path.join(real, "retroarch_*.cfg")))

    files = [f for f in dict.fromkeys(files) if os.path.isfile(f)]
    if not files:
        log("AVISO: no encontré retroarch.cfg")
        return

    for f in files:
        set_kv(f, "cheevos_enable", ra_quote("true"))
        set_kv(f, "cheevos_username", ra_quote(user))
        set_kv(f, "cheevos_password", ra_quote(password))
        log("configurado %s" % f)


def main():
    cfg = read_cfg()
    user = cfg.get("user", "").strip()
    password = cfg.get("pass", "").strip()

    if not user:
        log("ERROR: falta el usuario")
        return 2

    if password:
        try:
            key = api_login(user, password)
        except Exception as e:  # noqa: BLE001
            log("ERROR al validar credenciales: %s" % e)
            log("Se conserva la clave API anterior si existía.")
            key = cfg.get("key", "").strip()
        else:
            cfg["key"] = key
            write_cfg(cfg)
            log("clave API obtenida y guardada")
    else:
        key = cfg.get("key", "").strip()
        log("sin contraseña nueva: se usa la clave existente")

    if password:
        configure_retroarch(user, password)

    if key:
        subprocess.run(["python3", "/mnt/vendor/ctrl/ra_sync.py"],
                       check=False)
        log("sincronización lanzada")
    else:
        log("AVISO: no hay clave API; no se puede sincronizar")

    return 0


if __name__ == "__main__":
    sys.exit(main())
