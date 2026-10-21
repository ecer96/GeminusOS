#!/bin/sh
# GeminusOS: pide IP por DHCP en wlan0 cuando esta asociada y no tiene direccion.
# Necesario porque NetworkManager no gestiona wlan0 y wpa_supplicant solo asocia.
LOCK=/tmp/wifi-dhcp.pid
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
    exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

have_ip() { ip -4 addr show wlan0 2>/dev/null | grep -q "inet "; }
assoc() {
    [ "$(cat /sys/class/net/wlan0/operstate 2>/dev/null)" = "up" ] && return 0
    wpa_cli -i wlan0 status 2>/dev/null | grep -q "wpa_state=COMPLETED"
}

while true; do
    if ! have_ip && assoc; then
        timeout 20 udhcpc -i wlan0 -q -n -t 4 -T 3 >/dev/null 2>&1
    fi
    sleep 5
done
