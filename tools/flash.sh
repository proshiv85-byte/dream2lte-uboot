#!/bin/sh
# Pack build/u-boot.bin into a Samsung boot.img (out/boot-uboot.img) and,
# with an argument, flash it to BOOT (sda7):
#   tools/flash.sh            only pack
#   tools/flash.sh twrp       flash from TWRP over adb, then reboot
#   tools/flash.sh ssh [host] flash from the running Linux over ssh, then reboot
# NOREBOOT=1 skips the reboot.
set -e
cd "$(dirname "$0")/.."
mkdir -p out
if [ ! -f tools/sboot-dtbh.img ]; then
	echo "S-Boot needs a DTBH: tools/extract-dtbh.py your-boot.img tools/sboot-dtbh.img" >&2
	exit 1
fi
python3 tools/mkbootimg.py --kernel build/u-boot.bin --dt tools/sboot-dtbh.img \
	-o out/boot-uboot.img >/dev/null
IMG=out/boot-uboot.img
SUM=$(sha256sum $IMG | cut -d' ' -f1)
SIZE=$(stat -c %s $IMG)
echo "$IMG: $SIZE bytes, $SUM"

case "$1" in
twrp)
	adb get-state 2>/dev/null | grep -q recovery || { echo "phone not in TWRP"; exit 1; }
	adb push $IMG /tmp/b.img >/dev/null
	adb shell "dd if=/tmp/b.img of=/dev/block/sda7 bs=1M 2>/dev/null && sync"
	GOT=$(adb shell "head -c $SIZE /dev/block/sda7 | sha256sum" | cut -d' ' -f1)
	[ "$GOT" = "$SUM" ] || { echo "verify FAILED"; exit 1; }
	echo "flashed + verified"
	[ -n "$NOREBOOT" ] || adb reboot
	;;
ssh)
	H=root@${2:-172.16.42.1}
	ssh $H "cat > /tmp/b.img" < $IMG
	ssh $H "dd if=/tmp/b.img of=/dev/sda7 bs=1M 2>/dev/null && sync"
	GOT=$(ssh $H "head -c $SIZE /dev/sda7 | sha256sum" | cut -d' ' -f1)
	[ "$GOT" = "$SUM" ] || { echo "verify FAILED"; exit 1; }
	echo "flashed + verified"
	[ -n "$NOREBOOT" ] || ssh $H "reboot" || true
	;;
esac
