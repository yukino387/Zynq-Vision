#!/bin/sh
set -eu
: "${KERNEL_BUILD:?Set KERNEL_BUILD to the configured ARM Linux 6.6 kernel build directory}"
: "${CROSS_COMPILE:?Set CROSS_COMPILE to the ARM hard-float toolchain prefix}"
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output="$source_dir/../build/kernel"
mkdir -p "$output"
for file in vision_accel.c vision_fb.c vision_uapi.h Makefile; do cp "$source_dir/$file" "$output/$file"; done
make -C "$KERNEL_BUILD" M="$output" ARCH=arm CROSS_COMPILE="$CROSS_COMPILE" modules -j8
