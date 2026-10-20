#!/bin/sh
set -eu
if [ "$#" -ne 4 ]; then echo "Usage: build-rootfs.sh VERIFIED_PACKAGES_JSON DELIVERY KERNEL_ROOTFS NEW_ROOTFS_DIRECTORY" >&2; exit 2; fi
manifest=$(readlink -f "$1")
delivery=$(CDPATH= cd -- "$2" && pwd)
modules=$(CDPATH= cd -- "$3" && pwd)
board=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -e "$4" ]; then echo "The output root filesystem must be a new directory" >&2; exit 2; fi
mkdir -p "$4"
root=$(CDPATH= cd -- "$4" && pwd)
mkdir -p "$root/usr/bin" "$root/usr/sbin" "$root/usr/lib"
python3 - "$manifest" "$root" <<'PY'
import hashlib,json,subprocess,sys,shutil
from pathlib import Path
manifest,root=Path(sys.argv[1]),Path(sys.argv[2])
for item in json.loads(manifest.read_text()):
    file=manifest.parent/'packages'/item['file']
    if file.name!=item['file'] or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Package checksum mismatch')
    architecture=subprocess.check_output(['dpkg-deb','-f',str(file),'Architecture'],text=True).strip()
    if architecture not in ['armhf','all']:raise RuntimeError('Wrong root filesystem architecture')
    subprocess.run(['dpkg-deb','-x',str(file),str(root)],check=True)
for name in ['bin','sbin','lib']:
    legacy,target=root/name,root/'usr'/name
    if legacy.exists() and not legacy.is_symlink():
        for entry in legacy.iterdir():
            destination=target/entry.name
            if destination.exists() or destination.is_symlink():raise RuntimeError('Duplicate merged directory entry: '+str(destination))
            shutil.move(str(entry),str(destination))
        legacy.rmdir()
    if not legacy.is_symlink():legacy.symlink_to('usr/'+name)
PY
mkdir -p "$root/etc/init.d" "$root/proc" "$root/sys" "$root/dev" "$root/run" "$root/tmp" "$root/boot"
mknod -m600 "$root/dev/console" c 5 1
mknod -m666 "$root/dev/null" c 1 3
for applet in sh mount umount mkdir modprobe hostname ifconfig route udhcpc grep sleep sync chmod cp reboot dmesg cat ls poweroff; do
    [ -e "$root/bin/$applet" ] || ln -s busybox "$root/bin/$applet"
done
ln -s ../bin/busybox "$root/sbin/init"
ln -s ../bin/busybox "$root/sbin/reboot"
ln -s ../bin/busybox "$root/sbin/modprobe"
ln -s ../bin/busybox "$root/sbin/poweroff"
ln -s sbin/init "$root/init"
ln -s ../proc/self/mounts "$root/etc/mtab"
sh "$board/install-rootfs.sh" "$delivery" "$root"
cp -a "$modules/lib/modules" "$root/lib/"
install -m755 "$board/rcS" "$root/etc/init.d/rcS"
install -m755 "$board/udhcpc.script" "$root/etc/udhcpc.script"
install -m644 "$board/inittab" "$root/etc/inittab"
printf '%s\n' 'root:x:0:0:Terminal administrator:/root:/bin/sh' > "$root/etc/passwd"
printf '%s\n' 'root:x:0:' > "$root/etc/group"
mkdir -p "$root/root"
printf '%s\n' '127.0.0.1 localhost vision-terminal' > "$root/etc/hosts"
printf '%s\n' 'nameserver 223.5.5.5' > "$root/etc/resolv.conf"
chmod 1777 "$root/tmp"
echo "ARM terminal root filesystem assembled. Hardware boot qualification remains required."
