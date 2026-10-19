from pathlib import Path
import os, selectors, subprocess, sys, time

task = Path('/workspace/temporary/terminal_qspi_20261019')
delivery = Path('/workspace/camera/terminal/build/delivery')
device = sys.argv[1] if len(sys.argv) > 1 else 'usb-kbd'
assert device in ('usb-kbd', 'usb-mouse')
command = ['qemu-system-arm', '-M', 'xilinx-zynq-a9', '-m', '1024',
           '-kernel', str(delivery / 'boot/u-boot.elf'),
           '-drive', 'file=' + str(delivery / 'vision-terminal-sd.img') + ',if=sd,format=raw,snapshot=on',
           '-device', device + ',bus=usb-bus.0', '-nographic', '-monitor', 'none', '-no-reboot']
process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
selector = selectors.DefaultSelector()
selector.register(process.stdout, selectors.EVENT_READ)
output = bytearray()
interrupted = booted = checked = False
# U-Boot's emulated SD reads take about 40 seconds for the kernel.
deadline = time.monotonic() + 120

def send(command):
    process.stdin.write(command)
    process.stdin.flush()

try:
    while time.monotonic() < deadline:
        for key, _ in selector.select(.2):
            part = os.read(key.fileobj.fileno(), 65536)
            if not part:
                break
            output.extend(part)
            if not interrupted and b'Hit any key to stop autoboot' in output:
                interrupted = True
                send(b' ')
            if interrupted and not booted and b'Zynq> ' in output:
                booted = True
                # QEMU cannot reproduce Zynq CPU PLL rate changes after U-Boot.
                # Disable DVFS only in this test; production bootargs are untouched.
                send(b'mmc dev 0; mmc rescan; fatload mmc 0:1 0x02000000 zImage; fatload mmc 0:1 0x08000000 system.dtb; setenv bootargs console=ttyPS0,115200 root=/dev/mmcblk0p2 rw rootwait cma=64M init=/bin/sh cpufreq.off=1; bootz 0x02000000 - 0x08000000\n')
            if not checked and b'job control turned off' in output:
                checked = True
                send(b'mount -t proc proc /proc; mount -t sysfs sysfs /sys; /bin/busybox sleep 2; /usr/bin/python3 -c "import glob,zipfile,hashlib,json; assert glob.glob(\'/dev/input/event*\'); assert hashlib.sha256(open(\'/usr/local/bin/vision-panel\',\'rb\').read()).hexdigest()==\'020eb99dc7d79b4bbab20e0799249e36256339d144c81219a5fee8b45a1c2cde\'; print(\'VISION_UBOOT_SD_ROOTFS_PASSED\')"; /bin/busybox poweroff -f\n')
        if b'reboot: System halted' in output or process.poll() is not None:
            break
finally:
    if process.poll() is None:
        process.terminate()
    try:
        remaining = process.communicate(timeout=5)[0]
    except subprocess.TimeoutExpired:
        process.kill()
        remaining = process.communicate()[0]
    output.extend(remaining)
    task.joinpath('uboot-runtime-' + device + '.console.log').write_bytes(output)

expected = [b'U-Boot 2026.10', b'bytes read in', b'Starting kernel',
            b'VFS: Mounted root (ext4 filesystem)', b'EHCI Host Controller',
            b'QEMU USB Keyboard' if device == 'usb-kbd' else b'QEMU USB Mouse']
for marker in expected:
    assert marker in output, (marker, output[-6000:].decode(errors='replace'))
assert b'VISION_UBOOT_SD_ROOTFS_PASSED\r' in output or b'VISION_UBOOT_SD_ROOTFS_PASSED\n' in output, output[-6000:].decode(errors='replace')
print('PASS: packaged U-Boot ELF -> SD FAT kernel/DT -> Linux ext4 root -> ARM Python -> ' + device + ' evdev')
print('QEMU only; FSBL, physical DDR/PL, HDMI and USB hub still require hardware verification.')
