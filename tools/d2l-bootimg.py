#!/usr/bin/env python3
"""Install U-Boot into a Galaxy S8/S8+ (dream2lte) boot image, or take it out.

  d2l-bootimg.py patch   IN.img OUT.img [--uboot u-boot.bin] [--default chain|extlinux] [--name NAME]
  d2l-bootimg.py unpatch IN.img OUT.img
  d2l-bootimg.py info    IN.img

"patch" takes any boot image S-Boot boots (stock Samsung, TWRP-style,
AOSP/LineageOS, the mainline shim images) and makes U-Boot its kernel. The
original kernel is carried after U-Boot:

  kernel section = u-boot.bin, padded to 2 MiB | 4 KiB header | original kernel

The ramdisk, DTBH, header fields (command line, OS version, ...) and a
SEANDROIDENFORCE trailer stay as they are, so S-Boot still loads the
original ramdisk to 0x89000000 and its DTB to 0x8a000000. U-Boot's
"chainload" (menu: "Boot <name>") then enters the original kernel exactly
as S-Boot would have. With --default chain (the default) U-Boot boots it
unless the boot menu is opened; with --default extlinux it boots
/boot/extlinux/extlinux.conf from USERDATA first.

Patching an already patched image replaces U-Boot and keeps the original
kernel, "unpatch" gives back the original image.
"""
import argparse
import os
import struct
import sys
import zlib

MAGIC = b'ANDROID!'
CHAIN_MAGIC = b'D2LCHAIN'
CHAIN_VERSION = 1
CHAIN_OFFSET = 2 * 1024 * 1024        # header after U-Boot, see dream2lte.c
CHAIN_HDR_SIZE = 4096
CHAIN_F_DEFAULT = 1
# U-Boot's early stack sits 512 KiB above its BSS start, keep clear of it
UBOOT_MAX = CHAIN_OFFSET - 640 * 1024
# the kernel section may reach up to S-Boot's ramdisk at 0x89000000
KERNEL_MAX = 0x89000000 - 0x80080000
BOOT_PARTITION_SIZE = 40 * 1024 * 1024
SEANDROID = b'SEANDROIDENFORCE'
HERE = os.path.dirname(os.path.abspath(__file__))


def die(msg):
    sys.exit(f'd2l-bootimg: {msg}')


def align(n, page):
    return (n + page - 1) // page * page


class BootImage:
    """Samsung boot image: header v0, with the DTBH size in the header
    version field (offset 40)."""

    def __init__(self, data):
        if data[:8] != MAGIC:
            die('not an Android boot image')
        (self.kernel_size, _, self.ramdisk_size, _, self.second_size, _, _,
         self.page, self.dt_size) = struct.unpack_from('<9I', data, 8)
        if self.page not in (2048, 4096, 16384):
            die(f'unexpected page size {self.page}')
        self.header = bytearray(data[:self.page])
        off = self.page
        self.kernel = data[off:off + self.kernel_size]
        off += align(self.kernel_size, self.page)
        self.ramdisk = data[off:off + self.ramdisk_size]
        off += align(self.ramdisk_size, self.page)
        self.second = data[off:off + self.second_size]
        off += align(self.second_size, self.page)
        self.dt = data[off:off + self.dt_size]
        off += align(self.dt_size, self.page)
        if len(data) < off:
            die('image is truncated')
        # a partition dump has stale data after the image, a signed
        # Samsung image a SEANDROIDENFORCE marker that S-Boot checks
        self.trailer = SEANDROID if data[off:off + 16] == SEANDROID else b''
        if self.dt_size and self.dt[:4] != b'DTBH':
            print('warning: the dt section is not a Samsung DTBH image',
                  file=sys.stderr)

    @property
    def name(self):
        return self.header[48:64].split(b'\0')[0].decode(errors='replace')

    def chain(self):
        """(header fields, original kernel) if U-Boot is installed"""
        k = self.kernel
        if len(k) < CHAIN_OFFSET + CHAIN_HDR_SIZE or \
           k[CHAIN_OFFSET:CHAIN_OFFSET + 8] != CHAIN_MAGIC:
            return None
        ver, hsize, size, crc, flags = struct.unpack_from(
            '<IIQII', k, CHAIN_OFFSET + 8)
        name = k[CHAIN_OFFSET + 32:CHAIN_OFFSET + 96].split(b'\0')[0]
        payload = k[CHAIN_OFFSET + hsize:CHAIN_OFFSET + hsize + size]
        if ver != CHAIN_VERSION or len(payload) != size or \
           zlib.crc32(payload) != crc:
            die('U-Boot is installed, but the kernel after it is damaged')
        return {'flags': flags, 'name': name.decode(errors='replace'),
                'uboot_size': len(k[:CHAIN_OFFSET].rstrip(b'\0'))}, payload

    def pack(self):
        struct.pack_into('<I', self.header, 8, len(self.kernel))
        out = bytearray(self.header)
        for part in (self.kernel, self.ramdisk, self.second, self.dt):
            out += part + b'\0' * (align(len(part), self.page) - len(part))
        return bytes(out + self.trailer)


def kernel_kind(k):
    if len(k) >= 64 and k[56:60] == b'ARM\x64':
        text_offset, image_size = struct.unpack_from('<QQ', k, 8)
        return f'arm64 Image (text_offset {text_offset:#x})'
    if k[:2] == b'\x1f\x8b':
        return 'gzip'
    if k[:4] == b'\x02\x21\x4c\x18':
        return 'LZ4 (legacy)'
    return 'unknown format'


def cmd_info(args):
    img = BootImage(open(args.image, 'rb').read())
    print(f'{args.image}:')
    print(f'  page size {img.page}, name "{img.name}"')
    print(f'  ramdisk {img.ramdisk_size} bytes, dt {img.dt_size} bytes'
          f'{", SEANDROIDENFORCE" if img.trailer else ""}')
    chain = img.chain()
    if chain:
        hdr, payload = chain
        default = 'chain' if hdr['flags'] & CHAIN_F_DEFAULT else 'extlinux'
        print(f'  kernel: U-Boot ({hdr["uboot_size"]} bytes), carrying '
              f'"{hdr["name"]}": {len(payload)} bytes, {kernel_kind(payload)}')
        print(f'  U-Boot boots by default: {default}')
    else:
        print(f'  kernel: {img.kernel_size} bytes, {kernel_kind(img.kernel)}')
        print('  (U-Boot not installed)')


def write(path, data, limit):
    if len(data) > limit:
        die(f'the result is {len(data)} bytes, more than the {limit} bytes '
            f'of the BOOT partition')
    with open(path, 'wb') as f:
        f.write(data)
    print(f'{path}: {len(data)} bytes ({limit - len(data)} bytes left in BOOT)')


def cmd_patch(args):
    img = BootImage(open(args.image, 'rb').read())
    uboot = open(args.uboot, 'rb').read()
    if uboot[56:60] != b'ARM\x64':
        die(f'{args.uboot} is not a U-Boot image with a kernel header')
    if len(uboot) > UBOOT_MAX:
        die(f'{args.uboot} is too big ({len(uboot)} > {UBOOT_MAX} bytes)')

    chain = img.chain()
    if chain:
        hdr, payload = chain
        name = args.name or hdr['name']
        print(f'U-Boot already installed, replacing it (keeping "{name}")')
    else:
        payload = img.kernel
        name = args.name or img.name or os.path.basename(args.image)
    if not payload:
        die('the boot image has no kernel')

    flags = CHAIN_F_DEFAULT if args.default == 'chain' else 0
    hdr = struct.pack('<8sIIQII64s', CHAIN_MAGIC, CHAIN_VERSION,
                      CHAIN_HDR_SIZE, len(payload), zlib.crc32(payload),
                      flags, name.encode()[:63])
    kernel = (uboot.ljust(CHAIN_OFFSET, b'\0') +
              hdr.ljust(CHAIN_HDR_SIZE, b'\0') + payload)
    if len(kernel) > KERNEL_MAX:
        die('the kernel is too big to fit below the ramdisk')
    img.kernel = kernel
    write(args.output, img.pack(), args.max)
    print(f'U-Boot installed, original kernel "{name}" '
          f'({len(payload)} bytes, {kernel_kind(payload)}), '
          f'default boot: {args.default}')


def cmd_unpatch(args):
    img = BootImage(open(args.image, 'rb').read())
    chain = img.chain()
    if not chain:
        die('U-Boot is not installed in this image')
    img.kernel = chain[1]
    write(args.output, img.pack(), args.max)
    print('original kernel restored')


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split('\n\n')[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('\n\n', 1)[1])
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('info', help='show what a boot image contains')
    p.add_argument('image')
    p.set_defaults(func=cmd_info)

    p = sub.add_parser('patch', help='install U-Boot into a boot image')
    p.add_argument('image')
    p.add_argument('output')
    p.add_argument('--uboot', default=os.path.join(HERE, '..', 'build',
                                                   'u-boot.bin'),
                   help='U-Boot binary (default: build/u-boot.bin)')
    p.add_argument('--default', choices=('chain', 'extlinux'),
                   default='chain',
                   help='what U-Boot boots without the menu: the original '
                        'kernel (chain, default) or /boot/extlinux')
    p.add_argument('--name', help='name of the original kernel in the menu '
                                  '(default: the image name)')
    p.add_argument('--max', type=int, default=BOOT_PARTITION_SIZE,
                   help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_patch)

    p = sub.add_parser('unpatch', help='take U-Boot out of a boot image')
    p.add_argument('image')
    p.add_argument('output')
    p.add_argument('--max', type=int, default=BOOT_PARTITION_SIZE,
                   help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_unpatch)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
