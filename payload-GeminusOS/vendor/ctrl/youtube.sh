#!/bin/sh
# YouTube ligero para consola <1 GB RAM.
# Acepta la misma entrada que mpv-ytdl: ytdl://ytsearch:consulta, pero el
# mpv del firmware no trae Lua/ytdl_hook. Por eso yt-dlp resuelve el stream
# (video H.264 <=480p + audio) y mpv recibe ambas URLs directamente.
#
# Uso: youtube.sh 'ytdl://ytsearch:digimon openings'
#      o escribir la busqueda en /mnt/sdcard/ecerOS/youtube.conf

export XDG_RUNTIME_DIR=/var/run
export WAYLAND_DISPLAY=wayland-0
export HOME="${HOME:-/tmp}"

CTRL=/mnt/vendor/ctrl
YTDLP="$CTRL/yt-dlp"
CONF=/mnt/sdcard/ecerOS/youtube.conf
LOG=/tmp/youtube.log

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
: > "$LOG"
log "youtube mpv-ytdl: inicio"

# Limpiar solo procesos huerfanos de sesiones anteriores; no tocar Weston ni launcher.
for p in $(ps -o pid,comm | awk '$2 ~ /geminus-yt-pane|mpv/ {print $1}'); do
    kill -9 "$p" 2>/dev/null
done

TARGET="${1:-${YT_TARGET:-}}"
if [ -z "$TARGET" ] && [ -f "$CONF" ]; then
    TARGET="$(grep -vE '^[[:space:]]*(#|$)' "$CONF" | head -n1)"
fi
if [ -z "$TARGET" ]; then
    log "sin consulta; configura $CONF o pasa youtube.sh 'ytdl://ytsearch:consulta'"
    exit 2
fi

# Compatible con las URIs indicadas: mpv "ytdl://ytsearch:QUERY".
case "$TARGET" in ytdl://*) TARGET="${TARGET#ytdl://}" ;; esac
case "$TARGET" in
    http://*|https://*) URL="$TARGET" ;;
    ytsearch*:* )       URL="$TARGET" ;;
    *)                  URL="ytsearch1:$TARGET" ;;
esac
log "consulta: $URL"

# Seleccion baja en RAM y decodificable por el SoC: H.264 <=480p + AAC.
FMT='bestvideo[height<=480][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=480]+bestaudio/best'
printf '%s\n' "Buscando: $URL" > /tmp/youtube-status
RES="$(timeout 55 "$YTDLP" --no-warnings --no-playlist --format "$FMT" --get-url "$URL" 2>>"$LOG")"
VID="$(printf '%s\n' "$RES" | sed -n '1p')"
AUD="$(printf '%s\n' "$RES" | sed -n '2p')"
if [ -z "$VID" ]; then
    log "yt-dlp no encontro un stream"
    printf '%s\n' "No se encontro video; revisa la busqueda/conexion" > /tmp/youtube-status
    exit 1
fi
log "stream resuelto (audio separado: $([ -n "$AUD" ] && echo si || echo no))"
printf '%s\n' "Reproduciendo" > /tmp/youtube-status

# Audio por PulseAudio (sink del amplificador); imagen en salida superior.
SNK=$(XDG_RUNTIME_DIR=/var/run pactl list short sinks 2>/dev/null | awk '/stereo-fallback/ {print $2; exit}')
[ -n "$SNK" ] && export PULSE_SINK="$SNK"
if [ -n "$AUD" ]; then
    exec mpv --no-config --fullscreen --fs-screen=0 --keep-open=no \
        --hwdec=auto-safe --vo=gpu --gpu-context=wayland \
        --cache=yes --demuxer-readahead-secs=8 --mute=yes \
        --audio-file="$AUD" --title="YouTube" "$VID"
else
    exec mpv --no-config --fullscreen --fs-screen=0 --keep-open=no \
        --hwdec=auto-safe --vo=gpu --gpu-context=wayland \
        --cache=yes --demuxer-readahead-secs=8 --mute=yes --title="YouTube" "$VID"
fi
