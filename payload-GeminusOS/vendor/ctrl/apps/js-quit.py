#!/usr/bin/env python3
# js-quit.py — cierra Chromium (modo JS del navegador) al pulsar MENU o B.
#
# Chromium en kiosco no tiene botón de cerrar, así que leemos el mando por
# /dev/input y, al pulsar MENU (0x138) o B (0x131), matamos el Chromium del
# navegador (identificado por su user-data-dir "/tmp/geminus-chrome").
#
# Uso: js-quit.py

import os
import fcntl
import struct
import time
import subprocess
import sys

EVIOCGNAME = 0x81004506  # _IOC(_IOC_READ, 'E', 0x06, 256)
EV_KEY = 1
QUIT_KEYS = {0x138, 0x131, 0x136}   # MENU, B, SELECT
FMT = 'llHHi'
SZ = struct.calcsize(FMT)


def open_pad():
    try:
        names = sorted(os.listdir('/dev/input'))
    except OSError:
        return -1
    fallback = -1
    for n in names:
        if not n.startswith('event'):
            continue
        p = '/dev/input/' + n
        try:
            fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        name = ''
        try:
            buf = bytearray(256)
            fcntl.ioctl(fd, EVIOCGNAME, buf, True)
            name = bytes(buf).split(b'\0', 1)[0].decode('utf-8', 'replace')
        except OSError:
            pass
        low = name.lower()
        if 'anbernic' in low:
            return fd
        if ('key' in low or 'gamepad' in low or 'joystick' in low) and fallback < 0:
            fallback = fd
        else:
            os.close(fd)
    return fallback


def kill_chromium():
    for pat in ('geminus-chrome',):
        subprocess.run(['pkill', '-9', '-f', pat],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    fd = open_pad()
    if fd < 0:
        return 1
    while True:
        try:
            data = os.read(fd, SZ * 32)
        except BlockingIOError:
            time.sleep(0.03)
            continue
        except OSError:
            break
        for i in range(0, len(data) - SZ + 1, SZ):
            _, _, typ, code, val = struct.unpack(FMT, data[i:i + SZ])
            if typ == EV_KEY and val == 1 and code in QUIT_KEYS:
                kill_chromium()
                return 0
        time.sleep(0.02)
    return 0


if __name__ == '__main__':
    sys.exit(main())
