#!/bin/sh
# YouTube ligero (<1 GB RAM) para GeminusOS.
#
# Pantalla SUPERIOR: video (mpv del firmware, salida GPU/Mali).
# Pantalla INFERIOR: teclado tactil + buscador + controles (geminus-yt-panel).
#
# El mpv del firmware (0.35.1) no trae Lua/ytdl_hook, asi que yt-dlp resuelve
# los streams (H.264 <=480p + AAC) y mpv los reproduce. Se probo un mpv 0.36
# con Lua: funciona, pero sin contexto GPU en esta consola y con wlshm pierde
# ~55% de fotogramas, por eso se usa el mpv del firmware.
#
# Flujo:
#   1. Arranca el panel inferior: teclado + lista de resultados.
#   2. Al elegir un video escribe /tmp/yt-chosen.
#   3. Este script resuelve y reproduce con mpv en la pantalla de arriba.
#   4. "Buscar" cierra mpv y vuelve a la busqueda; "Salir" cierra todo.
#
# Uso:  youtube.sh [URL | "ytdl://ytsearch:consulta" | consulta]

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
CHOSEN=/tmp/yt-chosen
CONF=/mnt/sdcard/ecerOS/youtube.conf
LOG=/tmp/youtube.log

FMT='bestvideo[height<=480][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=480]+bestaudio/best'

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
status() { printf '%s\n' "$*" > "$STATUS" 2>/dev/null; log "estado: $*"; }

: > "$LOG"
rm -f "$SOCK" "$STATE" "$CHOSEN"
: > "$STATE"
log "=== youtube.sh iniciado ==="

# Audio: amplificador aw883xx via PulseAudio.
SNK=$(XDG_RUNTIME_DIR=/var/run pactl list short sinks 2>/dev/null | awk '/stereo-fallback/ {print $2; exit}')
if [ -n "$SNK" ]; then
    export PULSE_SINK="$SNK"
    log "PULSE_SINK=$SNK"
fi

resolve() {
    timeout 60 "$YTDLP" --no-warnings --no-playlist -f "$FMT" -g "$1" 2>>"$LOG" | head -n2
}

play() {
    rm -f "$SOCK"
    if [ -n "$3" ]; then
        mpv --no-config --fullscreen --fs-screen=1 \
            --vo="$2" --gpu-context=wayland --hwdec=auto-safe \
            --cache=yes --demuxer-readahead-secs=8 \
            --mute=no --volume=25 \
            --force-window=yes --osd-level=1 --osd-duration=3000 \
            --term-status-msg= \
            --input-ipc-server="$SOCK" --input-default-bindings=no \
            --title="YouTube" --audio-file="$3" "$1" >>"$LOG" 2>&1 &
    else
        mpv --no-config --fullscreen --fs-screen=1 \
            --vo="$2" --gpu-context=wayland --hwdec=auto-safe \
            --cache=yes --demuxer-readahead-secs=8 \
            --mute=no --volume=25 \
            --force-window=yes --osd-level=1 --osd-duration=3000 \
            --term-status-msg= \
            --input-ipc-server="$SOCK" --input-default-bindings=no \
            --title="YouTube" "$1" >>"$LOG" 2>&1 &
    fi
    MPV_PID=$!

    waited=0
    while [ $waited -lt 150 ] && [ ! -S "$SOCK" ] && kill -0 "$MPV_PID" 2>/dev/null; do
        sleep 0.1
        waited=$((waited+1))
    done
    if [ -S "$SOCK" ]; then
        status "Reproduciendo"
        python3 "$BRIDGE" "$SOCK" "$STATE" >/tmp/yt-bridge.log 2>&1 &
        BR=$!
        wait "$MPV_PID"
        rc=$?
        kill "$BR" 2>/dev/null
    else
        log "mpv no creo el socket IPC"
        wait "$MPV_PID"
        rc=$?
        status "No se pudo iniciar el reproductor"
    fi
    rm -f "$SOCK"
    return $rc
}

play_url() {
    log "resolver: $1"
    status "Resolviendo video..."
    RES="$(resolve "$1")"
    VID="$(printf '%s\n' "$RES" | sed -n '1p')"
    AUD="$(printf '%s\n' "$RES" | sed -n '2p')"
    if [ -z "$VID" ]; then
        status "No se pudo resolver el video"
        log "yt-dlp no devolvio stream"
        return 1
    fi

    T0=$(date +%s)
    play "$VID" gpu "$AUD"
    RC=$?
    # Si el contexto GPU falla de inmediato, reintento por software.
    if [ $RC -ne 0 ] && [ $(( $(date +%s) - T0 )) -lt 3 ]; then
        log "vo=gpu fallo rapido; reintento con wlshm"
        play "$VID" wlshm "$AUD"
    fi
    status "Elige otro video o pulsa Buscar"
}

# ---------------------------------------------------------------- supervisor
if [ -z "$1" ] && [ -x "$PANEL" ]; then
    "$PANEL" --sock "$SOCK" --status "$STATUS" --parent $$ >/dev/null 2>>"$LOG" &
    PANEL_PID=$!
    log "panel inferior iniciado (pid=$PANEL_PID)"

    LAST=""
    while kill -0 "$PANEL_PID" 2>/dev/null; do
        if [ ! -f "$CHOSEN" ]; then
            LAST=""
        else
            U="$(cat "$CHOSEN" 2>/dev/null)"
            if [ -n "$U" ] && [ "$U" != "$LAST" ]; then
                LAST="$U"
                play_url "$U"
            fi
        fi
        sleep 0.2
    done
    log "panel cerrado"
    status "Cerrando..."
else
    # Sin panel (pruebas o lanzamiento directo): argumento, config o busqueda.
    TARGET="${1:-${YT_TARGET:-}}"
    if [ -z "$TARGET" ] && [ -f "$CONF" ]; then
        TARGET="$(grep -vE '^[[:space:]]*(#|$)' "$CONF" | head -n1)"
    fi
    [ -z "$TARGET" ] && TARGET="musica"

    case "$TARGET" in
        ytdl://*)          TARGET="${TARGET#ytdl://}" ;;
    esac
    case "$TARGET" in
        http://*|https://*) URL="$TARGET" ;;
        ytsearch*:*)        URL="$(timeout 60 "$YTDLP" --no-warnings --no-playlist --flat-playlist \
                                    --print "%(webpage_url)s" "$TARGET" 2>>"$LOG" | head -n1)" ;;
        *)                  URL="$(timeout 60 "$YTDLP" --no-warnings --no-playlist --flat-playlist \
                                    --print "%(webpage_url)s" "ytsearch1:$TARGET" 2>>"$LOG" | head -n1)" ;;
    esac

    if [ -n "$URL" ]; then
        play_url "$URL"
    else
        log "no se encontro video para: $TARGET"
        status "No se encontro el video"
    fi
fi

log "=== youtube.sh fin ==="
