from pathlib import Path
import hashlib
import json
import os
import signal
import struct
import urllib.request

expected = Path('/tmp/panel-expected-sha256').read_text().strip()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('http://169.254.140.109:9090/panel', timeout=30) as response:
    data = response.read(16 * 1024**2)
assert data[:5] == b'\x7fELF\x01' and struct.unpack_from('<H', data, 18)[0] == 40
assert hashlib.sha256(data).hexdigest() == expected
destination = Path('/usr/local/bin/vision-panel')
with destination.open('rb') as stream:
    previous = hashlib.file_digest(stream, 'sha256').hexdigest()
staging = destination.with_name('vision-panel.next')
with staging.open('xb') as stream:
    stream.write(data)
    stream.flush()
    os.fchmod(stream.fileno(), 0o755)
    os.fsync(stream.fileno())
os.replace(staging, destination)
fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
os.fsync(fd)
os.close(fd)
for process in Path('/proc').glob('[0-9]*'):
    try:
        if (process / 'comm').read_text().strip() == 'vision-panel':
            os.kill(int(process.name), signal.SIGTERM)
    except FileNotFoundError:
        pass
print('PANEL_UPDATE ' + json.dumps({'previousSha256': previous, 'sha256': expected,
                                   'bytes': len(data), 'persistedToSdRoot': True}), flush=True)
