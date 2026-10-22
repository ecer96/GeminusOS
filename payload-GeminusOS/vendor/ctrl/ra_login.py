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


STATUS = "/mnt/data/geminus_ra_login.status"


def status(state, msg):
    try:
        tmp = STATUS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("state=%s\nmsg=%s\n" % (state, msg.replace("\n", " ")))
        os.replace(tmp, STATUS)
    except OSError:
        pass


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


def verify_key(user, key):
    """Comprueba que la clave sirve para la Web API (y=)."""
    if not user or not key:
        return False
    url = "https://retroachievements.org/API/API_GetUserProfile.php?" + urllib.parse.urlencode(
        {"u": user, "y": key})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=30) as r:
            data = json.load(r)
        return bool(data.get("User") or data.get("Username") or data.get("ID"))
    except Exception as e:  # noqa: BLE001
        log("clave API no válida: %s" % e)
        return False


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
        # Un token viejo/inválido impide el login aunque la contraseña sea
        # correcta: RetroArch lo usa en lugar de cheevos_password.
        set_kv(f, "cheevos_token", ra_quote(""))
        log("configurado %s" % f)


def main():
    cfg = read_cfg()
    user = cfg.get("user", "").strip()
    password = cfg.get("pass", "").strip()

    # Configs guardadas por versiones con el bug: la "contraseña" era la
    # propia clave API. No sirve para API_Login ni para RetroArch.
    if password and password == cfg.get("key", "").strip():
        password = ""

    status("running", "Validando credenciales...")

    if not user:
        status("error", "Falta el usuario de RetroAchievements")
        log("ERROR: falta el usuario")
        return 2

    oldkey = cfg.get("key", "").strip()
    key = oldkey

    # API_Login está obsoleto (devuelve 401 siempre). La contraseña se
    # escribe directamente en RetroArch, que hace su propio login.
    # Para la lista del launcher solo se valida la Web API Key.
    if key and not verify_key(user, key):
        log("la clave API guardada no es válida")
        key = ""

    if not key:
        status("error", "Falta la clave API web (pégala en el 3er campo)")
    else:
        status("running", "Sincronizando logros...")

    if password:
        configure_retroarch(user, password)

    try:
        with open("/mnt/data/geminus_ra_login.stamp", "w") as st:
            st.write(str(int(__import__("time").time())) + "\n")
    except OSError:
        pass

    if key:
        rc = subprocess.run(["python3", "/mnt/vendor/ctrl/ra_sync.py"],
                            check=False, capture_output=True, text=True)
        if rc.stderr:
            print(rc.stderr, end="")
        if rc.returncode == 0:
            n = 0
            try:
                with open("/mnt/data/geminus_ra.tsv", encoding="utf-8") as tsv:
                    n = sum(1 for _ in tsv)
            except OSError:
                pass
            status("ok", "Logros sincronizados: %d juegos" % n)
            log("sincronización OK: %d juegos" % n)
        else:
            detail = ""
            for line in (rc.stderr or "").splitlines():
                if "error" in line.lower() or "401" in line or "403" in line:
                    detail = line.strip()
                    break
            if not detail:
                detail = (rc.stderr or "").strip().splitlines()[-1] if (rc.stderr or "").strip() else ""
            msg = "No se pudieron sincronizar los logros"
            if detail:
                msg += ": " + detail[:90]
            status("error", msg)
            log("ERROR: ra_sync.py devolvió %d" % rc.returncode)
    else:
        log("AVISO: no hay clave API válida; no se puede sincronizar")

    return 0


if __name__ == "__main__":
    sys.exit(main())
