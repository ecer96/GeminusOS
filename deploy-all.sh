#!/bin/bash
# ============================================================================
# GeminusOS — deploy general
#
#   ./deploy-all.sh build                  # solo compila y refresca el payload
#   ./deploy-all.sh console [root@IP]      # compila y despliega por SSH
#   ./deploy-all.sh image <imagen.img>     # compila y escribe en una imagen
#   ./deploy-all.sh sd /dev/sdX            # compila y escribe en una SD
#
#   Opciones: --no-boot   no tocar la particion de arranque (p3)
#
# Compila los TRES proyectos y los mete en el payload:
#   GeminusOSLauncher -> geminuslauncher, geminus-yt-panel
#   menu-drastic      -> menu-drastic, libmenuhook.so
#   drastic-shader    -> libdrastic_shader.so
# y luego instala vendor + rootfs + (opcional) bootlogo.
#
# Particiones que usa (layout de la consola): p3 = boot (64 MB), p6 = rootfs, p8 = vendor.
# ============================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$ROOT/GeminusOSLauncher"
MENU="$ROOT/menu-drastic"
SHADER="$ROOT/drastic-shader"
PAYLOAD="$ROOT/payload-GeminusOS"
SDK="${GEMINUS_SDK:-$HOME/Escritorio/GeminusOS/umfeld-rocknix-h700-sdk/sysroot}"
BOOT_IMG="$PAYLOAD/boot/bootp_geminus.bin"

DO_BOOT=1
ARGS=()
for a in "$@"; do
    case "$a" in
        --no-boot) DO_BOOT=0 ;;
        *) ARGS+=("$a") ;;
    esac
done
MODE="${ARGS[0]:-}"

msg() { echo -e "\n\033[1;36m== $* ==\033[0m"; }
die() { echo "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------- compilar
build_all() {
    [ -d "$LAUNCHER" ] || die "no existe $LAUNCHER"
    msg "Compilando launcher (GeminusOSLauncher)"
    ( cd "$LAUNCHER" && GEMINUS_SDK="$SDK" ./build.sh )

    msg "Compilando menu-drastic"
    ( cd "$MENU" && GEMINUS_SDK="$SDK" ./build-menu.sh )

    msg "Compilando drastic-shader"
    ( cd "$SHADER" && GEMINUS_SDK="$SDK" ./build.sh )

    msg "Refrescando payload"
    mkdir -p "$PAYLOAD/vendor/ctrl"
    cp -f "$LAUNCHER/build/geminuslauncher"      "$PAYLOAD/vendor/ctrl/"
    cp -f "$LAUNCHER/build/geminus-yt-panel"     "$PAYLOAD/vendor/ctrl/"
    cp -f "$LAUNCHER/apps/youtube.sh"            "$PAYLOAD/vendor/ctrl/"
    cp -f "$LAUNCHER/apps/yt-bridge.py"          "$PAYLOAD/vendor/ctrl/"
    cp -f "$LAUNCHER/geminus-run.sh"             "$PAYLOAD/vendor/ctrl/dmenu_ln"
    cp -f "$MENU/build/menu-drastic"             "$PAYLOAD/vendor/ctrl/"
    cp -f "$MENU/build/libmenuhook.so"           "$PAYLOAD/vendor/ctrl/"
    cp -f "$MENU/ndsCtrl-libdsflip.sh"           "$PAYLOAD/vendor/ctrl/"
    cp -f "$SHADER/build/libdrastic_shader.so"   "$PAYLOAD/vendor/ctrl/"
    cp -f "$LAUNCHER/assets/icons/png/"*.png     "$PAYLOAD/vendor/ctrl/icons_grid/"
    cp -f "$LAUNCHER/assets/brand/geminus_word.png" \
          "$LAUNCHER/assets/brand/geminus_word_dark.png" "$PAYLOAD/vendor/ctrl/ui/"
    chmod 755 "$PAYLOAD/vendor/ctrl/"{geminuslauncher,geminus-yt-panel,youtube.sh,yt-bridge.py,dmenu_ln,menu-drastic,ndsCtrl-libdsflip.sh}
    mkdir -p "$PAYLOAD/vendor/ctrl/apps"
    cp -f "$LAUNCHER/apps/"*.sh "$LAUNCHER/apps/"*.py "$LAUNCHER/apps/"*.conf \
          "$LAUNCHER/apps/yt-dlp" "$PAYLOAD/vendor/ctrl/apps/" 2>/dev/null || true
    cp -rf "$LAUNCHER/apps/media/." "$PAYLOAD/vendor/ctrl/apps/media/" 2>/dev/null || true
    chmod 755 "$PAYLOAD/vendor/ctrl/apps/"*.sh "$PAYLOAD/vendor/ctrl/apps/yt-dlp" 2>/dev/null || true
    ( cd "$PAYLOAD" && find . -type f ! -name MD5SUMS ! -name deploy.sh -exec md5sum {} \; | sort -k2 > MD5SUMS )
    echo "payload: $(wc -l < "$PAYLOAD/MD5SUMS") ficheros"
}

# ---------------------------------------------------------------- consola (SSH)
deploy_console() {
    local DEST="${1:-root@192.168.1.36}"
    msg "Desplegando en $DEST"
    tar -C "$PAYLOAD" -czf - . | ssh -o StrictHostKeyChecking=no "$DEST" \
        'rm -rf /tmp/geminus-payload && mkdir -p /tmp/geminus-payload && tar -C /tmp/geminus-payload -xzf -'
    ssh -o StrictHostKeyChecking=no "$DEST" \
        'sh /tmp/geminus-payload/deploy.sh /mnt/vendor / && sync'
    msg "Reiniciando el launcher"
    ssh -o StrictHostKeyChecking=no "$DEST" '
        ps -o pid,comm | awk "\$2 ~ /geminuslauncher|dmenu/ {print \$1}" | xargs -r kill -9 2>/dev/null
        sleep 1
        pgrep -x weston >/dev/null || { /etc/init.d/S49weston start >/dev/null 2>&1; sleep 3; }
        rm -f /tmp/stopAPP.ini /mnt/data/geminus_next
        setsid /mnt/vendor/ctrl/dmenu_ln >/dev/null 2>&1 </dev/null &
        sleep 5
        ps -o pid,comm | awk "\$2 ~ /geminuslauncher|dmenu|weston/"'
    echo "OK"
}

# ---------------------------------------------------------------- imagen / SD
deploy_fs() {
    local VENDOR="$1" ROOTFS="$2" BOOTPART="$3"
    [ -d "$VENDOR" ] || die "$VENDOR no existe"
    msg "Instalando payload en $VENDOR ($ROOTFS)"
    "$PAYLOAD/deploy.sh" "$VENDOR" "$ROOTFS"
    if [ "$DO_BOOT" = 1 ] && [ -n "$BOOTPART" ] && [ -f "$BOOT_IMG" ]; then
        msg "Escribiendo logo de arranque en $BOOTPART"
        sudo dd if="$BOOT_IMG" of="$BOOTPART" bs=4M conv=fsync status=progress
        sync
    fi
    echo "OK"
}

deploy_image() {
    local IMG="${1:-}"; [ -f "$IMG" ] || die "uso: $0 image <imagen.img>"
    msg "Montando $IMG"
    local LOOP
    LOOP="$(sudo losetup -Pf --show "$IMG")"
    trap 'sudo umount /tmp/geminus-mnt/* 2>/dev/null; sudo losetup -d '"$LOOP"' 2>/dev/null' EXIT
    sudo mkdir -p /tmp/geminus-mnt/{vendor,rootfs}
    sudo mount "${LOOP}p8" /tmp/geminus-mnt/vendor
    sudo mount "${LOOP}p6" /tmp/geminus-mnt/rootfs
    deploy_fs /tmp/geminus-mnt/vendor /tmp/geminus-mnt/rootfs "${LOOP}p3"
    sudo umount /tmp/geminus-mnt/vendor /tmp/geminus-mnt/rootfs 2>/dev/null || true
    sudo losetup -d "$LOOP"
    trap - EXIT
}

deploy_sd() {
    local DEV="${1:-}"; [ -b "$DEV" ] || die "uso: $0 sd /dev/sdX"
    msg "Montando ${DEV}8 / ${DEV}6"
    sudo mkdir -p /tmp/geminus-mnt/{vendor,rootfs}
    sudo mount "${DEV}8" /tmp/geminus-mnt/vendor
    sudo mount "${DEV}6" /tmp/geminus-mnt/rootfs
    deploy_fs /tmp/geminus-mnt/vendor /tmp/geminus-mnt/rootfs "${DEV}3"
    sudo umount /tmp/geminus-mnt/vendor /tmp/geminus-mnt/rootfs 2>/dev/null || true
}

# ---------------------------------------------------------------- main
case "$MODE" in
    build)   build_all ;;
    console) build_all; deploy_console "${ARGS[1]:-root@192.168.1.36}" ;;
    image)   build_all; deploy_image "${ARGS[1]:-}" ;;
    sd)      build_all; deploy_sd "${ARGS[1]:-}" ;;
    *)       sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
