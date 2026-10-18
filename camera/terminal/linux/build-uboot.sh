#!/bin/sh
set -eu
if [ "$#" -ne 3 ]; then echo "Usage: build-uboot.sh UBOOT_SOURCE TERMINAL_DTB OUTPUT_DIRECTORY" >&2; exit 2; fi
source=$(CDPATH= cd -- "$1" && pwd)
dtb=$(readlink -f "$2")
mkdir -p "$3"
output=$(CDPATH= cd -- "$3" && pwd)
board=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${CROSS_COMPILE:=arm-linux-gnueabihf-}"
export ARCH=arm CROSS_COMPILE
# Linux omits U-Boot's pre-relocation markers. Keep a separate control DT
# so the early bus, clock, timer and console bind before serial_init().
control="$output/control.dtb"
cp "$dtb" "$control"
serial=$(fdtget -t s "$control" /aliases serial0)
for node in /axi /axi/slcr@f8000000 /axi/slcr@f8000000/clkc@100 /axi/timer@f8f00600 "$serial"; do
    fdtput -t s "$control" "$node" bootph-all
done
make -C "$source" O="$output" xilinx_zynq_virt_defconfig
"$source/scripts/kconfig/merge_config.sh" -m -O "$output" "$output/.config" "$board/uboot.config"
make -C "$source" O="$output" olddefconfig
make -C "$source" O="$output" EXT_DTB="$control" -j8 u-boot.elf
python3 - "$control" "$output/u-boot.elf" <<'PY'
from pathlib import Path
import sys
dtb,elf=map(Path,sys.argv[1:])
content=elf.read_bytes()
if content[:4]!=b'\x7fELF' or content[18:20]!=b'\x28\0' or dtb.read_bytes() not in content:raise RuntimeError('ARM U-Boot ELF must contain the terminal control device tree')
PY
echo "ARM U-Boot built with the terminal device tree and SD-only boot command."
