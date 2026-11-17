#!/bin/sh
# Fetch upstream U-Boot at the base commit of the patches and apply them.
set -e
cd "$(dirname "$0")/.."
BASE=$(cat patches/BASE)
git init -q u-boot
git -C u-boot fetch --depth 1 https://source.denx.de/u-boot/u-boot.git "$BASE"
git -C u-boot checkout -q -b dream2lte FETCH_HEAD
git -C u-boot am -q "$PWD"/patches/*.patch
git -C u-boot log --oneline | head -n 10
