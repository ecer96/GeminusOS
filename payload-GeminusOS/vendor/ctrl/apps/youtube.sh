#!/bin/sh
# youtube.sh — app de YouTube (mpv + yt-dlp) con buscador y lista en la
# pantalla de abajo (geminus-yt-panel).
#
# Flujo:
#   1. Arranca el panel inferior (barra de busqueda + resultados + controles).
#   2. El usuario busca, elige un video -> el panel escribe /tmp/yt-chosen.
#   3. Este script resuelve el stream con yt-dlp y lo reproduce con mpv.
#   4. Si en el panel se pulsa "Buscar", mpv se cierra y el panel vuelve a la
#      busqueda; al elegir otro video se reproduce el nuevo.
#
# Controles (gamepad via yt-bridge.py -> IPC de mpv):
#   A = pausa/play   B/MENU = salir   Y/START = siguiente
#   L1/R1 = -10s/+10s   D-pad = -5s/+5s / volumen

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
LOG=/tmp/youtube.log

VFMTSEL='bv*[height<=720][fps<=30][vcodec^=avc1]/bv*[height<=720][fps<=30][vcodec^=vp9]/bv*[height<=720][fps<=30]/b[height<=480]/bv*[height<=720]/bv*'
AFMTSEL='ba[acodec^=mp4a]/ba/b'

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
status() { printf '%s\n' "$*" > "$STATUS" 2>/dev/null; log "estado: $*"; }

: > "$LOG"
rm -f "$SOCK" "$STATE" "$CHOSEN"
: > "$STATE"
log "=== youtube.sh iniciado ==="

# Audio: sink del amplificador (aw883xx)
SNK=$(XDG_RUNTIME_DIR=/var/run pactl list short sinks 2>/dev/null | grep stereo-fallback | cut -f2)
if [ -n "$SNK" ]; then
    export PULSE_SINK="$SNK"
    log "PULSE_SINK=$SNK"
fi

# Panel inferior (buscador + lista + controles)
PANEL_PID=""
if [ -x "$PANEL" ]; then
    "$PANEL" --sock "$SOCK" --status "$STATUS" --parent $$ >/dev/null 2>>"$LOG" &
    PANEL_PID=$!
    log "panel inferior iniciado (pid=$PANEL_PID)"
else
    log "AVISO: no existe $PANEL"
fi

resolve() { timeout 60 "$YTDLP" --no-warnings --no-playlist -f "$1" -g "$2" 2>>"$LOG" | head -n1; }

play() {
    rm -f "$SOCK"
    local args=(--no-config --really-quiet --fullscreen --keep-open=no
                --vo="$3" --gpu-context=wayland --hwdec=auto-safe
                --force-window=yes --background-color='#0e0e14'
                --osd-level=1 --osd-duration=3000
                --input-touch=no --no-input-default-bindings
                --input-ipc-server="$SOCK" --msg-level=all=info)
    [ -n "$4" ] && args+=(--title="$4" --osd-playing-msg="$4")
    [ -n "$2" ] && args+=(--audio-file="$2")
    mpv "${args[@]}" "$1" >>"$LOG" 2>&1 &
    MPV=$!

    local waited=0
    while [ $waited -lt 40 ] && ! [ -S "$SOCK" ]; do sleep 0.1; waited=$((waited+1)); done
    if [ -S "$SOCK" ]; then
        status "Reproduciendo"
        python3 "$BRIDGE" "$SOCK" "$STATE" >>"$LOG" 2>&1 &
        BR=$!
        wait $MPV; local rc=$?
        kill "$BR" 2>/dev/null
    else
        log "mpv no creo el socket IPC en 4 s"
        wait $MPV; local rc=$?
    fi
    rm -f "$SOCK"
    return $rc
}

play_fb() {
    local t0=$(date +%s)
    play "$1" "$2" gpu "$3"
    local rc=$?
    status "Resolviendo"
    if [ $rc -ne 0 ] && [ $(( $(date +%s) - t0 )) -lt 3 ]; then
        log "vo=gpu fallo rapido, reintento con wlshm"
        play "$1" "$2" wlshm "$3"
    fi
    return 0
}

play_url() {
    local url="$1" vid aud title
    status "Resolviendo stream..."
    vid="$(resolve "$VFMTSEL" "$url")"
    if [ -z "$vid" ]; then
        status "No se pudo resolver el video"
        log "no resolvio: $url"
        return 0
    fi
    aud="$(resolve "$AFMTSEL" "$url")"
    title="$(echo "$url" | sed 's|.*[?&]v=||; s|[?&].*||')"
    : > "$STATE"
    play_fb "$vid" "$aud" "$title"
}

# ---------------------------------------------------------------- supervisor
if [ -n "$PANEL_PID" ]; then
    LAST=""
    while kill -0 "$PANEL_PID" 2>/dev/null; do
        if [ -f "$CHOSEN" ]; then
            U="$(cat "$CHOSEN" 2>/dev/null)"
            if [ -n "$U" ] && [ "$U" != "$LAST" ]; then
                LAST="$U"
                log "seleccion: $U"
                play_url "$U"
                status "Elige otro video o pulsa Buscar"
            fi
        fi
        sleep 0.2
    done
    log "panel cerrado"
else
    # Sin panel: comportamiento clasico (argumento o youtube.conf)
    TARGET="${1:-${YT_TARGET:-}}"
    if [ -z "$TARGET" ]; then
        for c in /mnt/sdcard/ecerOS/youtube.conf /mnt/sdcard/GeminusOS/youtube.conf "$CTRL/youtube.conf"; do
            [ -f "$c" ] || continue
            TARGET="$(grep -vE '^[[:space:]]*(#|$)' "$c" | head -n1)"
            [ -n "$TARGET" ] && break
        done
    fi
    [ -z "$TARGET" ] && TARGET="ytsearch10:musica"
    case "$TARGET" in
        http://*|https://*|ytsearch*) URL="$TARGET" ;;
        *) URL="ytsearch10:$TARGET" ;;
    esac
    ENTRY="$(timeout 60 "$YTDLP" --no-warnings --no-playlist --flat-playlist \
             --print "%(webpage_url)s" "$URL" 2>>"$LOG" | head -n1)"
    [ -n "$ENTRY" ] && play_url "$ENTRY"
fi

status "Cerrando..."
log "=== youtube.sh fin ==="
