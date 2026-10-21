#!/bin/bash
# Navegador para GeminusOS — motor Chromium (JS real) dentro del UI de doble pantalla.
#
# - Se lanza Chromium en modo headless (motor de render, ejecuta JavaScript).
# - Nuestro navegador (geminus-browser) muestra la página en la pantalla SUPERIOR
#   (frames por DevTools Protocol) y el panel táctil en la INFERIOR
#   (pestañas RATÓN / TECLADO, con ESPACIO y símbolos).
# - El control se envía a Chromium por CDP: clic, scroll, escribir, navegar.
#
# Página de inicio: /mnt/sdcard/GeminusOS/browser.conf (1ª línea no comentada).
#
# Controles (mando):
#   RATÓN:  D-pad cursor · A clic · B atrás · Y adelante · L1/R1 scroll
#           START recargar · SELECT teclado · MENU salir
#   TECLADO: D-pad elegir · A escribir · B borrar · Y espacio · START (Ir)
#            SELECT volver · MENU salir
#   Táctil (pantalla inferior): trackpad y teclado.

export XDG_RUNTIME_DIR=/var/run
export WAYLAND_DISPLAY=wayland-0
export SDL_VIDEODRIVER=wayland
export HOME="${HOME:-/tmp}"

CTRL=/mnt/vendor/ctrl
BIN="$CTRL/geminus-browser"
CONF=/mnt/sdcard/GeminusOS/browser.conf
LOG=/tmp/browser.log

if [ "$(date +%Y)" -lt 2024 ]; then
    command -v chronyc >/dev/null 2>&1 && chronyc makestep >>"$LOG" 2>&1
fi

RAW=""
if [ -f "$CONF" ]; then
    RAW="$(grep -vE '^[[:space:]]*(#|$)' "$CONF" | head -n1)"
fi
[ -z "$RAW" ] && RAW="https://www.google.com/"

pkill -9 -x geminus-browser 2>/dev/null
pkill -9 -f geminus-chrome 2>/dev/null
sleep 0.3

# Audio: usar el MISMO sink que los emuladores (el launcher usa este).
pactl set-default-sink alsa_output.1.stereo-fallback 2>/dev/null

echo "[$(date '+%H:%M:%S')] navegador (chromium) -> $RAW" >> "$LOG"

# Motor: Chromium con ventana real en la pantalla superior (audio nativo, sin screencast).
/usr/bin/chromium --ozone-platform=wayland --enable-features=UseOzonePlatform \
    --kiosk --no-sandbox --autoplay-policy=no-user-gesture-required \
    --touch-events=disabled \
    --remote-debugging-port=9222 --remote-allow-origins=* \
    --user-data-dir=/tmp/geminus-chrome --no-first-run --password-store=basic \
    --no-default-browser-check \
    --disable-features=Translate,MediaRouter,OptimizationHints \
    "$RAW" >/tmp/chromium.log 2>&1 &
CH=$!

for i in $(seq 1 60); do
    (echo > /dev/tcp/127.0.0.1/9222) >/dev/null 2>&1 && break
    sleep 0.25
done

# UI: panel de la pantalla inferior + control por CDP.
GEMINUS_CDP=1 GEMINUS_PANEL=1 "$BIN" "$RAW"

pkill -9 -f geminus-chrome 2>/dev/null
kill -9 $CH 2>/dev/null
echo "[$(date '+%H:%M:%S')] navegador cerrado" >> "$LOG"
