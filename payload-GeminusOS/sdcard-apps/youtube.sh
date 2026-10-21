#!/bin/bash
# YouTube para GeminusOS — yt-dlp (resuelve streams) + mpv (reproduce)
#
# Se lanza desde la tab "Apps" del launcher (EMU_SCRIPT).
#
# Objetivo (página/vídeo/búsqueda), en este orden:
#   1. variable de entorno YT_TARGET (útil para pruebas)
#   2. /mnt/sdcard/ecerOS/youtube.conf      <- ruta actual en la consola
#   3. /mnt/sdcard/GeminusOS/youtube.conf   <- ruta antigua (compatibilidad)
#   4. /mnt/vendor/ctrl/youtube.conf
# Primera línea no vacía y no comentada. Puede ser:
#   - una URL:    https://www.youtube.com/watch?v=... | /playlist?list=... | /@canal
#   - una búsqueda: musica relajante
#   - formateado:  ytsearch10:musica
# Si no hay configuración se usa DEFAULT_TARGET (abajo), NO el antiguo lofi.
#
# Pantalla inferior: se lanza geminus-yt-panel (apps/yt-panel.c) al instante,
# con botones grandes Play/Pausa, Atrás/Adelante ±10 s, Vol-/Vol+ y Salir.
# El panel envía los comandos al mismo socket IPC de mpv que yt-bridge.py.
#
# Controles (gamepad, vía yt-bridge.py -> mpv IPC):
#   A = pausa/play     B o MENU = salir      Y o START = siguiente
#   L1/R1 = -10s/+10s  D-pad izq/der = -5s/+5s   D-pad arr/aba = volumen

export XDG_RUNTIME_DIR=/var/run
export WAYLAND_DISPLAY=wayland-0
export SDL_VIDEODRIVER=wayland
export HOME="${HOME:-/tmp}"

CTRL=/mnt/vendor/ctrl
YTDLP="$CTRL/yt-dlp"
BRIDGE="$CTRL/yt-bridge.py"
PANEL="$CTRL/geminus-yt-panel"
SOCK=/tmp/mpv-yt.sock
STATE=/tmp/mpv-yt.state
STATUS=/tmp/mpv-yt.status
LOG=/tmp/youtube.log
PANEL_LOG=/tmp/yt-panel.log

# Objetivo por defecto cuando no hay ningún youtube.conf. Cámbialo aquí o,
# mejor, crea /mnt/sdcard/ecerOS/youtube.conf con la URL/búsqueda que quieras.
DEFAULT_TARGET="ytsearch10:musica"

# Preferimos H.264/VP9 720p a <=30 fps; si no, 480p. (No hay /dev/video*, así
# que la decodificación es por software: importa el tamaño y los fps.)
VFMTSEL='bv*[height<=720][fps<=30][vcodec^=avc1]/bv*[height<=720][fps<=30][vcodec^=vp9]/bv*[height<=720][fps<=30]/b[height<=480]/bv*[height<=720]/bv*'
AFMTSEL='ba[acodec^=mp4a]/ba/b'

T0=$(date +%s)
log() { echo "[$(date '+%H:%M:%S') +$(( $(date +%s) - T0 ))s] $*" >> "$LOG"; }

# Estado visible en el panel inferior (y en el log).
status() {
    printf '%s\n' "$*" > "$STATUS"
    log "estado: $*"
}

PANEL_PID=""
cleanup() {
    if [ -n "$PANEL_PID" ]; then
        kill "$PANEL_PID" 2>/dev/null
        wait "$PANEL_PID" 2>/dev/null
        PANEL_PID=""
    fi
    rm -f "$SOCK"
}
trap cleanup EXIT INT TERM

if ! command -v timeout >/dev/null 2>&1; then
    timeout() { shift; "$@"; }
fi

: > "$LOG"
: > "$STATE"
status "Iniciando YouTube..."
log "=== youtube.sh iniciado ==="

# 0) Panel táctil de la pantalla inferior: se abre YA, antes de la red, para
#    que no haya pantalla negra mientras yt-dlp resuelve.
if [ -x "$PANEL" ]; then
    setsid "$PANEL" --sock "$SOCK" --status "$STATUS" --parent $$ \
        </dev/null >>"$PANEL_LOG" 2>&1 &
    PANEL_PID=$!
    log "panel inferior iniciado (pid=$PANEL_PID)"
else
    log "AVISO: no existe $PANEL; seguimos sin panel inferior"
fi

# 1) Reloj correcto (TLS). El RTC suele venir bien; forzamos el step por si acaso.
if [ "$(date +%Y)" -lt 2024 ]; then
    command -v chronyc >/dev/null 2>&1 && chronyc makestep >>"$LOG" 2>&1
fi

# 2) Objetivo: config actual, config antigua y respaldo neutro.
TARGET="${YT_TARGET:-}"
CONF_USED=""
if [ -z "$TARGET" ]; then
    for c in /mnt/sdcard/ecerOS/youtube.conf \
             /mnt/sdcard/GeminusOS/youtube.conf \
             /mnt/vendor/ctrl/youtube.conf; do
        if [ -f "$c" ]; then
            TARGET="$(grep -vE '^[[:space:]]*(#|$)' "$c" | head -n1)"
            if [ -n "$TARGET" ]; then
                CONF_USED="$c"
                break
            fi
        fi
    done
fi
if [ -n "$TARGET" ]; then
    log "objetivo de ${CONF_USED:-YT_TARGET}: $TARGET"
else
    TARGET="$DEFAULT_TARGET"
    log "sin youtube.conf utilizable; objetivo por defecto: $TARGET"
fi
status "Objetivo: $TARGET"

case "$TARGET" in
    http://*|https://*|ytsearch*) URL="$TARGET" ;;
    *)                            URL="ytsearch10:$TARGET" ;;
esac
log "URL resuelta a: $URL"

resolve() { timeout 60 "$YTDLP" --no-warnings --no-playlist -f "$1" -g "$2" 2>>"$LOG" | head -n1; }

# Reproduce un par de URLs (vídeo [+ audio]) con mpv. $1=vid $2=aud $3=vo $4=título
play() {
    rm -f "$SOCK"
    local args=(--no-config --really-quiet --fullscreen --keep-open=no
                --vo="$3" --gpu-context=wayland --hwdec=auto-safe
                --force-window=yes --background-color='#0e0e14'
                --osd-level=1 --osd-duration=3000
                --input-ipc-server="$SOCK" --msg-level=all=info)
    [ -n "$4" ] && args+=(--title="$4" --osd-playing-msg="$4")
    [ -n "$2" ] && args+=(--audio-file="$2")
    mpv "${args[@]}" "$1" >>"$LOG" 2>&1 &
    MPV=$!

    local waited=0
    while [ $waited -lt 40 ] && ! [ -S "$SOCK" ]; do sleep 0.1; waited=$((waited+1)); done
    if [ -S "$SOCK" ]; then
        status "Reproduciendo: ${4:-$1}"
        log "mpv listo en ${waited}00 ms"
        python3 "$BRIDGE" "$SOCK" "$STATE" >>"$LOG" 2>&1 &
        BR=$!
        wait $MPV; local rc=$?
        kill "$BR" 2>/dev/null
    else
        log "mpv no creó el socket IPC en 4 s"
        status "Reproductor no disponible"
        wait $MPV; local rc=$?
    fi
    rm -f "$SOCK"
    return $rc
}

play_fb() {
    local t0=$(date +%s)
    play "$1" "$2" gpu "$3"
    local rc=$?
    if [ $rc -ne 0 ] && [ $(( $(date +%s) - t0 )) -lt 3 ]; then
        log "vo=gpu falló rápido, reintento con wlshm"
        play "$1" "$2" wlshm "$3"
    fi
    return 0
}

# 3) Lista de entradas (vídeo suelto, playlist, canal o búsqueda).
#    Pedimos URL y título en la misma pasada (sin una segunda llamada de red).
status "Buscando en YouTube..."
log "listando entradas de $URL"
mapfile -t ENTRIES < <(timeout 90 "$YTDLP" --no-warnings --flat-playlist \
        --print "%(webpage_url)s|%(title)s" "$URL" 2>>"$LOG")
NM=${#ENTRIES[@]}
if [ "$NM" -eq 0 ]; then
    log "sin entradas (¿red, hora o URL?)"
    status "Error: sin resultados (revisa red/hora/URL)"
    sleep 5
    exit 0
fi
log "entradas: $NM"
status "$NM vídeos encontrados"

idx=0
while [ $idx -lt $NM ]; do
    line="${ENTRIES[$idx]}"
    [ -z "$line" ] && { idx=$((idx+1)); continue; }
    ENTRY="${line%%|*}"
    TITLE="${line#*|}"
    [ "$TITLE" = "$line" ] && TITLE="$ENTRY"
    [ -z "$ENTRY" ] && { idx=$((idx+1)); continue; }
    log "[$((idx+1))/$NM] $TITLE"

    status "Resolviendo stream $((idx+1))/$NM: $TITLE"
    VID="$(resolve "$VFMTSEL" "$ENTRY")"
    if [ -z "$VID" ]; then
        log "no resolvió vídeo; siguiente"
        status "No se pudo resolver el vídeo; probando el siguiente..."
        idx=$((idx+1)); continue
    fi
    AUD="$(resolve "$AFMTSEL" "$ENTRY")"

    : > "$STATE"
    play_fb "$VID" "$AUD" "$TITLE"
    act="$(cat "$STATE" 2>/dev/null)"
    case "$act" in
        next) idx=$((idx+1)); continue ;;
        prev) [ $idx -gt 0 ] && idx=$((idx-1)); continue ;;
        quit) break ;;
        *) break ;;
    esac
done

status "Cerrando..."
log "=== youtube.sh fin ==="
