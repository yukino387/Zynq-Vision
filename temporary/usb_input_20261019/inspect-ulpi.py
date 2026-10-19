import json
import ctypes
import mmap
import os
import struct
import time

fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
regs = mmap.mmap(fd, 4096, flags=mmap.MAP_SHARED,
                 prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=0xe0002000)

def read32(offset):
    return struct.unpack_from('<I', regs, offset)[0]

def write32(offset, value):
    ctypes.c_uint32.from_buffer(regs, offset).value = value

def wait_clear(mask):
    deadline = time.monotonic() + 0.1
    while read32(0x170) & mask:
        if time.monotonic() > deadline:
            raise TimeoutError(hex(read32(0x170)))

def read_ulpi(addr):
    write32(0x170, (1 << 31) | (1 << 29))
    wait_clear(1 << 31)
    write32(0x170, (1 << 30) | (addr << 16))
    wait_clear(1 << 30)
    return (read32(0x170) >> 8) & 255

try:
    print('USB_REGS', {hex(i): hex(read32(i)) for i in
                       [0x140, 0x144, 0x170, 0x184, 0x1a8]}, flush=True)
    print('ULPI_REGS', json.dumps({hex(i): hex(read_ulpi(i)) for i in
                                  [0, 1, 2, 3, 4, 7, 0x0a, 0x13, 0x15]}), flush=True)
finally:
    regs.close()
    os.close(fd)
