#!/bin/sh
set -eu
if [ "$#" -ne 3 ]; then echo "Usage: build-sd-image.sh DELIVERY STAGED_ROOTFS NEW_IMAGE_FILE" >&2; exit 2; fi
delivery=$(CDPATH= cd -- "$1" && pwd)
root=$(CDPATH= cd -- "$2" && pwd)
directory=$(CDPATH= cd -- "$(dirname -- "$3")" && pwd)
image="$directory/$(basename -- "$3")"
if [ -e "$image" ] || [ -e "$image.gz" ]; then echo "The image output must be a new file" >&2; exit 2; fi
for file in BOOT.bin zImage system.dtb; do test -s "$delivery/boot/$file"; done
test -x "$root/usr/local/bin/vision-engine"
test -x "$root/etc/init.d/rcS"
# Operate exclusively on new regular files. Never accept a disk device.
work=$(mktemp -d "$directory/.sd-image-XXXXXX")
trap 'rm -rf -- "$work"' EXIT
truncate -s 128M "$work/boot.fat"
mkfs.fat -F32 -n VISIONBOOT "$work/boot.fat"
mcopy -i "$work/boot.fat" "$delivery/boot/BOOT.bin" "$delivery/boot/zImage" "$delivery/boot/system.dtb" ::/
mmd -i "$work/boot.fat" ::/vision
fsck.fat -n "$work/boot.fat"
truncate -s 1919M "$work/rootfs.ext4"
mkfs.ext4 -F -q -L VISIONROOT -m 1 -d "$root" "$work/rootfs.ext4"
e2fsck -fn "$work/rootfs.ext4"
python3 - "$work" "$image" <<'PY'
from pathlib import Path
import os,shutil,struct,sys
work,image=map(Path,sys.argv[1:])
sector=512
parts=[(2048,128*2048,0x0c,'boot.fat'),(129*2048,1919*2048,0x83,'rootfs.ext4')]
mbr=bytearray(512)
for index,(start,count,kind,name) in enumerate(parts):
    struct.pack_into('<B3sB3sII',mbr,446+index*16,0x80 if index==0 else 0,b'\xfe\xff\xff',kind,b'\xfe\xff\xff',start,count)
mbr[510:]=b'\x55\xaa'
partial=work/'image.partial'
with partial.open('xb') as stream:
    stream.truncate(2048*1024*1024)
    stream.seek(0);stream.write(mbr)
    for start,count,kind,name in parts:
        if (work/name).stat().st_size!=count*sector:raise RuntimeError('Invalid partition size')
        stream.seek(start*sector)
        with (work/name).open('rb') as source:shutil.copyfileobj(source,stream,1024*1024)
    stream.flush();os.fsync(stream.fileno())
partial.rename(image)
PY
gzip -k -f "$image"
echo "2 GiB SD image assembled and filesystem-checked: $image.gz"
echo "HDMI, USB, camera and cold-boot qualification on the physical board remains required."
