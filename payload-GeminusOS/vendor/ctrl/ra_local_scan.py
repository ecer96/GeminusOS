#!/usr/bin/env python3
"""
ra_local_scan.py - Escaneo por lotes de logros locales de NDS.

Uso:
  ra_local_scan.py --list /tmp/geminus_ach_scan.list [--refresh]

--list contiene una ruta de ROM por linea. Sin --refresh se saltan los juegos
que ya tienen datos firmados; con --refresh se vuelven a descargar todos.
No envia ningun desbloqueo a RetroAchievements.
"""
import argparse
import fcntl
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ra_local_export as ex

STATUS = "/tmp/geminus_ach_scan.status"
LOCK = "/tmp/geminus_ach_scan.lock"
TOAST = "/mnt/vendor/ctrl/geminus-ach-toast"


def write_status(state, done, total, ok, none, fail, current=""):
    tmp = STATUS + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("state=%s\n" % state)
            f.write("done=%d\n" % done)
            f.write("total=%d\n" % total)
            f.write("ok=%d\n" % ok)
            f.write("none=%d\n" % none)
            f.write("fail=%d\n" % fail)
            f.write("current=%s\n" % current.replace("\n", " "))
        os.chmod(tmp, 0o600)
        os.replace(tmp, STATUS)
    except OSError:
        pass


def notify(label, title, subtitle, ms=6000):
    if not os.path.isfile(TOAST) or not os.access(TOAST, os.X_OK):
        return
    try:
        subprocess.run([TOAST, "--label=" + label, "--title=" + title,
                        "--subtitle=" + subtitle, "--duration=%d" % ms],
                       timeout=10, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def has_data(rom):
    base = os.path.splitext(os.path.basename(rom))[0]
    for ext in (".defs", ".meta", ".addrs", ".sig"):
        if not os.path.isfile(os.path.join(ex.DATA_DIR, base + ext)):
            return False
    if not os.path.isfile(ex.KEY_FILE):
        return False
    return os.path.isfile(os.path.join(ex.SCRIPTS_DIR, base + ".lua"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--timeout", type=int, default=50)
    args = ap.parse_args()

    os.umask(0o077)

    lf = open(LOCK, "a+")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Ya hay un escaneo en curso", flush=True)
        return 0

    try:
        with open(args.list, encoding="utf-8") as f:
            roms = [l.strip() for l in f if l.strip()]
    except OSError as e:
        write_status("error", 0, 0, 0, 0, 0, str(e))
        print("No se pudo leer la lista: %s" % e, flush=True)
        return 1

    # Quitar duplicados manteniendo el orden.
    seen = set()
    roms = [r for r in roms if os.path.isfile(r) and not (r in seen or seen.add(r))]

    cfg = ex.read_cfg()
    user, password = cfg.get("user", ""), cfg.get("pass", "")
    if not user or not password:
        write_status("error", 0, len(roms), 0, 0, 0, "sin configuracion RA")
        notify("ESCANEO DE LOGROS", "Falta configurar RetroAchievements",
               "Ajustes > RetroAchievements", 7000)
        print("Faltan credenciales en %s" % ex.CFG, flush=True)
        return 1

    try:
        token = ex.ra_login(user, password)
    except Exception as e:
        write_status("error", 0, len(roms), 0, 0, 0, "login fallido")
        notify("ESCANEO DE LOGROS", "No se pudo conectar",
               "Comprueba la red y la cuenta", 7000)
        print("Login fallido: %s" % e, flush=True)
        return 1

    total = len(roms)
    ok = none = fail = skipped = 0
    write_status("running", 0, total, ok, none, fail)
    print("[scan] %d juegos, refresh=%s" % (total, args.refresh), flush=True)

    for i, rom in enumerate(roms, 1):
        base = os.path.splitext(os.path.basename(rom))[0]
        write_status("running", i - 1, total, ok, none, fail, base)

        if not args.refresh and has_data(rom):
            skipped += 1
            print("[scan] %d/%d skip %s" % (i, total, base), flush=True)
            continue
        if not args.refresh and \
           os.path.exists(os.path.join(ex.DATA_DIR, base + ".none")):
            skipped += 1
            print("[scan] %d/%d sin logros %s" % (i, total, base), flush=True)
            continue

        print("[scan] %d/%d %s" % (i, total, base), flush=True)
        cmd = [sys.executable, os.path.join(HERE, "ra_local_export.py"),
               rom, "--auto", "--force", "--token", token]
        try:
            r = subprocess.run(cmd, timeout=args.timeout,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = 124
        except Exception as e:
            print("[scan] error %s: %s" % (base, e), flush=True)
            rc = 1

        if rc == 0:
            ok += 1
        elif rc == 2:
            none += 1
        else:
            fail += 1
            print("[scan] fallo %s rc=%d" % (base, rc), flush=True)

        write_status("running", i, total, ok, none, fail, base)
        time.sleep(0.15)

    write_status("done", total, total, ok, none, fail)
    print("[scan] fin: ok=%d sin_logros=%d fallos=%d saltados=%d"
          % (ok, none, fail, skipped), flush=True)

    if total == 0:
        notify("ESCANEO DE LOGROS", "No hay juegos que escanear",
               "Nintendo DS  -  GeminusOS", 6000)
    else:
        notify("ESCANEO DE LOGROS",
               "%d juegos actualizados" % ok,
               "%d sin logros  -  %d errores  -  %d ya listos"
               % (none, fail, skipped), 7000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
