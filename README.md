# U-Boot for the Galaxy S8+ (dream2lte, Exynos 8895)

U-Boot is the kernel of the boot image in BOOT (sda7). S-Boot loads it (at a
random address, Samsung KASLR), U-Boot shows its console on the screen and
boots `/boot/extlinux/extlinux.conf` from USERDATA (sda27), or the original
kernel of a boot image it was installed into (see below).

Upstream U-Boot (the commit in [`patches/BASE`](patches/BASE)) plus the
patches in [`patches/`](patches/): the board (`board/samsung/dream2lte`, DT
`arch/arm/dts/exynos8895-dream2lte.dts`), an Exynos UFS host driver
(`drivers/ufs/ufs-exynos.c`, with hooks and quirks in the UFS core), and
Exynos 8895 support for pinctrl/GPIO, the USB DRD PHY, DWC3 and HSI2C.

## Build and flash

Needs an `aarch64-linux-gnu-` cross toolchain and python3.

```sh
tools/build.sh                       # fetches U-Boot + patches into u-boot/, builds build/u-boot.bin
tools/extract-dtbh.py your-boot.img tools/sboot-dtbh.img   # once: S-Boot needs a DTBH in the image
tools/flash.sh twrp                  # pack out/boot-uboot.img, flash it to BOOT from TWRP, reboot
tools/flash.sh ssh                   # the same from the running Linux
fastboot flash BOOT out/boot-uboot.img   # from U-Boot's fastboot mode
```

**Back up BOOT first** (`dd if=/dev/block/sda7 of=...` in TWRP). To go back,
write the old image to sda7 from TWRP.

Working on U-Boot: commit in `u-boot/` (branch `dream2lte`), then
`tools/export-patches.sh`. `DEV=1 tools/build.sh` builds with
`CONFIG_DREAM2LTE_DEV_RECOVERY=y`, which presets the reboot reason to
recovery at the first instruction, so a crash of U-Boot lands in TWRP.
U-Boot's log: `tools/getlog.sh` from TWRP (`pmsg-ramoops-0`), or
`/sys/fs/pstore/console-ramoops-0` in Linux.

## Kernels

`/boot/Image`, `/boot/dtbs/exynos/exynos8895-dream2lte.dtb` and
[`rootfs/boot/extlinux/extlinux.conf`](rootfs/boot/extlinux/extlinux.conf) on
USERDATA. A new kernel is a copy into `/boot`, no boot image to pack.

## Keys

- hold **Volume Down** while U-Boot starts: boot menu (Volume Up/Down move,
  Power selects): boot, fastboot, USB mass storage (the whole UFS LUN 0),
  USB serial console, reboot (normal, TWRP, download), power off
- hold **Bixby for 5 s**, anywhere in U-Boot (also in fastboot or mass
  storage mode): reboot into TWRP

## Installing U-Boot into another boot image

```sh
tools/d2l-bootimg.py patch stock-boot.img boot-with-uboot.img [--default chain|extlinux] [--name NAME]
tools/d2l-bootimg.py info boot-with-uboot.img
tools/d2l-bootimg.py unpatch boot-with-uboot.img original-boot.img
```

The kernel section becomes U-Boot (padded to 2 MiB), a 4 KiB header and the
original kernel; ramdisk, DTBH and header fields stay. U-Boot's `chainload`
(menu entry "Boot NAME", the default with `--default chain`) copies the
original kernel to where S-Boot loaded the image and enters it with MMU and
caches off and x0 = S-Boot's DTB, like S-Boot: the original ramdisk and DTB
are the ones S-Boot loaded. Tested with the mainline shim image.

Careful with stock Android images while USERDATA holds the Linux rootfs:
Android mounts (and may format) userdata through its fstab.

## License

The patches are GPL-2.0+ like U-Boot (the UFS and USB PHY code GPL-2.0-only,
as the Linux drivers it comes from). Everything else here is GPL-2.0 as well.
