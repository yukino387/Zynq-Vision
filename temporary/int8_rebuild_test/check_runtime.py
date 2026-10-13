from pathlib import Path
import hashlib
import re
import struct
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
elf = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'vitis_live/camera_live/build/camera_live.elf'
data = elf.read_bytes()
assert data[:6] == b'\x7fELF\x01\x01', 'Expected a little-endian ARM ELF32'
offset = struct.unpack_from('<I', data, 28)[0]
stride, count = struct.unpack_from('<HH', data, 42)
segments = [struct.unpack_from('<8I', data, offset+i*stride) for i in range(count)]
nm = 'C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-nm.exe'
symbols = subprocess.check_output([nm, str(elf)], text=True)
for name in ('weights', 'metadata'):
    match = re.search(r'^([0-9a-f]+)\s+\w\s+'+name+r'$', symbols, re.M)
    assert match, f'Missing {name} symbol'
    address = int(match[1], 16)
    expected = (root / 'camera/int8' / (name+'.bin')).read_bytes()
    for kind, start, virtual, _, size, _, _, _ in segments:
        if kind == 1 and virtual <= address and address+len(expected) <= virtual+size:
            actual = data[start+address-virtual:start+address-virtual+len(expected)]
            assert actual == expected, f'{name} payload mismatch'
            print('PASS embedded', name, len(actual), 'bytes', hashlib.sha256(actual).hexdigest())
            break
    else:
        raise AssertionError(f'{name} is outside the ELF load segments')
