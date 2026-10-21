#!/bin/sh
# usb-mtp-on.sh — monta el gadget USB con FunctionFS/MTP y arranca umtprd.
# Se invoca desde /mnt/vendor/ctrl/mtp-watch.sh cuando el cable entra en modo
# dispositivo. Idempotente: se puede llamar varias veces.

G=/sys/kernel/config/usb_gadget/g1
FFS=/dev/usb-ffs/mtp
LOG=/tmp/usb-mtp.log

msg() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

# 1) configfs
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config || { msg "sin configfs"; exit 1; }

# 2) gadget g1
if [ ! -d "$G" ]; then
    mkdir -p "$G" || { msg "no se pudo crear $G"; exit 1; }
    echo 0x1d6b > "$G/idVendor"
    echo 0x0104 > "$G/idProduct"
    echo 0x0100 > "$G/bcdDevice"
    echo 0x0200 > "$G/bcdUSB"
    echo 0xEF > "$G/bDeviceClass"
    echo 0x02 > "$G/bDeviceSubClass"
    echo 0x01 > "$G/bDeviceProtocol"
    mkdir -p "$G/strings/0x409"
    echo "ROCKNIX"   > "$G/strings/0x409/manufacturer"
    echo "MTP"       > "$G/strings/0x409/product"
    echo "ROCKNIXMTP" > "$G/strings/0x409/serialnumber"
    mkdir -p "$G/configs/c.1/strings/0x409"
    echo "MTP" > "$G/configs/c.1/strings/0x409/configuration"
    echo 500   > "$G/configs/c.1/MaxPower"
    mkdir -p "$G/functions/ffs.mtp"
    ln -sf "$G/functions/ffs.mtp" "$G/configs/c.1/ffs.mtp"
    msg "gadget g1 creado"
fi

# 3) FunctionFS
mkdir -p "$FFS"
if ! mountpoint -q "$FFS"; then
    mount -t functionfs mtp "$FFS" || { msg "functionfs fallo"; exit 1; }
    msg "functionfs montado en $FFS"
fi

# 4) umtprd (escribe descriptores en ep0)
if ! pgrep -x umtprd >/dev/null 2>&1; then
    /usr/bin/umtprd -conf /etc/umtprd/umtprd.conf >>"$LOG" 2>&1 &
    sleep 1
    msg "umtprd arrancado"
fi

# 5) atar UDC (despues de que umtprd prepare ep0)
UDC=$(ls /sys/class/udc 2>/dev/null | head -1)
if [ -n "$UDC" ]; then
    cur=$(cat "$G/UDC" 2>/dev/null)
    if [ -z "$cur" ]; then
        echo "$UDC" > "$G/UDC" && msg "UDC atado: $UDC" || msg "fallo al atar UDC $UDC"
    fi
else
    msg "no hay UDC"
fi
exit 0
