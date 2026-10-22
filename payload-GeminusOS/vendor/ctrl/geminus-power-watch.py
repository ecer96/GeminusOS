#!/usr/bin/env python3
"""Vigila el botón power y la tapa (Hall) durante una sesión de DraStic.

La launcher maneja ambos, pero cuando DraStic está abierto el launcher no
existe. Este proceso hace lo mismo que power.c: lanza pwr_new.sh (suspend).

Uso:
  geminus-power-watch.py [--parent PID] [--dry-run]
"""
import argparse
import os
import select
import struct
import subprocess
import sys
import time

PWR_DEV = "/dev/input/event0"
HALL = "/sys/class/anbernic_misc/hallkey"
PWR_SCRIPT = "/mnt/vendor/ctrl/pwr_new.sh"
LOG = "/tmp/geminus-power-watch.log"
HALL_CLOSED = 2
DEBOUNCE = 3


def log(msg):
    with open(LOG, "a") as f:
        f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))


def hall_raw():
    try:
        with open(HALL) as f:
            return int(f.read().strip())
    except Exception:
        return -1


def parent_alive(pid):
    if not pid:
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def suspend(dry):
    if dry:
        log("dry-run: suspend")
        return
    log("suspend")
    try:
        subprocess.run([PWR_SCRIPT], check=False)
    except Exception as e:
        log("error suspend: %s" % e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    log("inicio (parent=%d dry=%d)" % (args.parent, args.dry_run))
    try:
        fd = os.open(PWR_DEV, os.O_RDONLY | os.O_NONBLOCK)
    except OSError as e:
        log("no abrir %s: %s" % (PWR_DEV, e))
        return 1

    closed = 0
    last_hall = -1
    last_poll = 0.0

    while True:
        if not parent_alive(args.parent):
            log("padre terminado")
            break

        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            try:
                data = os.read(fd, 24 * 32)
            except BlockingIOError:
                data = b""
            off = 0
            while off + 24 <= len(data):
                _sec, _usec, typ, code, val = struct.unpack_from("llHHi", data, off)
                off += 24
                if typ == 1 and code == 116 and val == 1:   # KEY_POWER press
                    suspend(args.dry_run)

        now = time.time()
        if now - last_poll >= 0.5:
            last_poll = now
            v = hall_raw()
            if v != last_hall:
                log("hall %s -> %s" % (last_hall, v))
                last_hall = v
                if v == HALL_CLOSED:
                    closed = 1
                else:
                    closed = 0
            elif v == HALL_CLOSED:
                closed += 1
                if closed == DEBOUNCE:
                    log("tapa cerrada confirmada")
                    suspend(args.dry_run)
            else:
                closed = 0

    os.close(fd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
