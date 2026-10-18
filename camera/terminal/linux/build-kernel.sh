#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then echo "Usage: build-kernel.sh LINUX_6_6_SOURCE OUTPUT_DIRECTORY" >&2; exit 2; fi
source=$(CDPATH= cd -- "$1" && pwd)
mkdir -p "$2"
output=$(CDPATH= cd -- "$2" && pwd)
board=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${CROSS_COMPILE:=arm-linux-gnueabihf-}"
export CROSS_COMPILE ARCH=arm
case "$(make -s -C "$source" kernelversion)" in 6.6.*) ;; *) echo "Linux 6.6 LTS source is required" >&2; exit 2;; esac
for file in navigator-v3.9.dts navigator-v3.9-usb.dtsi vision-pl.dtsi; do cp "$board/$file" "$source/arch/arm/boot/dts/xilinx/$file"; done
make -C "$source" O="$output/kernel" multi_v7_defconfig
"$source/scripts/kconfig/merge_config.sh" -m -O "$output/kernel" "$output/kernel/.config" "$board/kernel.config"
make -C "$source" O="$output/kernel" olddefconfig
for symbol in CMA DMA_CMA DEVTMPFS_MOUNT EXT4_FS MMC_SDHCI_OF_ARASAN VFAT_FS USB_CHIPIDEA_HOST USB_CHIPIDEA_GENERIC NOP_USB_XCEIV USB_HID INPUT_EVDEV MOTORCOMM_PHY; do
    if ! grep -qx "CONFIG_${symbol}=y" "$output/kernel/.config"; then echo "Required built-in kernel support is missing: $symbol" >&2; exit 1; fi
done
make -C "$source" O="$output/kernel" -j8 zImage modules xilinx/navigator-v3.9.dtb
KERNEL_BUILD="$output/kernel" sh "$board/build-modules.sh"
release=$(make -s -C "$source" O="$output/kernel" kernelrelease)
mkdir -p "$output/boot" "$output/rootfs/lib/modules/$release/extra"
cp "$output/kernel/arch/arm/boot/zImage" "$output/boot/zImage"
cp "$output/kernel/arch/arm/boot/dts/xilinx/navigator-v3.9.dtb" "$output/boot/system.dtb"
make -C "$source" O="$output/kernel" INSTALL_MOD_PATH="$output/rootfs" modules_install
cp "$board/../build/kernel/vision_accel.ko" "$board/../build/kernel/vision_fb.ko" "$output/rootfs/lib/modules/$release/extra/"
depmod -b "$output/rootfs" "$release"
printf '%s\n' "$release" > "$output/kernel-release"
echo "Kernel, device tree and terminal modules built; boot commissioning is still required."
