#!/bin/sh
set -eu
delivery=/workspace/camera/terminal/build/delivery
board=/workspace/camera/terminal/linux
root=/opt/vision/rootfs-20261018-v2
sh "$board/install-rootfs.sh" "$delivery" "$root"
tar -C "$root" -czf "$delivery/rootfs.tar.gz" .
sh "$board/build-initramfs.sh" "$root" "$delivery/boot/initramfs.cpio.gz"
gzip -t "$delivery/boot/initramfs.cpio.gz"
echo 'Updated root filesystem and RAM boot archive passed gzip verification'
