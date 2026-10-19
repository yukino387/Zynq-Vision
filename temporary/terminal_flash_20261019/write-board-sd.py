"""One-time, CID-locked installation from the RAM-booted terminal."""
from pathlib import Path, PurePosixPath
import fcntl
import gzip
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tarfile
import time
import urllib.request

def sha(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def run(*args):
    subprocess.run(args, check=True)

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('http://169.254.140.109:9089/plan', timeout=10) as response:
    plan = json.load(response)
assert plan['cid'] == 'fe3432534431364720000001cf017b00'
assert Path('/sys/block/mmcblk0/device/cid').read_text().strip() == plan['cid']
assert int(Path('/sys/block/mmcblk0/size').read_text()) == plan['sectors']
assert plan['image']['size'] == 2 * 1024**3
assert 'rootfs / rootfs ' in Path('/proc/mounts').read_text()
assert sha('/tmp/sd-original-files.tar.gz') == plan['backupSha256']
original = json.loads(Path('/tmp/sd-original-manifest.json').read_text())
assert original['cid'] == plan['cid']
for entry in original['files']:
    relative = PurePosixPath(entry['path'])
    assert not relative.is_absolute() and '..' not in relative.parts
    assert relative.parts[0].lower() not in ['boot.bin', 'zimage', 'system.dtb', 'vision']
    assert sha(Path('/boot') / entry['path']) == entry['sha256']
image = Path('/tmp/vision-terminal-sd.img.gz')
with opener.open('http://169.254.140.109:9089/image.gz', timeout=60) as response, image.open('xb') as stream:
    shutil.copyfileobj(response, stream, 1024 * 1024)
assert image.stat().st_size == plan['compressed']['size']
assert sha(image) == plan['compressed']['sha256']
with gzip.open(image, 'rb') as stream:
    header = stream.read(512)
assert header[510:] == b'\x55\xaa'
assert struct.unpack_from('<II', header, 454) == (2048, 128 * 2048)
assert struct.unpack_from('<II', header, 470) == (129 * 2048, 1919 * 2048)
print('SD_PREFLIGHT_PASSED', flush=True)
run('/bin/busybox', 'umount', '/boot')
assert not any(line.split()[0].startswith('/dev/mmcblk0') for line in Path('/proc/mounts').read_text().splitlines())
fd = os.open('/dev/mmcblk0', os.O_RDWR | os.O_EXCL | os.O_SYNC)
try:
    digest = hashlib.sha256()
    total = 0
    with gzip.open(image, 'rb') as stream:
        while block := stream.read(1024 * 1024):
            assert total + len(block) <= plan['image']['size']
            digest.update(block)
            view = memoryview(block)
            while view:
                view = view[os.write(fd, view):]
            total += len(block)
            if total % (256 * 1024**2) == 0:
                print('SD_WRITTEN_BYTES', total, flush=True)
    assert total == plan['image']['size'] and digest.hexdigest() == plan['image']['sha256']
    os.fsync(fd)
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    remaining = total
    while remaining:
        block = os.read(fd, min(1024 * 1024, remaining))
        assert block
        digest.update(block)
        remaining -= len(block)
    assert digest.hexdigest() == plan['image']['sha256'], 'Full raw SD readback hash differs'
    fcntl.ioctl(fd, 0x125f)  # BLKRRPART, only after the original FAT mount is gone.
finally:
    os.close(fd)
deadline = time.monotonic() + 10
while not Path('/dev/mmcblk0p2').exists():
    assert time.monotonic() < deadline
    time.sleep(.1)
run('/bin/busybox', 'mount', '-t', 'vfat', '-o', 'rw,nodev,nosuid,noexec', '/dev/mmcblk0p1', '/boot')
with tarfile.open('/tmp/sd-original-files.tar.gz') as archive:
    for entry in original['files']:
        target = Path('/boot') / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.extractfile('boot/' + entry['path']) as source, target.open('xb') as destination:
            shutil.copyfileobj(source, destination)
for entry in original['files']:
    assert sha(Path('/boot') / entry['path']) == entry['sha256']
for name, entry in plan['boot'].items():
    assert sha(Path('/boot') / name) == entry['sha256']
run('/bin/busybox', 'sync')
run('/bin/busybox', 'mount', '-o', 'remount,ro', '/boot')
result = {'cid': plan['cid'], 'imageBytes': total, 'imageSha256BeforeModelRestore': digest.hexdigest(),
          'fullRawReadbackVerified': True, 'restoredFiles': len(original['files']),
          'allRestoredModelHashesVerified': True, 'bootFilesVerified': True,
          'partition2Present': Path('/dev/mmcblk0p2').exists()}
Path('/tmp/sd-flash-result.json').write_text(json.dumps(result))
print('SD_FLASH_RESULT ' + json.dumps(result), flush=True)
