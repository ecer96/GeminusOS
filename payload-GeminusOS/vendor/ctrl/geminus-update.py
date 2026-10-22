#!/usr/bin/env python3
# geminus-update.py - Actualizaciones de GeminusOS por WiFi.
#
# Uso:
#   geminus-update.py check [--force]   busca una version nueva (respeta cache)
#   geminus-update.py apply             descarga e instala la version disponible
#   geminus-update.py state             imprime el estado actual
#
# El launcher solo lee /mnt/data/geminus-update/state y muestra el aviso.
# Estados: idle | checking | available | downloading | applying | done | error
#
# El paquete es el payload (launcher, apps, scripts), no la imagen completa.

import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request

REPO = "ecer96/GeminusOS"
TAG_URL = "https://api.github.com/repos/%s/releases/latest" % REPO
ASSET = "geminus-payload.tar.gz"
ASSET_SHA = ASSET + ".sha256"
VENDOR = os.environ.get("GEMINUS_VENDOR", "/mnt/vendor")
CTRL = os.path.join(VENDOR, "ctrl")
STATE_DIR = os.environ.get("GEMINUS_UPDATE_DIR", "/mnt/data/geminus-update")
ROOTFS = os.environ.get("GEMINUS_ROOTFS", "/")
STATE_FILE = os.path.join(STATE_DIR, "state")
VERSION_FILE = os.path.join(CTRL, "version")
DEFAULT_VERSION = "v1"
CHECK_TTL = 3600  # no consultar GitHub mas de una vez cada hora
LOCK_DIR = os.path.join(STATE_DIR, ".lock")


def _state_write(state, version="", pct=0, msg=""):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("state=%s\nversion=%s\npct=%d\nmsg=%s\n" %
                (state, version, pct, msg.replace("\n", " ")))
    os.replace(tmp, STATE_FILE)


def _state_read():
    data = {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k] = v
    except OSError:
        pass
    return data


def _ver_tuple(s):
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums) if nums else None


def is_newer(latest, current):
    """True solo si `latest` es una version posterior a `current`.

    Evita ofrecer "actualizaciones" cuando el tag es igual o anterior
    (por ejemplo, tag v1 con la v1.1 ya instalada).
    """
    a, b = _ver_tuple(latest), _ver_tuple(current)
    if a is not None and b is not None:
        n = max(len(a), len(b))
        return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))
    return (latest or "") != (current or "")


def installed_version():
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip() or DEFAULT_VERSION
    except OSError:
        return DEFAULT_VERSION


def _ssl_context():
    ctx = ssl.create_default_context()
    for ca in ("/etc/ssl/certs/ca-certificates.crt",
               "/etc/pki/tls/certs/ca-bundle.crt",
               "/etc/ssl/cert.pem"):
        if os.path.exists(ca):
            try:
                ctx.load_verify_locations(ca)
                break
            except ssl.SSLError:
                pass
    return ctx


def _open(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "GeminusOS-updater/1.0",
        "Accept": "application/vnd.github+json",
    })
    return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())


def _lock():
    os.makedirs(STATE_DIR, exist_ok=True)
    for _ in range(10):
        try:
            os.mkdir(LOCK_DIR)
            return True
        except FileExistsError:
            # Un check/apply anterior puede haberse quedado colgado.
            try:
                if time.time() - os.path.getmtime(LOCK_DIR) > 3600:
                    shutil.rmtree(LOCK_DIR, ignore_errors=True)
                    continue
            except OSError:
                pass
            return False
    return False


def _unlock():
    shutil.rmtree(LOCK_DIR, ignore_errors=True)


def latest_release():
    with _open(TAG_URL) as r:
        data = json.load(r)
    tag = data.get("tag_name", "")
    assets = {a.get("name"): a.get("browser_download_url", "")
              for a in data.get("assets", [])}
    if not tag or not assets.get(ASSET):
        raise RuntimeError("el ultimo release no tiene %s" % ASSET)
    return tag, assets[ASSET], assets.get(ASSET_SHA, "")


def cmd_check(force=False):
    st = _state_read()
    try:
        if not force and time.time() - os.path.getmtime(STATE_FILE) < CHECK_TTL \
                and st.get("state") in ("idle", "available", "done") \
                and st.get("version") == installed_version():
            return 0
    except OSError:
        pass

    if not _lock():
        return 0
    try:
        _state_write("checking")
        tag, _, _ = latest_release()
        if is_newer(tag, installed_version()):
            _state_write("available", tag, 0, "version %s disponible" % tag)
        else:
            _state_write("idle", tag, 0, "al dia")
    except Exception as e:  # noqa: BLE001 - cualquier fallo es "sin conexion"
        _state_write("idle", installed_version(), 0, "sin conexion: %s" % e)
    finally:
        _unlock()
    return 0


def _download(url, dest, tag, pct_from=0, pct_to=70):
    total = 0
    try:
        with _open(url) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            last = 0
            with open(dest + ".part", "wb") as f:
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = pct_from + (pct_to - pct_from) * done // total
                        now = time.time()
                        if now - last > 0.5:
                            last = now
                            _state_write("downloading", tag, pct, "descargando")
        os.replace(dest + ".part", dest)
    except Exception:
        try:
            os.remove(dest + ".part")
        except OSError:
            pass
        raise


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _backup(tag):
    backup = os.path.join(STATE_DIR, "backup-ctrl.tar.gz")
    with tarfile.open(backup, "w:gz") as t:
        if os.path.isdir(CTRL):
            t.add(CTRL, arcname="ctrl")
        if os.path.exists(VERSION_FILE):
            t.add(VERSION_FILE, arcname="ctrl/version")
    return backup


def _restore(backup):
    with tarfile.open(backup, "r:gz") as t:
        t.extractall(VENDOR)


def cmd_apply():
    if not _lock():
        return 0
    tag = installed_version()
    try:
        tag, url, sha_url = latest_release()
        if not is_newer(tag, installed_version()):
            _state_write("idle", tag, 0, "al dia")
            return 0

        os.makedirs(STATE_DIR, exist_ok=True)
        pkg = os.path.join(STATE_DIR, ASSET)
        sha_file = os.path.join(STATE_DIR, ASSET_SHA)

        _state_write("downloading", tag, 0, "descargando")
        if sha_url:
            _download(sha_url, sha_file, tag, 0, 5)
        _download(url, pkg, tag, 5, 70)

        if sha_url:
            with open(sha_file, encoding="utf-8") as f:
                expected = f.read().split()[0].strip().lower()
            if expected and _sha256(pkg) != expected:
                raise RuntimeError("la verificación SHA-256 no coincide")

        _state_write("applying", tag, 75, "instalando")
        stage = os.path.join(STATE_DIR, "stage")
        shutil.rmtree(stage, ignore_errors=True)
        os.makedirs(stage, exist_ok=True)
        with tarfile.open(pkg, "r:gz") as t:
            t.extractall(stage)

        deploy = os.path.join(stage, "deploy.sh")
        if not os.path.isfile(deploy):
            raise RuntimeError("el paquete no contiene deploy.sh")

        backup = _backup(tag)
        try:
            subprocess.run(["/bin/sh", deploy, VENDOR, ROOTFS], check=True)
        except Exception:
            _restore(backup)
            raise

        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(tag + "\n")
        subprocess.run(["/bin/sync"], check=False)

        _state_write("done", tag, 100, "instalada")
    except Exception as e:  # noqa: BLE001
        _state_write("error", tag, 0, "no se pudo actualizar: %s" % e)
    finally:
        _unlock()
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "state"
    if cmd == "check":
        return cmd_check("--force" in argv)
    if cmd == "apply":
        return cmd_apply()
    st = _state_read()
    print("state=%s version=%s pct=%s msg=%s" % (
        st.get("state", "idle"), st.get("version", installed_version()),
        st.get("pct", "0"), st.get("msg", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
