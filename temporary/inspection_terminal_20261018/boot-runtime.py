from pathlib import Path
import os,selectors,subprocess,sys,time

task=Path('/workspace/temporary/inspection_terminal_20261018')
delivery=Path('/workspace/camera/terminal/build/delivery')
device=sys.argv[1] if len(sys.argv)>1 else 'usb-kbd'
assert device in ['usb-kbd','usb-mouse']
# QEMU's Zynq model has one high-speed port per controller and its hub is
# full-speed only; exercise each HID separately on USB0, as wired in the DT.
command=['qemu-system-arm','-M','xilinx-zynq-a9','-m','1024','-kernel',str(delivery/'boot/zImage'),'-dtb',str(delivery/'boot/system.dtb'),'-drive','file='+str(delivery/'vision-terminal-sd.img')+',if=sd,format=raw,snapshot=on','-device',device+',bus=usb-bus.0','-nographic','-monitor','none','-no-reboot','-append','console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait init=/bin/sh']
process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
output=bytearray();sent=False
deadline=time.monotonic()+55
try:
    while time.monotonic()<deadline:
        for key,events in selector.select(.2):
            part=os.read(key.fileobj.fileno(),65536)
            if not part:break
            output.extend(part)
            if not sent and b'job control turned off' in output:
                sent=True
                process.stdin.write(b'mount -t proc proc /proc; mount -t sysfs sysfs /sys; /bin/busybox sleep 2; /usr/bin/python3 -c "import glob,zipfile,hashlib,json; assert len(glob.glob(\'/dev/input/event*\'))>=1; print(\'VISION_ARM_SD_ROOTFS_PASSED\')"; /bin/busybox poweroff -f\n');process.stdin.flush()
        if b'reboot: System halted' in output:break
        if process.poll() is not None:break
finally:
    if process.poll() is None:process.terminate()
    try:remaining=process.communicate(timeout=5)[0]
    except subprocess.TimeoutExpired:process.kill();remaining=process.communicate()[0]
    output.extend(remaining)
    task.joinpath('boot-runtime-'+device+'.console.log').write_bytes(output)
assert b'VISION_ARM_SD_ROOTFS_PASSED\r' in output or b'VISION_ARM_SD_ROOTFS_PASSED\n' in output,output[-6000:].decode(errors='replace')
assert b'VFS: Mounted root (ext4 filesystem)' in output
assert b'EHCI Host Controller' in output and (b'QEMU USB Keyboard' if device=='usb-kbd' else b'QEMU USB Mouse') in output
print('Zynq Cortex-A9 SD boot, ext4 root, ARM Python and '+device+' evdev enumeration passed. Physical PL, HDMI, hub wiring and FSBL cold boot remain unverified.')
