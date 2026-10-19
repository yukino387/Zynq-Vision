#!/bin/bash
set -euo pipefail
delivery=/workspace/camera/terminal/build/delivery
expected=$(sha256sum /workspace/camera/terminal/build/arm/vision-panel | cut -d' ' -f1)
actual=$(tar -xOzf "$delivery/rootfs.tar.gz" ./usr/local/bin/vision-panel | sha256sum | cut -d' ' -f1)
test "$actual" = "$expected"
actual=$(gzip -dc "$delivery/boot/initramfs.cpio.gz" | cpio -i --to-stdout usr/local/bin/vision-panel | sha256sum | cut -d' ' -f1)
test "$actual" = "$expected"
directory=$(mktemp -d /tmp/xp-root-XXXXXX)
trap 'umount "$directory"; rmdir "$directory"' EXIT
mount -t ext4 -o ro,noload,loop,offset=135266304,sizelimit=2012217344 "$delivery/vision-terminal-sd.img" "$directory"
actual=$(sha256sum "$directory/usr/local/bin/vision-panel" | cut -d' ' -f1)
test "$actual" = "$expected"
echo "PASS: SD ext4 image, initramfs and rootfs archive contain the exact XP panel $expected"
