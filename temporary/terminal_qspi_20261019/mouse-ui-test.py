from pathlib import Path
import base64
import hashlib
import json
import os
import struct
import time
import zlib

node = '/dev/input/event8'
assert Path('/sys/class/input/event8/device/name').read_text().strip() == 'Logitech USB Receiver Mouse'
fd = os.open(node, os.O_WRONLY)
def send(kind, code, value):
    os.write(fd, struct.pack('<iiHHi', 0, 0, kind, code, value))
def move(x, y):
    send(2, 0, x);send(2, 1, y);send(0, 0, 0);time.sleep(.2)
def click():
    send(1, 272, 1);send(0, 0, 0);time.sleep(.15)
    send(1, 272, 0);send(0, 0, 0);time.sleep(.25)
def frame():
    with open('/dev/fb0', 'rb', buffering=0) as stream:
        data = stream.read(1280 * 720 * 4)
    assert len(data) == 1280 * 720 * 4
    return data
def pixel(data, x, y):
    return struct.unpack_from('<I', data, (y * 1280 + x) * 4)[0] & 0xffffff
def roi(data):
    return b''.join(data[(y * 1280 + 20) * 4:(y * 1280 + 415) * 4] for y in range(100, 145))

try:
    move(-50000, -50000)
    move(900, 400)
    first = frame()
    assert pixel(first, 907, 407) == 0xffffff, 'Cursor did not recover from left/top overshoot'
    move(50000, 50000)
    edge = frame()
    assert pixel(edge, 907, 407) != 0xffffff, 'Old cursor pixels were not cleared'
    move(-479, -219)
    recovered = frame()
    assert pixel(recovered, 807, 507) == 0xffffff, 'Cursor did not recover from right/bottom overshoot'
    move(-650, -430)  # (150,70), inside the job dropdown.
    closed = frame()
    click()
    opened = frame()
    changed = sum(a != b for a, b in zip(roi(closed), roi(opened)))
    assert changed > 500, 'Left click did not open the dropdown'
    print('MOUSE_UI_FRAME ' + base64.b64encode(zlib.compress(opened, 1)).decode(), flush=True)
    move(950, 580);click()  # Close the dropdown on the empty lower-right screen.
    result = {'method': 'Linux evdev injection into the enumerated Logitech mouse node',
              'device': node, 'leftTopRecovery': True, 'rightBottomRecovery': True,
              'cursorVisible': True, 'oldCursorPixelsCleared': True,
              'leftClickOpenedDropdown': True, 'dropdownRoiBytesChanged': changed,
              'frameSha256': hashlib.sha256(opened).hexdigest(),
              'physicalMouseOperationConfirmed': False}
    print('MOUSE_UI_RESULT ' + json.dumps(result), flush=True)
finally:
    os.close(fd)
