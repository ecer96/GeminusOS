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
mkdir -p "$DDIR/scripts"
export GEMINUS_NDS_ROM="$1"

# === Configuracion ===
# 3D multihilo desactivado: en esta consola a veces descoloca las pantallas.
DCFG="$DDIR/config/drastic.cfg"
if [ -f "$DCFG" ]; then
    sed -i 's/^[[:space:]]*threaded_3d[[:space:]]*=.*/threaded_3d = 0/' "$DCFG" 2>/dev/null
    grep -q '^threaded_3d' "$DCFG" || echo 'threaded_3d = 0' >> "$DCFG"
    log "threaded_3d = 0"
fi
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

# === Vigilante de power/tapa (el launcher no esta activo durante el juego) ===
PWR_WATCH=/mnt/vendor/ctrl/geminus-power-watch.py
WPID=""
if [ -f "$PWR_WATCH" ]; then
    python3 "$PWR_WATCH" --parent $$ >>"${LOG}.power" 2>&1 &
    WPID=$!
    log "power watcher iniciado (pid=$WPID)"
fi

# === Logros locales (rcheevos) ===
ACH_DIR=/mnt/data/geminus_ach
BASE=$(basename "$1"); BASE=${BASE%.*}
ACH_DEFS="$ACH_DIR/$BASE.defs"
ACH_TITLES="$ACH_DIR/$BASE.titles"
ACH_META="$ACH_DIR/$BASE.meta"
ACH_ADDRS="$ACH_DIR/$BASE.addrs"
ACH_SIG="$ACH_DIR/$BASE.sig"
ACH_KEY=/mnt/vendor/ctrl/ach.key
ACH_LUA="$DDIR/scripts/$BASE.lua"
ACH_SCAN=/mnt/vendor/ctrl/ra_local_export.py
ACH_TOAST=/mnt/vendor/ctrl/geminus-ach-toast
ACHD_PID=""

# Primer lanzamiento: descarga y firma los logros antes de arrancar DraStic.
# Si falta la firma o la clave NO se re-firman datos existentes: se vuelven a
# descargar de RetroAchievements (evita re-firmar ficheros manipulados).
NET_OK=1
if command -v ip >/dev/null 2>&1; then
    ip route 2>/dev/null | grep -q '^default ' || NET_OK=0
fi

if [ -x "$ACH_SCAN" ] && [ ! -f "$ACH_DIR/$BASE.none" ]; then
    SCAN=0
    if [ ! -f "$ACH_DEFS" ] || [ ! -f "$ACH_META" ] || [ ! -f "$ACH_ADDRS" ] || \
       [ ! -f "$ACH_LUA" ] || [ ! -f "$ACH_SIG" ] || [ ! -f "$ACH_KEY" ]; then
        SCAN=1
    fi
    if [ "$SCAN" = "1" ] && { [ "$NET_OK" = "0" ] || \
       [ ! -f /mnt/sdcard/GeminusOS/retroachievements.cfg ]; }; then
        log "sin red o sin config RA: se omite el escaneo automatico"
        SCAN=0
    fi
    if [ "$SCAN" != "0" ]; then
        SPID=""
        if [ -x "$ACH_TOAST" ]; then
            "$ACH_TOAST" --label="PREPARANDO LOGROS" \
                --title="Buscando logros..." --duration=90000 >/dev/null 2>&1 &
            SPID=$!
        fi
        log "escaneo automatico de logros (primera vez / reparacion)"
        timeout 45 python3 "$ACH_SCAN" "$1" --auto --force >>"$LOG" 2>&1
        SRC=$?
        [ -n "$SPID" ] && kill "$SPID" 2>/dev/null
        log "escaneo/firma de logros rc=$SRC"
    fi
fi

rm -f /tmp/geminus_ach_snap.txt*
if [ -x /mnt/vendor/ctrl/geminus-achd ] && [ -f "$ACH_DEFS" ] && [ -f "$ACH_ADDRS" ]; then
    ACH_ARGS=(--defs "$ACH_DEFS" --titles "$ACH_TITLES")
    [ -f "$ACH_META" ] && ACH_ARGS+=(--meta "$ACH_META")
    /mnt/vendor/ctrl/geminus-achd "${ACH_ARGS[@]}" \
        --addrs "$ACH_ADDRS" --script "$ACH_LUA" \
        --snap /tmp/geminus_ach_snap.txt \
        --events /tmp/geminus_ach_events --tsv /mnt/data/geminus_local_ach.tsv \
        --emu-rom "$1" --parent $$ >>"$LOG" 2>&1 &
    ACHD_PID=$!
    log "achd iniciado (pid=$ACHD_PID)"
fi

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
    # DSHOOK_MIC_LIVE=1: libmenuhook entrega el micro real a DraStic.
    # (No definimos DSHOOK_MIC_THRESH: eso activaria el micro duplicado de
    #  libdrastouch y ambas inyecciones se pelearian.)
    LD_PRELOAD="$PRE" \
    DSHOOK_MIC_LIVE=1 \
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

if [ -n "$ACHD_PID" ]; then
    kill "$ACHD_PID" 2>/dev/null
    wait "$ACHD_PID" 2>/dev/null
    log "achd detenido"
fi

if [ -n "$WPID" ]; then
    kill "$WPID" 2>/dev/null
    wait "$WPID" 2>/dev/null
    log "power watcher detenido"
fi

rm -f "$RESTART_FLAG" /tmp/menu-cmd
echo "calibration:gt9xx-0:clear" > /tmp/.weston_drm.conf

# El launcher lo relanza dmenu_ln (ecer-run.sh) cuando este script termina.

log "=== Fin sesion NDS ==="
exit $RC