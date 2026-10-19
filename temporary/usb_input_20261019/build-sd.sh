#!/bin/sh
set -eu
task=/workspace/temporary/usb_input_20261019
delivery=/workspace/camera/terminal/build/delivery
backup=/workspace/camera/terminal/build/pre-usb-fix
sh /workspace/camera/terminal/linux/build-sd-image.sh "$delivery" \
    /opt/vision/rootfs-20261018-v2 "$task/vision-terminal-sd.img"
mv "$delivery/vision-terminal-sd.img" "$backup/vision-terminal-sd.img"
mv "$delivery/vision-terminal-sd.img.gz" "$backup/vision-terminal-sd.img.gz"
mv "$task/vision-terminal-sd.img" "$delivery/vision-terminal-sd.img"
mv "$task/vision-terminal-sd.img.gz" "$delivery/vision-terminal-sd.img.gz"
python3 /workspace/temporary/terminal_board_20261018/verify-image.py
