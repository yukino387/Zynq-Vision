#!/bin/sh
set -eu
task=/workspace/temporary/inspection_terminal_20261018
for kind in cases tensors; do
    qemu-arm -cpu cortex-a9 -L /usr/arm-linux-gnueabihf "$task/native_oracle.arm" "$task/native-$kind.json" > "$task/arm-$kind.json"
done
echo ARM-oracle-executed
