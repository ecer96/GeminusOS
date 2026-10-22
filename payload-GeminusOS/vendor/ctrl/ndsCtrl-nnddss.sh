#!/bin/bash
# ndsCtrl-nnddss.sh — lanza NNDDSS con el mismo flujo que DraStic.
# El launcher ya se cierra antes de ejecutar este wrapper; al salir,
# geminus-run.sh relanza el launcher.
set +e

CTRL=/mnt/vendor/ctrl
NDIR=/mnt/vendor/deep/nnddss
DDIR=/mnt/vendor/deep/drastic64
LOG=$CTRL/ndsCtrl-nnddss.log
ROM="$1"
ACHD_PID=""

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

cleanup() {
    if [ -n "$ACHD_PID" ]; then
        kill "$ACHD_PID" 2>/dev/null
        wait "$ACHD_PID" 2>/dev/null
        log "achd detenido"
        ACHD_PID=""
    fi
    echo "calibration:gt9xx-0:clear" > /tmp/.weston_drm.conf 2>/dev/null
    for cpu in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/; do
        echo schedutil > "${cpu}scaling_governor" 2>/dev/null
    done
}

trap cleanup EXIT

log "=== Inicio sesion NNDDSS ROM=$ROM ==="

if [ -z "$ROM" ] || [ ! -f "$ROM" ]; then
    log "Uso: $0 <ruta_al_rom>"
    exit 1
fi
if [ ! -x "$NDIR/nnddss" ]; then
    log "ERROR: no existe $NDIR/nnddss"
    exit 1
fi

if pgrep -x dmenu.bin > /dev/null; then
    log "Matando dmenu.bin (firmware)"
    pkill -9 -x dmenu.bin
fi
sleep 0.3

cd "$NDIR" || exit 1

# Pantalla tactil / calibracion, igual que el wrapper de DraStic.
echo "calibration:gt9xx-0:0.5 0 0.5 0 1 0" > /tmp/.weston_drm.conf
echo 0 > /sys/class/anbernic_misc/tpctrl

LCDXOFF="$(cat /sys/class/anbernic_misc/lcdoff 2>/dev/null)"
if [ -n "$LCDXOFF" ] && [ "x$LCDXOFF" != "x0" ]; then
    echo 0 > /sys/class/anbernic_misc/lcdoff
    /mnt/vendor/bin/bright.dge
fi

export XDG_RUNTIME_DIR=/var/run
export WAYLAND_DISPLAY=wayland-0
export SDL_VIDEODRIVER=wayland
export SDL_RENDER_VSYNC=0
export SDL_VIDEO_DOUBLE_BUFFER=0
export SDL_TOUCH_MOUSE_EVENTS="0"

for cpu in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/; do
    echo performance > "${cpu}scaling_governor" 2>/dev/null
done
for gpu in /sys/class/devfreq/*mali*/ /sys/class/devfreq/fde60000.gpu/; do
    [ -d "$gpu" ] && echo performance > "${gpu}governor" 2>/dev/null
done

# El sink audible de la consola es stereo-fallback (aw883xx).
SNK=$(XDG_RUNTIME_DIR=/var/run pactl list short sinks 2>/dev/null | grep stereo-fallback | cut -f2)
if [ -n "$SNK" ]; then
    export PULSE_SINK="$SNK"
    XDG_RUNTIME_DIR=/var/run pactl set-default-sink "$SNK" 2>/dev/null
    log "AUDIO PULSE_SINK=$SNK"
fi
pactl set-source-mute @DEFAULT_SOURCE@ 0 2>/dev/null

# === Logros locales (rcheevos) ===
# Mismos datos/firma/TSV/toast que DraStic. El unico cambio es el lector de
# memoria: NNDDSS usa su propio motor Lua, pero la API
# drastic.get_ds_memory_arm9_32 es la misma. libnnddss_ach.so activa el flag
# interno que permite cargar scripts/<rom>.lua (ver nnddss-ach-preload.c).
ACH_DIR=/mnt/data/geminus_ach
BASE=$(basename "$ROM"); BASE=${BASE%.*}
ACH_DEFS="$ACH_DIR/$BASE.defs"
ACH_TITLES="$ACH_DIR/$BASE.titles"
ACH_META="$ACH_DIR/$BASE.meta"
ACH_ADDRS="$ACH_DIR/$BASE.addrs"
ACH_SIG="$ACH_DIR/$BASE.sig"
ACH_KEY=$CTRL/ach.key
ACH_LUA_DR="$DDIR/scripts/$BASE.lua"
ND_SCRIPTS="$NDIR/User/scripts"
ND_SCRIPTS_ALT="$NDIR/scripts"
ACH_LUA_ND="$ND_SCRIPTS/$BASE.lua"
ACH_SCAN=$CTRL/ra_local_export.py
ACH_TOAST=$CTRL/geminus-ach-toast
ACH_PRELOAD=$CTRL/libnnddss_ach.so
ACH_DEFAULT=$CTRL/nds_ach_default.lua

export GEMINUS_NDS_ROM="$ROM"

NET_OK=1
if command -v ip >/dev/null 2>&1; then
    ip route 2>/dev/null | grep -q '^default ' || NET_OK=0
fi

if [ -x "$ACH_SCAN" ] && [ ! -f "$ACH_DIR/$BASE.none" ]; then
    SCAN=0
    if [ ! -f "$ACH_DEFS" ] || [ ! -f "$ACH_META" ] || [ ! -f "$ACH_ADDRS" ] || \
       [ ! -f "$ACH_LUA_DR" ] || [ ! -f "$ACH_SIG" ] || [ ! -f "$ACH_KEY" ]; then
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
        timeout 45 python3 "$ACH_SCAN" "$ROM" --auto --force >>"$LOG" 2>&1
        SRC=$?
        [ -n "$SPID" ] && kill "$SPID" 2>/dev/null
        log "escaneo/firma de logros rc=$SRC"
    fi
fi

# Copia el script firmado de DraStic al arbol de NNDDSS. La firma HMAC cubre
# nombre base + contenido, no la ruta, asi que el mismo .lua sigue siendo
# valido para geminus-achd desde cualquiera de las dos carpetas.
prepare_nd_scripts() {
    mkdir -p "$ND_SCRIPTS" "$ND_SCRIPTS_ALT" 2>/dev/null
    if [ -f "$ACH_LUA_DR" ]; then
        for dst in "$ND_SCRIPTS/$BASE.lua" "$ND_SCRIPTS_ALT/$BASE.lua"; do
            # El script de DraStic es la fuente de verdad y se regenera al
            # escanear; NNDDSS debe usar exactamente el mismo.
            cp -f "$ACH_LUA_DR" "$dst" 2>/dev/null
            chmod 600 "$dst" 2>/dev/null
        done
        log "scripts NNDDSS actualizados desde $ACH_LUA_DR"
    fi
    # Respaldo generico: solo se instala si no hay un default.lua ajeno.
    if [ -f "$ACH_DEFAULT" ]; then
        for dst in "$ND_SCRIPTS/default.lua" "$ND_SCRIPTS_ALT/default.lua"; do
            if [ ! -f "$dst" ] || grep -q 'GEMINUSOS_ACH_DEFAULT' "$dst" 2>/dev/null; then
                cp -f "$ACH_DEFAULT" "$dst" 2>/dev/null
                chmod 600 "$dst" 2>/dev/null
            else
                log "default.lua existente ajeno, se respeta: $dst"
            fi
        done
    fi
}
prepare_nd_scripts

rm -f /tmp/geminus_ach_snap.txt*
# Se verifica preferentemente el script firmado de DraStic; si no existe,
# el copiado a NNDDSS conserva nombre base y contenido.
ACH_LUA="$ACH_LUA_DR"
[ -f "$ACH_LUA" ] || ACH_LUA="$ACH_LUA_ND"
[ -f "$ACH_LUA" ] || ACH_LUA="$ND_SCRIPTS_ALT/$BASE.lua"
if [ -x "$CTRL/geminus-achd" ] && [ -f "$ACH_DEFS" ] && [ -f "$ACH_ADDRS" ] && \
   [ -f "$ACH_LUA" ]; then
    ACH_ARGS=(--defs "$ACH_DEFS" --titles "$ACH_TITLES")
    [ -f "$ACH_META" ] && ACH_ARGS+=(--meta "$ACH_META")
    "$CTRL/geminus-achd" "${ACH_ARGS[@]}" \
        --addrs "$ACH_ADDRS" --script "$ACH_LUA" \
        --snap /tmp/geminus_ach_snap.txt \
        --events /tmp/geminus_ach_events --tsv /mnt/data/geminus_local_ach.tsv \
        --emu-rom "$ROM" --parent $$ >>"$LOG" 2>&1 &
    ACHD_PID=$!
    log "achd iniciado (pid=$ACHD_PID, lua=$ACH_LUA)"
else
    log "logros: sin datos firmados para $BASE"
fi

# NNDDSS deja el flag de scripts Lua a cero; este preload lo activa sin
# modificar el core. Si el fichero no existe, NNDDSS arranca igual.
if [ -f "$ACH_PRELOAD" ]; then
    export LD_PRELOAD="$ACH_PRELOAD${LD_PRELOAD:+:$LD_PRELOAD}"
    log "LD_PRELOAD=$LD_PRELOAD"
fi

# El core de NNDDSS trae el flag Lua a cero y no carga scripts/<rom>.lua.
# Parcheamos la comprobacion cbz de FUN_00175c00 (offset 0x75d98) a NOP.
# Se hace una copia .pre-ach y solo si los bytes son los esperados.
patch_nnddss_core() {
    local lib="$NDIR/lib/libnnddss.so"
    [ -f "$lib" ] || return 0
    if [ ! -f "$lib.pre-ach" ]; then
        cp -f "$lib" "$lib.pre-ach"
        log "backup core NNDDSS: $lib.pre-ach"
    fi
    python3 - "$lib" <<'PYEOF'
import sys
p=sys.argv[1]
d=bytearray(open(p,'rb').read())
off=0x75d98
if len(d) < off+4:
    print("patch: core corto"); sys.exit(0)
if d[off:off+4] == bytes.fromhex("1f2003d5"):
    print("patch: ya aplicado"); sys.exit(0)
if d[off:off+4] != bytes.fromhex("68040034"):
    print("patch: bytes inesperados "+d[off:off+4].hex()); sys.exit(0)
d[off:off+4]=bytes.fromhex("1f2003d5")
open(p,'wb').write(d)
print("patch: NOP aplicado")
PYEOF
}
patch_nnddss_core >>"$LOG" 2>&1

log "Lanzando NNDDSS..."
# launch.sh hace el enlace de saves y termina con exec; lo ejecutamos como
# hijo para poder restaurar la calibracion al volver.
bash "$NDIR/launch.sh" "$ROM" >> "$LOG" 2>&1
RC=$?

log "NNDDSS salio con codigo: $RC"
log "=== Fin sesion NNDDSS ==="
exit $RC
