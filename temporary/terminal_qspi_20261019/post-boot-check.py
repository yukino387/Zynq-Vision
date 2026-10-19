from pathlib import Path
import hashlib
import json
import os
import sys
import urllib.request

root_device = os.stat('/').st_dev
assert (os.major(root_device), os.minor(root_device)) == (179, 2), 'Linux root must be the physical SD ext4 partition'
assert Path('/sys/block/mmcblk0/device/cid').read_text().strip() == 'fe3432534431364720000001cf017b00'
original = json.loads(Path('/tmp/original-model-manifest.json').read_text())
for entry in original['files']:
    path = Path('/boot') / entry['path']
    assert path.stat().st_size == entry['size']
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256'], entry['path']
devices = []
for path in Path('/sys/bus/usb/devices').glob('*'):
    if (path / 'idVendor').exists():
        devices.append(((path / 'idVendor').read_text().strip(), (path / 'idProduct').read_text().strip()))
assert ('05e3', '0608') in devices and ('0c45', 'fefe') in devices
processes = {}
input_files = []
for process in Path('/proc').glob('[0-9]*'):
    try:
        name = (process / 'comm').read_text().strip()
        if name in ('vision-panel', 'vision-engine'):
            processes[name] = int(process.name)
            if name == 'vision-panel':
                input_files = [os.readlink(fd) for fd in (process / 'fd').glob('*')
                               if os.readlink(fd).startswith('/dev/input/')]
    except FileNotFoundError:
        pass
assert set(processes) == {'vision-engine', 'vision-panel'}
assert '/dev/input/event0' in input_files
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('http://127.0.0.1:8877/state', timeout=5) as response:
    engine = json.load(response)
marker = Path('/var/lib/vision/.qspi-boot-verification.json')
boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
phase = sys.argv[1]
if phase == 'write':
    with marker.open('x') as stream:
        json.dump({'token': 'qspi-terminal-20261019', 'bootId': boot_id}, stream)
        stream.flush()
        os.fsync(stream.fileno())
elif phase == 'verify':
    saved = json.loads(marker.read_text())
    assert saved['token'] == 'qspi-terminal-20261019' and saved['bootId'] != boot_id
    marker.unlink()
else:
    raise ValueError(phase)
fd = os.open(marker.parent, os.O_RDONLY | os.O_DIRECTORY)
os.fsync(fd)
os.close(fd)
result = {'phase': phase, 'bootId': boot_id, 'rootDevice': [179, 2],
          'rootOnPhysicalSd': True, 'kernel': os.uname().release,
          'modelsRestoredAndVerified': len(original['files']), 'usbDevices': devices,
          'processes': processes, 'panelInputFds': input_files,
          'engineResponding': True, 'engineJob': engine.get('job'),
          'statePersistedAcrossReboot': phase == 'verify'}
print('QSPI_BOOT_STATE ' + json.dumps(result), flush=True)
