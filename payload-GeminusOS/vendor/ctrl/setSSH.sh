#!/bin/sh
# GeminusOS: este sistema usa sysvinit (no systemd).
if [ -x /etc/init.d/S50sshd ]; then
    /etc/init.d/S50sshd restart >/dev/null 2>&1 || /etc/init.d/S50sshd start >/dev/null 2>&1
fi
exit 0
