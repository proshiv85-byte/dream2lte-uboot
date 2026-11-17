#!/bin/sh
# Build U-Boot into build/ (DEV=1: preset the reboot reason to recovery)
set -e
cd "$(dirname "$0")/.."
[ -d u-boot ] || tools/get-uboot.sh
M="make -C u-boot O=$PWD/build CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}"
$M dream2lte_defconfig >/dev/null
[ "${DEV:-0}" = 1 ] && u-boot/scripts/config --file build/.config -e DREAM2LTE_DEV_RECOVERY && $M olddefconfig >/dev/null
$M -j"$(nproc)"
ls -l build/u-boot.bin
