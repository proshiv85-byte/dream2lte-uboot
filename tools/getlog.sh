#!/bin/sh
# Print U-Boot's log (the ramoops console zone) from TWRP
adb shell 'mount | grep -q pstore || mount -t pstore pstore /sys/fs/pstore; cat /sys/fs/pstore/pmsg-ramoops-0'
