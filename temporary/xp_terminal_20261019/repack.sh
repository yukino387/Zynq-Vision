#!/bin/sh
set -eu
delivery=/workspace/camera/terminal/build/delivery
root=/opt/vision/rootfs-20261018-v2
backup=/workspace/camera/terminal/build/pre-xp-desktop
test ! -e "$backup"
mkdir -p "$backup/boot"
for name in rootfs.tar.gz vision-terminal-sd.img vision-terminal-sd.img.gz; do
    mv "$delivery/$name" "$backup/$name"
done
mv "$delivery/boot/initramfs.cpio.gz" "$backup/boot/initramfs.cpio.gz"
cp "$delivery/qualification.json" "$backup/qualification.json"
cp "$delivery/checksums.json" "$backup/checksums.json"
install -m755 /workspace/camera/terminal/build/arm/vision-panel "$root/usr/local/bin/vision-panel"
sh /workspace/camera/terminal/linux/build-initramfs.sh "$root" "$delivery/boot/initramfs.cpio.gz"
tar --numeric-owner --owner=0 --group=0 -czf "$delivery/rootfs.tar.gz" -C "$root" .
sh /workspace/camera/terminal/linux/build-sd-image.sh "$delivery" "$root" "$delivery/vision-terminal-sd.img"
python3 /workspace/temporary/terminal_board_20261018/verify-image.py
sha256sum "$root/usr/local/bin/vision-panel"
