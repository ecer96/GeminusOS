#!/bin/sh
# App YouTube — Chromium (web movil) en la pantalla de ARRIBA y panel de
# controles en la de ABAJO (joystick = puntero, L1/R1 = clic izq/der,
# D-pad = flechas, teclado y volumen).
#
# Uso:  youtube.sh [URL]
export XDG_RUNTIME_DIR=/var/run
export WAYLAND_DISPLAY=wayland-0
export HOME="${HOME:-/tmp}"

PROFILE=/mnt/data/chromium-yt
PANEL=/mnt/vendor/ctrl/geminus-yt-panel
URL="${1:-https://m.youtube.com}"
LOG=/tmp/youtube.log
mkdir -p "$PROFILE" 2>/dev/null

SNK=$(XDG_RUNTIME_DIR=/var/run pactl list short sinks 2>/dev/null | grep stereo-fallback | cut -f2)
[ -n "$SNK" ] && export PULSE_SINK="$SNK"
echo "[$(date '+%H:%M:%S')] youtube.sh: $URL" >> "$LOG"

chromium \
    --ozone-platform=wayland \
    --kiosk --app="$URL" \
    --user-data-dir="$PROFILE" \
    --no-first-run --no-default-browser-check \
    --disable-extensions --disable-sync --disable-translate \
    --disable-background-networking --disable-component-update \
    --disable-default-apps --disable-breakpad --disable-domain-reliability \
    --disable-client-side-phishing-detection --no-pings \
    --disable-features=Translate,MediaRouter,OptimizationHints,InterestFeedContentSuggestions,CalculateNativeWinOcclusion \
    --enable-low-end-device-mode \
    --renderer-process-limit=2 --process-per-site \
    --disk-cache-size=67108864 \
    --autoplay-policy=no-user-gesture-required \
    >>"$LOG" 2>&1 &
CH=$!

PN=""
if [ -x "$PANEL" ]; then
    "$PANEL" --web >>"$LOG" 2>&1 &
    PN=$!
    echo "[$(date '+%H:%M:%S')] panel inferior pid=$PN" >> "$LOG"
fi

wait $CH
echo "[$(date '+%H:%M:%S')] chromium termino" >> "$LOG"
[ -n "$PN" ] && kill $PN 2>/dev/null
exit 0
