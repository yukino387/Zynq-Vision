import ctypes
import glob
import json
import mmap
import os
from pathlib import Path

def read_registers(address, offsets):
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, 4096, prot=mmap.PROT_READ, offset=address) as memory:
            import struct
            return {hex(i): hex(struct.unpack_from('<I', memory, i)[0]) for i in offsets}
    finally:
        os.close(fd)

devices = []
for path in Path('/sys/bus/usb/devices').glob('*'):
    if not (path / 'idVendor').exists():
        continue
    item = {'path': path.name}
    for name in ['idVendor', 'idProduct', 'product', 'speed']:
        if (path / name).exists():
            item[name] = (path / name).read_text().strip()
    devices.append(item)

panel = []
for process in Path('/proc').glob('[0-9]*'):
    try:
        if (process / 'comm').read_text().strip() == 'vision-panel':
            panel.append({'pid': int(process.name), 'inputFds':
                          [os.readlink(fd) for fd in (process / 'fd').glob('*')
                           if os.readlink(fd).startswith('/dev/input/')]})
    except (FileNotFoundError, PermissionError):
        pass

state = {'kernel': os.uname().release, 'usbDevices': devices,
         'inputNodes': glob.glob('/dev/input/event*'), 'panel': panel,
         'inputDevices': Path('/proc/bus/input/devices').read_text(),
         'gpio': Path('/sys/kernel/debug/gpio').read_text(),
         'mio': read_registers(0xf8000000, [0x724]),
         'usb': read_registers(0xe0002000, [0x140, 0x144, 0x170, 0x184]),
         'vdma': read_registers(0x43000000, [0, 4, 0x50, 0x54, 0x58]),
         'physicalSdWritten': False}
Path('/tmp/usb-board-state.json').write_text(json.dumps(state))
print('USB_BOARD_STATE ' + json.dumps(state), flush=True)
