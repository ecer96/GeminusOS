#!/bin/bash
# Reproducir vídeos (mp4, mkv, mov, avi, webm...) desde una carpeta de la microSD.
#
# Se lanza desde la tab "Apps" del launcher (EMU_SCRIPT).
# Carpeta a explorar (una línea):
#   /mnt/sdcard/GeminusOS/media.conf     -> por defecto /mnt/sdcard/media
#
# Reproduce todos los vídeos encontrados (recursivo) en orden alfabético.
# Controles (gamepad, vía yt-bridge.py -> mpv IPC):
#   A = pausa/play   B o MENU = salir   Y o START = siguiente
#   L1/R1 = -10s/+10s   D-pad izq/der = -5s/+5s   D-pad arr/aba = volumen

export XDG_RUNTIME_DIR=/var/run
export WAYLAND_DISPLAY=wayland-0
export SDL_VIDEODRIVER=wayland
export HOME="${HOME:-/tmp}"

CTRL=/mnt/vendor/ctrl
BRIDGE="$CTRL/yt-bridge.py"
CONF=/mnt/sdcard/GeminusOS/media.conf
SOCK=/tmp/mpv-media.sock
STATE=/tmp/mpv-media.state
LOG=/tmp/media.log

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
: > "$LOG"
: > "$STATE"
log "=== media.sh iniciado ==="

# Audio por el mismo sink que los emuladores.
pactl set-default-sink alsa_output.1.stereo-fallback 2>/dev/null

# Reloj correcto (por si acaso).
if [ "$(date +%Y)" -lt 2024 ]; then
    command -v chronyc >/dev/null 2>&1 && chronyc makestep >>"$LOG" 2>&1
fi

DIR=/mnt/sdcard/media
if [ -f "$CONF" ]; then
    L="$(grep -vE '^[[:space:]]*(#|$)' "$CONF" | head -n1)"
    [ -n "$L" ] && DIR="$L"
fi
log "carpeta: $DIR"
if [ ! -d "$DIR" ]; then log "no existe la carpeta"; exit 0; fi

mapfile -t FILES < <(find "$DIR" -type f \
    \( -iname '*.mp4' -o -iname '*.mkv' -o -iname '*.mov' -o -iname '*.avi' \
       -o -iname '*.webm' -o -iname '*.m4v' -o -iname '*.ts' -o -iname '*.mpg' \) \
    2>/dev/null | sort)
NM=${#FILES[@]}
log "vídeos: $NM"
[ "$NM" -eq 0 ] && exit 0

play() {
    local f="$1"
    rm -f "$SOCK"
    local args=(--no-config --fullscreen --keep-open=no
                --vo=gpu --gpu-context=wayland --hwdec=auto-safe
                --input-ipc-server="$SOCK" --msg-level=all=info
                --osd-level=1 --force-window=yes
                --osd-playing-msg="${f##*/}")
    mpv "${args[@]}" "$f" >>"$LOG" 2>&1 &
    MPV=$!
    local waited=0
    while [ $waited -lt 40 ] && ! [ -S "$SOCK" ]; do sleep 0.1; waited=$((waited+1)); done
    if [ -S "$SOCK" ]; then
        python3 "$BRIDGE" "$SOCK" "$STATE" >>"$LOG" 2>&1 &
        BR=$!
        wait $MPV; local rc=$?
        kill "$BR" 2>/dev/null
    else
        wait $MPV; local rc=$?
    fi
    rm -f "$SOCK"
    return $rc
}

idx=0
while [ $idx -lt $NM ]; do
    f="${FILES[$idx]}"
    log "[$((idx+1))/$NM] $f"
    : > "$STATE"
    play "$f"
    act="$(cat "$STATE" 2>/dev/null)"
    case "$act" in
        next) idx=$((idx+1)) ;;
        prev) [ $idx -gt 0 ] && idx=$((idx-1)) ;;
        *) break ;;
    esac
done

log "=== media.sh fin ==="
