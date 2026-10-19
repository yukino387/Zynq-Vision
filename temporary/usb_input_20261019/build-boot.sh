#!/bin/sh
set -eu
task=/workspace/temporary/usb_input_20261019
delivery=/workspace/camera/terminal/build/delivery
backup=/workspace/camera/terminal/build/pre-usb-fix
mkdir -p "$backup/boot"
for name in system.dtb u-boot.elf BOOT.bin; do
    test ! -e "$backup/boot/$name"
    cp "$delivery/boot/$name" "$backup/boot/$name"
done
cp "$delivery/qualification.json" "$backup/qualification.json"
cp "$delivery/checksums.json" "$backup/checksums.json"
cp "$task/system.dtb" "$delivery/boot/system.dtb"
sh /workspace/camera/terminal/linux/build-uboot.sh \
    /opt/vision/u-boot-a58e2b7af42c179ace2c6210de0a219fa3f3cf3c \
    "$delivery/boot/system.dtb" /opt/vision/uboot
cp /opt/vision/uboot/u-boot.elf "$delivery/boot/u-boot.elf"
fdtget -t x "$delivery/boot/system.dtb" /usb-phy reset-gpios
fdtget -t s "$delivery/boot/system.dtb" /axi/slcr@f8000000/pinctrl@700/usb-reset-default/mux groups
echo USB_DEVICE_TREE_BUILD_PASSED
