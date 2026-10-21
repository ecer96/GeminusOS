#!/bin/sh
# mtp-watch.sh — activa MTP automáticamente cuando el USB entra en modo
# dispositivo (cable a un PC). Se lanza desde el launcher al activar MTP.
#
# Evita duplicados con un archivo PID y reintenta mientras el puerto no esté
# listo. CPU despreciable (duerme 2 s por vuelta).

LOCK=/tmp/mtp-watch.pid
LOG=/tmp/usb-mtp.log

if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
    exit 0   # ya hay un watcher
fi
echo $$ > "$LOCK"

cleanup() { rm -f "$LOCK"; }
trap cleanup EXIT INT TERM

while true; do
    dev=0
    for f in /sys/class/extcon/*/state; do
        [ -f "$f" ] || continue
        if grep -q '^USB=1' "$f" 2>/dev/null; then dev=1; break; fi
    done

    if [ "$dev" = 1 ]; then
        if ! pgrep -x umtprd >/dev/null 2>&1; then
            [ -x /usr/bin/usb-mtp-on.sh ] && /usr/bin/usb-mtp-on.sh >>"$LOG" 2>&1
        fi
    fi
    sleep 2
done
