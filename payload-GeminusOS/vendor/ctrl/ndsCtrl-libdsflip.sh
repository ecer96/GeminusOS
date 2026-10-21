#!/bin/bash
# ndsCtrl-libdsflip.sh v37
# v38: DSFLIP_GL=1 (shaders GLSL en GPU)
# v37: PULSE_SINK (audio, ver SINK-FIX.md), shader inject, no mata dmenu_ln
#
# Cambios respecto al v35:
#  - NO mata loadapp.sh (asi el WiFi no se cae)
#  - Solo mata dmenu.bin/dmenu_ln si estan corriendo (fallback por si acaso)
#  - NO mata ecerlauncher (se cierra solo al pulsar A)
#  - Al salir del juego: mata cualquier ecerlauncher huerfano y relanza uno limpio
#  - sleep reducidos (0.3s en lugar de 1s)
#  - Log sin 'tee' (menos E/S)

set +e

CTRL=/mnt/vendor/ctrl
LOG=$CTRL/ndsCtrl-libdsflip.log
DDIR=/mnt/vendor/deep/drastic64
MENUHOOK=$CTRL/libmenuhook.so
SHADERLIB=$CTRL/libdrastic_shader.so
RESTART_FLAG=/tmp/nds-restart
ROM="$1"

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

log "=== Inicio sesion NDS (v36) ROM=$ROM ==="

if [ -z "$ROM" ] || [ ! -f "$ROM" ]; then
    log "Uso: $0 <ruta_al_rom>"
    exit 1
fi

# === NO matar dmenu_ln ni ecerlauncher ===
# dmenu_ln (ecer-run.sh) es quien lanza este script y espera a que termine
# para relanzar el launcher. Si se mata, loadapp.sh lo reinicia y el
# launcher aparece encima del juego.
if pgrep -x dmenu.bin > /dev/null; then
    log "Matando dmenu.bin (firmware)"
    pkill -9 -x dmenu.bin
fi

sleep 0.3

cd "$DDIR" || exit 1

# === Configuracion ===
echo "calibration:gt9xx-0:0.5 0 0.5 0 1 0" > /tmp/.weston_drm.conf
echo 0 > /sys/class/anbernic_misc/tpctrl

LCDXOFF="$(cat /sys/class/anbernic_misc/lcdoff 2>/dev/null)"
if [ -n "$LCDXOFF" ] && [ "x$LCDXOFF" != "x0" ]; then
    echo 0 > /sys/class/anbernic_misc/lcdoff
    /mnt/vendor/bin/bright.dge
fi

export SDL_TOUCH_MOUSE_EVENTS="0"
export SDL_RENDER_VSYNC=0
export SDL_VIDEO_DOUBLE_BUFFER=0
export SDL_RENDER_DRIVER=opengles2
export SDL_HINT_RENDER_BATCHING=1

for cpu in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/; do
    echo schedutil > "${cpu}scaling_governor" 2>/dev/null
done
for gpu in /sys/class/devfreq/*mali*/ /sys/class/devfreq/fde60000.gpu/; do
    [ -d "$gpu" ] && echo simple_ondemand > "${gpu}governor" 2>/dev/null
done

export MENU_DISPLAY=1
export DRASTIC_SHADER="${DRASTIC_SHADER:-none}"
export DSFLIP_SHADER="${DSFLIP_SHADER:-$DRASTIC_SHADER}"
export DSFLIP_COLOR=1
# 1 = shaders GLSL en GPU (si falla cae solo al conversor CPU). 0 = solo CPU.
export DSFLIP_GL=1
rm -f /tmp/shader-inject.log

# === Lanzar DraStic ===
RUNS=0
while true; do
    rm -f "$RESTART_FLAG" /tmp/menu-cmd
    RUNS=$((RUNS + 1))
    log "Lanzando DraStic (ejecucion $RUNS)..."

    # ecer-sink-fix: DraStic usa el mismo sink que los demas emuladores (ver SINK-FIX.md)
    SNK=$(XDG_RUNTIME_DIR=/var/run pactl list short sinks 2>/dev/null | grep stereo-fallback | cut -f2)
    if [ -n "$SNK" ]; then
        export PULSE_SINK="$SNK"
        log "PULSE_SINK=$SNK"
    else
        log "AVISO: sink stereo-fallback no encontrado, audio puede no sonar"
    fi

    # Micro: asegurar que la fuente de captura no este muteada.
    pactl set-source-mute @DEFAULT_SOURCE@ 0 2>/dev/null

    PRE="./libs/libdrastouch.so"
    [ -f "$MENUHOOK" ]  && PRE="$MENUHOOK:$PRE"
    [ -f "$SHADERLIB" ] && PRE="$SHADERLIB:$PRE"
    log "LD_PRELOAD=$PRE"
    LD_PRELOAD="$PRE" \
    DSHOOK_MIC_THRESH=0.03 \
    ./drastic_oga "$1" > "${LOG}.drastic" 2>&1
    RC=$?
    log "DraStic salio con codigo: $RC"

    if [ -f "$RESTART_FLAG" ] && [ "$RUNS" -lt 20 ]; then
        rm -f "$RESTART_FLAG"
        log "Reinicio pedido desde el menu"
        continue
    fi
    break
done

rm -f "$RESTART_FLAG" /tmp/menu-cmd
echo "calibration:gt9xx-0:clear" > /tmp/.weston_drm.conf

# El launcher lo relanza dmenu_ln (ecer-run.sh) cuando este script termina.

log "=== Fin sesion NDS ==="
exit $RC