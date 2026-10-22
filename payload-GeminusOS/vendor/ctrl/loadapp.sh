#!/bin/bash

# Candado: solo una cadena a la vez
exec 9>/tmp/loadapp.lock
flock -n 9 || exit 0

. /etc/profile.d/myenv.sh

# --- sdl2 use two buffer ---
export SDL_VIDEO_DOUBLE_BUFFER=1
export SDL_RENDER_VSYNC=1

StopBin="/tmp/stopAPP.ini"
DEBUG="/mnt/data/xudebug.ini"
CHRGBIN="/mnt/vendor/bin/charg.dge"
RunBin="/mnt/vendor/ctrl/dmenu_ln"

stop_ums_gadget()
{
    USB_ONLINE=`cat /sys/class/power_supply/usb/online`
    if [ $USB_ONLINE != 1 ] && [ -f "/var/run/usb-gadget/funcs" ]
    then
        /mnt/vendor/ctrl/usbgadget.sh
    fi
}

off_wait_loading()
{
    if [ -f "/tmp/loading.msg" ]
    then
        sleep 2
        kill -9 $(pidof wait.dge)
    fi
}

check_weston_run()
{
    MAX_ATTEMPTS=5
    ATTEMPT=0

    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        if pgrep -x "weston" > /dev/null
        then
            if [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]
            then
                echo "---> [loadapp] found weston, finish check <---" > /dev/console 2>&1
                break;
            fi
        fi

        echo "[loadapp] Waiting... (attempt $((ATTEMPT+1))/$MAX_ATTEMPTS)" > /dev/console 2>&1
        sleep 0.5
        ATTEMPT=$((ATTEMPT+1))
    done
}

check_anbernic_manage()
{
    #set cw2015, default PMU
    if [ -f /sys/class/power_supply/cw2015-battery/capacity ];then
        echo "1" > /sys/class/anbernic_misc/chrg_dev
    fi

    #set shutdown voltage value, default is 3430mV
    if [ -f /sys/class/anbernic_misc/shutdown_voltage ];then
        echo "3560" > /sys/class/anbernic_misc/shutdown_voltage
    fi

    #set shutdown cap value, default is 5%
    if [ -f /sys/class/anbernic_misc/shutdown_cap ];then
        echo "10" > /sys/class/anbernic_misc/shutdown_cap
    fi

    #force hdmi out 1280x720-60
    if [ -f /sys/class/hdmi/hdmi/attr/force_720p ];then
        echo 1 > /sys/class/hdmi/hdmi/attr/force_720p
    fi
}

load_usb_bt_module()
{
LOCKFILE=/tmp/.load_wifibt
return

if [ ! -f $LOCKFILE ]; then
        if [ -f /lib/modules/5.15.140/kernel/drivers/misc/seekwaveplatform_lite/skw_usb_lite.ko ]; then
                insmod  /lib/modules/5.15.140/kernel/drivers/misc/seekwaveplatform_lite/skw_usb_lite.ko  >/dev/null 2>&1
        fi

        if [ $1 -eq 0 ];then
                if [ -f /lib/modules/5.15.140/kernel/drivers/net/wireless/swt6621s_wifi/swt6621s_wifi.ko ]; then
                        insmod  /lib/modules/5.15.140/kernel/drivers/net/wireless/swt6621s_wifi/swt6621s_wifi.ko  >/dev/null 2>&1
                fi

                if [ -f /lib/modules/5.15.140/kernel/drivers/bluetooth/skwbt.ko ]; then
                        insmod  /lib/modules/5.15.140/kernel/drivers/bluetooth/skwbt.ko  >/dev/null 2>&1
                fi
        fi

        touch $LOCKFILE
fi
}

charging_boot_set_server()
{
        load_usb_bt_module 1
}

normal_boot_set_server()
{
        load_usb_bt_module 0
}

# ----------- start function-------------------
check_anbernic_manage

check_weston_run

BOOT_MODE=0
if [ $BOOT_MODE == 1 ]; then
        charging_boot_set_server

        if [ -f $CHRGBIN ]; then
                $CHRGBIN
                sleep 5
                poweroff
        fi
else
        normal_boot_set_server

        #----- sync local wall time to rtc time ------
        RTC_DATE=`cat /sys/class/rtc/rtc0/date`
        if [ x"$RTC_DATE" == x ]
        then
                SYS_DATE=`date "+%Y-%m-%d"`
                date -s  $SYS_DATE
                hwclock -w
        else
                hwclock --hctosys -l
        fi
fi

/mnt/vendor/ctrl/setRA.sh  check_cfg

#---- third mod need this to mount sdcard ---
/mnt/vendor/ctrl/mmc_new.sh add

/mnt/vendor/ctrl/setPulseaudio.sh checkrun

off_wait_loading
stop_ums_gadget

# disable wifi auto connect (comentado para que el WiFi no se caiga)
#nmcli networking off

# disable bt auto connect (comentado)
#bluetoothctl power off

# PulseAudio ya se ha comprobado arriba con setPulseaudio.sh checkrun;
# no hace falta un sleep fijo antes de lanzar el launcher.


if [ -f "/mnt/mod/ctrl/autostart" ]; then
        /mnt/mod/ctrl/autostart
fi

if [ -f $DEBUG ];then
        exit 0
fi

# === MODIFICADO: usar ecer-run.sh via dmenu_ln ===
trap 'kill 0' EXIT TERM INT

while [ -f $RunBin ]
do
        if [ -f $StopBin ];then
                break
        fi
        $RunBin || true
done

exit 0
