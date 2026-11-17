#!/bin/sh
# Export the commits of u-boot/ (branch dream2lte) on top of patches/BASE.
set -e
cd "$(dirname "$0")/.."
rm -f patches/*.patch
git -C u-boot format-patch -q -o "$PWD/patches" "$(cat patches/BASE)"..dream2lte
ls patches
