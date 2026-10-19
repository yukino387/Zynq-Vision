"""Observe evdev alongside the panel without grabbing devices or injecting keys."""
import collections
import glob
import json
import os
import select
import struct
import time
from pathlib import Path

files = {os.open(path, os.O_RDONLY | os.O_NONBLOCK): path
         for path in glob.glob('/dev/input/event*')}
counts = collections.Counter()
keys = collections.Counter()
deadline = time.monotonic() + 45
try:
    while time.monotonic() < deadline:
        ready, _, _ = select.select(list(files), [], [], .25)
        for fd in ready:
            data = os.read(fd, 16 * 128)
            for _, _, kind, code, value in struct.iter_unpack('<iiHHi', data):
                if kind in (1, 2):
                    counts[files[fd] + ':' + str(kind)] += 1
                    if kind == 1 and value == 1:
                        keys[str(code)] += 1
finally:
    for fd in files:
        os.close(fd)
result = {'seconds': 45, 'counts': dict(counts), 'pressedKeyCodes': dict(keys)}
Path('/tmp/usb-input-events.json').write_text(json.dumps(result))
print('USB_INPUT_EVENTS', json.dumps(result), flush=True)
