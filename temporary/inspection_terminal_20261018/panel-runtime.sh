#!/bin/sh
set -eu
ulimit -c 0
task=/workspace/temporary/inspection_terminal_20261018
native=/workspace/camera/terminal
arm-linux-gnueabihf-gcc -shared -fPIC "$task/panel_fb_fixture.c" -o "$task/panel_fb_fixture.so" -ldl
mkdir -p /var/lib/vision
rm -f "$task/panel-fb.bin"
python3 "$task/panel_fixture.py" &
fixture=$!
trap 'kill "$fixture" 2>/dev/null || true' EXIT
sleep 1
kill -0 "$fixture"
set +e
timeout 8 qemu-arm -cpu cortex-a9 -L /usr/arm-linux-gnueabihf -E LD_PRELOAD="$task/panel_fb_fixture.so" "$native/build/arm/vision-panel" "$native/build/delivery/rootfs/usr/share/vision/NotoSansCJKsc-Regular.otf"
status=$?
set -e
test "$status" = 124
test -s "$task/panel-fb.bin"
echo ARM-panel-runtime-and-framebuffer-passed
