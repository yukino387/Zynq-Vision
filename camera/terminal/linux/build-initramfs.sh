#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then echo "Usage: build-initramfs.sh STAGED_ROOTFS NEW_INITRAMFS_FILE" >&2; exit 2; fi
root=$(CDPATH= cd -- "$1" && pwd)
directory=$(CDPATH= cd -- "$(dirname -- "$2")" && pwd)
output="$directory/$(basename -- "$2")"
if [ -e "$output" ]; then echo "The initramfs output must be a new file" >&2; exit 2; fi
test -x "$root/sbin/init"
test -x "$root/usr/local/bin/vision-engine"
test -d "$root/lib/modules"
temporary=$(mktemp -d "$directory/.initramfs-XXXXXX")
trap 'rm -rf -- "$temporary"' EXIT
# Keep find/cpio separate so a failed archive cannot be hidden by a pipeline.
(cd "$root" && find . -print0 > "$temporary/files")
(cd "$root" && cpio --null -o --format=newc < "$temporary/files" > "$temporary/root.cpio")
gzip -1 -c "$temporary/root.cpio" > "$temporary/initramfs.cpio.gz"
mv -- "$temporary/initramfs.cpio.gz" "$output"
echo "RAM boot archive created: $output"
