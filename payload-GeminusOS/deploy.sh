#!/bin/bash
# Instala TODO el payload de GeminusOS en una SD montada (o en la imagen).
#
#   ./deploy.sh /run/media/USUARIO/vendor [/run/media/USUARIO/rootfs]
#
# Si no se da la particion del sistema (rootfs), solo se actualiza vendor.
# Hace copia de seguridad de lo que reemplaza y verifica md5 al final.
set -e

DEST="${1:?uso: $0 <punto de montaje de la particion vendor> [punto de montaje del rootfs]}"
ROOT="${2:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"

[ -d "$DEST" ] || { echo "ERROR: $DEST no existe"; exit 1; }

echo "=== 1. vendor/ctrl ==="
mkdir -p "$DEST/ctrl"
for f in geminuslauncher geminus-yt-panel geminus-inpanel geminus-browser youtube.sh yt-bridge.py dmenu_ln menu-drastic \
         libmenuhook.so libdrastic_shader.so ndsCtrl-libdsflip.sh mtp-watch.sh setSSH.sh \
         geminus-update.py version scrape_libretro.py scrape_screenscraper.py \
         scrape_thegamesdb.py ra_login.py ra_sync.py ra_achievements.py; do
    src="$HERE/vendor/ctrl/$f"
    [ -f "$src" ] || { echo "  falta $src"; exit 1; }
    cp -f "$src" "$DEST/ctrl/$f"; chmod 755 "$DEST/ctrl/$f"
    echo "  $f"
done

    echo "=== 1b. vendor/ctrl/icons_grid + ui ==="
    for d in icons_grid ui apps fonts; do
        mkdir -p "$DEST/ctrl/$d"
        cp -rf "$HERE/vendor/ctrl/$d/." "$DEST/ctrl/$d"/ 2>/dev/null || true
        chmod 644 "$DEST/ctrl/$d"/* 2>/dev/null
        echo "  $d ($(ls "$DEST/ctrl/$d" | wc -l) ficheros)"
    done
    # Los scripts de Apps deben seguir siendo ejecutables (si no, el launcher
    # los lanzaría con "sh" y sus bashismos fallarían).
    chmod 755 "$DEST/ctrl/apps/"*.sh  "$DEST/ctrl/apps/"*.py \
              "$DEST/ctrl/apps/yt-dlp" 2>/dev/null || true

echo "=== 1c. despachador (geminus-run.sh) ==="
for d in /userdata /mnt/data; do
    if [ -d "$d" ] && [ -w "$d" ]; then
        cp -f "$HERE/vendor/ctrl/dmenu_ln" "$d/geminus-run.sh"
        chmod 755 "$d/geminus-run.sh"
        echo "  $d/geminus-run.sh"
    fi
done

echo "=== 2. vendor/deep ==="
mkdir -p "$DEST/deep/nds-emu"
cp -f "$HERE/vendor/deep/nds-emu/nds_emu" "$DEST/deep/nds-emu/nds_emu"
chmod 755 "$DEST/deep/nds-emu/nds_emu"
echo "  nds_emu"

echo "=== 2b. vendor/ctrl/locale ==="
DATA="${GEMINUS_DATA:-/mnt/data}"
for l in es en; do
    if [ -f "$HERE/vendor/ctrl/locale/$l/LC_MESSAGES/geminuslauncher.mo" ]; then
        mkdir -p "$DATA/locale/$l/LC_MESSAGES"
        cp -f "$HERE/vendor/ctrl/locale/$l/LC_MESSAGES/geminuslauncher.mo" \
              "$DATA/locale/$l/LC_MESSAGES/geminuslauncher.mo"
        echo "  $l"
    fi
done

echo "=== 3. vendor/logos y resources ==="
mkdir -p "$DEST/ctrl/waiting"
[ -f "$HERE/vendor/ctrl/waiting/bootlogo.bmp" ] && cp -f "$HERE/vendor/ctrl/waiting/bootlogo.bmp" "$DEST/ctrl/waiting/bootlogo.bmp"
for d in res1 res2; do
    if [ -d "$HERE/vendor/resource/$d/boot" ]; then
        mkdir -p "$DEST/resource/$d/boot"
        cp -f "$HERE/vendor/resource/$d/boot/"*.png "$DEST/resource/$d/boot/" 2>/dev/null || true
    fi
done
rm -f "$DEST"/resource/res*/boot/*.orig-anbernic 2>/dev/null || true
echo "  logos"

if [ -n "$ROOT" ] && [ -d "$ROOT" ]; then
    echo "=== 4. rootfs: init scripts ==="
    mkdir -p "$ROOT/etc/init.d"
    for f in S37wifi-fix S38wifi-supp S39mtp-watch S99wifi-diag; do
        cp -f "$HERE/rootfs/etc-init.d/$f" "$ROOT/etc/init.d/$f"; chmod 755 "$ROOT/etc/init.d/$f"
        echo "  $f"
    done

    echo "=== 5. rootfs: umtprd + usb-mtp-on ==="
    mkdir -p "$ROOT/usr/bin"
    cp -f "$HERE/rootfs/usr-bin/umtprd" "$ROOT/usr/bin/umtprd"; chmod 755 "$ROOT/usr/bin/umtprd"
    cp -f "$HERE/rootfs/usr-bin/usb-mtp-on.sh" "$ROOT/usr/bin/usb-mtp-on.sh"; chmod 755 "$ROOT/usr/bin/usb-mtp-on.sh"
    cp -f "$HERE/rootfs/usr-bin/wifi-dhcp-watch.sh" "$ROOT/usr/bin/wifi-dhcp-watch.sh"; chmod 755 "$ROOT/usr/bin/wifi-dhcp-watch.sh"
    echo "  umtprd + usb-mtp-on.sh + wifi-dhcp-watch.sh"

    echo "=== 5b. rootfs: umtprd (MTP limitado a SD + Datos) ==="
    mkdir -p "$ROOT/etc/umtprd"
    cp -f "$HERE/rootfs/etc-umtprd/umtprd.conf" "$ROOT/etc/umtprd/umtprd.conf"
    echo "  umtprd.conf"

    echo "=== 6. rootfs: NetworkManager ==="
    sed -i 's/^plugins=ifupdown,keyfile/plugins=keyfile/' "$ROOT/etc/NetworkManager/NetworkManager.conf" 2>/dev/null || true
    mkdir -p "$ROOT/etc/NetworkManager/conf.d"
    cp -f "$HERE/rootfs/nm-conf.d/unmanaged-p2p0.conf" "$ROOT/etc/NetworkManager/conf.d/unmanaged-p2p0.conf"
    echo "  plugins=keyfile + conf.d"

    echo "=== 7. rootfs: logos de firmware ==="
    mkdir -p "$ROOT/lib/firmware"
    [ -f "$HERE/rootfs/lib-firmware/logo_kernel.bmp" ] && cp -f "$HERE/rootfs/lib-firmware/logo_kernel.bmp" "$ROOT/lib/firmware/logo_kernel.bmp"
    [ -f "$HERE/rootfs/lib-firmware/logo_bottom.bmp" ] && cp -f "$HERE/rootfs/lib-firmware/logo_bottom.bmp" "$ROOT/lib/firmware/logo.bmp"
    echo "  logo_kernel.bmp + logo.bmp"
else
    echo "=== 4-7. rootfs OMITIDO (no se paso el punto de montaje) ==="
fi

sync
echo
echo "Instalado en $DEST${ROOT:+ y $ROOT}"
echo "Particion de arranque: escribir boot/bootp_geminus.bin en la particion 3 (64MB) con dd,"
echo "  p.ej.: dd if=boot/bootp_geminus.bin of=/dev/sdX3 bs=4M conv=fsync"
echo "  (bootp_original.bin = respaldo de fabrica)."
