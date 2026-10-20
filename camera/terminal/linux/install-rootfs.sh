#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then echo "Usage: install-rootfs.sh DELIVERY_DIRECTORY STAGED_ROOTFS" >&2; exit 2; fi
delivery=$(CDPATH= cd -- "$1" && pwd)
rootfs=$(CDPATH= cd -- "$2" && pwd)
if [ "$rootfs" = / ]; then echo "Use a staged root filesystem directory" >&2; exit 2; fi
install -d "$rootfs/usr/local/bin" "$rootfs/usr/share/vision" "$rootfs/etc/systemd/system/multi-user.target.wants" "$rootfs/var/lib/vision/jobs"
install -m755 "$delivery/rootfs/usr/local/bin/vision-engine" "$rootfs/usr/local/bin/vision-engine"
install -m755 "$delivery/rootfs/usr/local/bin/vision-panel" "$rootfs/usr/local/bin/vision-panel"
install -m755 "$delivery/rootfs/usr/local/bin/vision-install-job.py" "$rootfs/usr/local/bin/vision-install-job.py"
install -m755 "$delivery/rootfs/usr/local/bin/vision-manager.py" "$rootfs/usr/local/bin/vision-manager.py"
install -m644 "$delivery/rootfs/usr/local/bin/vision_auth.py" "$rootfs/usr/local/bin/vision_auth.py"
install -m644 "$delivery/rootfs/usr/share/vision/simsun.ttc" "$rootfs/usr/share/vision/"
for service in vision-engine.service vision-panel.service vision-manager.service; do
    install -m644 "$delivery/rootfs/etc/systemd/system/$service" "$rootfs/etc/systemd/system/$service"
    ln -sfn "../$service" "$rootfs/etc/systemd/system/multi-user.target.wants/$service"
done
chmod 700 "$rootfs/var/lib/vision"
echo "User-space terminal installed. Install matching kernel modules, ARM runtime libraries and the board device tree before booting."
