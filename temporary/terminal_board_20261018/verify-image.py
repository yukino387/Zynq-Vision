from pathlib import Path
import hashlib, struct, subprocess

delivery = Path('/workspace/camera/terminal/build/delivery')
image = delivery / 'vision-terminal-sd.img'
with image.open('rb') as stream:
    mbr = stream.read(512)
assert image.stat().st_size == 2048 * 1024 * 1024
assert mbr[510:] == b'\x55\xaa'
partitions = [struct.unpack_from('<B3sB3sII', mbr, 446 + 16 * index) for index in range(2)]
assert [(part[0], part[2], part[4], part[5]) for part in partitions] == [
    (0x80, 0x0c, 2048, 128 * 2048), (0, 0x83, 129 * 2048, 1919 * 2048)]
for name in ('BOOT.bin', 'zImage', 'system.dtb'):
    embedded = subprocess.check_output(['mtype', '-i', str(image) + '@@1048576', '::/' + name])
    expected = (delivery / 'boot' / name).read_bytes()
    assert embedded == expected, name + ' differs from the current delivery artifact'
    print(name, hashlib.sha256(embedded).hexdigest())
print('PASS: 2 GiB MBR partition bounds and all current boot files match the SD image exactly')
