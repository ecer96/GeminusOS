#!/usr/bin/env python3
"""yt-bridge.py — puente gamepad -> mpv (IPC JSON).

El launcher de GeminusOS no está activo mientras se reproduce el vídeo, así que
este pequeño lector de /dev/input traduce las pulsaciones del mando ANBERNIC a
comandos del socket IPC de mpv.

Uso:  python3 yt-bridge.py /tmp/mpv-yt.sock
"""
import fcntl
import json
import os
import select
import socket
import struct
import sys
import time

IPC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mpv-yt.sock"
STATE = sys.argv[2] if len(sys.argv) > 2 else ""

# struct input_event en Linux x86_64/aarch64 (64-bit): long, long, u16, u16, s32
EVENT_FMT = "llHHI"
EVENT_SIZE = struct.calcsize(EVENT_FMT)

EV_KEY = 0x01
EV_ABS = 0x03

# Códigos de botón (coinciden con src/input.c del launcher)
K_A, K_B, K_Y, K_X = 0x130, 0x131, 0x132, 0x133
K_SELECT, K_START, K_MENU = 0x136, 0x137, 0x138
K_L1, K_R1 = 0x134, 0x135
K_VOL_DOWN, K_VOL_UP = 0x72, 0x73

# Ejes de cruceta (Rockchip): ABS_HAT0X / ABS_HAT0Y
ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11

EVIOCGNAME = 0x81004506  # _IOC(_IOC_READ, 'E', 0x06, 256)


def find_gamepad():
    """Devuelve el path del mando: preferimos el que se llama 'ANBERNIC'."""
    fallback = None
    for name in sorted(os.listdir("/dev/input")):
        if not name.startswith("event"):
            continue
        path = "/dev/input/" + name
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        try:
            buf = bytearray(256)
            fcntl.ioctl(fd, EVIOCGNAME, buf, True)
            devname = buf.split(b"\0", 1)[0].decode("utf-8", "replace")
        except OSError:
            os.close(fd)
            continue
        os.close(fd)
        if "ANBERNIC" in devname:
            return path
        if fallback is None and "key" in devname.lower():
            fallback = path
    return fallback


class Mpv:
    def __init__(self, path):
        self.path = path
        self.sock = None

    def _connect(self):
        if self.sock is not None:
            return True
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(self.path)
            self.sock = s
            return True
        except OSError:
            self.sock = None
            return False

    def cmd(self, *args):
        if not self._connect():
            return
        try:
            self.sock.sendall((json.dumps({"command": list(args)}) + "\n").encode())
        except OSError:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


def main():
    dev = find_gamepad()
    if not dev:
        sys.stderr.write("yt-bridge: no encontré mando\n")
        return 1
    sys.stderr.write("yt-bridge: mando=%s sock=%s\n" % (dev, IPC))

    mpv = Mpv(IPC)
    fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
    try:
        while True:
            r, _, _ = select.select([fd], [], [], 1.0)
            if not r:
                continue
            data = os.read(fd, EVENT_SIZE * 64)
            for off in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                _, _, etype, code, value = struct.unpack_from(EVENT_FMT, data, off)
                if etype == EV_KEY and value == 1:
                    if code in (K_B, K_MENU):
                        mpv.cmd("quit")
                    elif code == K_A:
                        mpv.cmd("cycle", "pause")
                    elif code in (K_Y, K_START):
                        if STATE:
                            try:
                                with open(STATE, "w") as f:
                                    f.write("next")
                            except OSError:
                                pass
                        mpv.cmd("quit")
                    elif code == K_X:
                        # X = vídeo anterior (youtube.sh lee STATE=prev).
                        if STATE:
                            try:
                                with open(STATE, "w") as f:
                                    f.write("prev")
                            except OSError:
                                pass
                        mpv.cmd("quit")
                    elif code == K_L1:
                        mpv.cmd("seek", -10, "relative")
                    elif code == K_R1:
                        mpv.cmd("seek", 10, "relative")
                    elif code == K_SELECT:
                        mpv.cmd("cycle", "mute")
                    elif code == K_VOL_DOWN:
                        mpv.cmd("add", "volume", -5)
                    elif code == K_VOL_UP:
                        mpv.cmd("add", "volume", 5)
                elif etype == EV_ABS:
                    if code == ABS_HAT0X and value != 0:
                        mpv.cmd("seek", -5 if value < 0 else 5, "relative")
                    elif code == ABS_HAT0Y and value != 0:
                        mpv.cmd("add", "volume", 2 if value < 0 else -2)
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
