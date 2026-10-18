"""Install the model and capture board status/error codes during activation."""
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(r'C:/00_workplace/fpga/cnn_accelerator/camera')))
import importlib.util

spec = importlib.util.spec_from_file_location('board_control', r'C:/00_workplace/fpga/cnn_accelerator/camera/board_control.py')
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

package = Path(sys.argv[1] if len(sys.argv) > 1 else
               r'C:/00_workplace/fpga/cnn_accelerator/temporary/milk_model_import/board_model_20261017/model.bin').read_bytes()
b = bc.Board(local_port=5004)
b.command(1)
b.command(2, 0)
b.call(1)
for offset in range(0, len(package), 1400):
    b.call(2, offset, package[offset:offset + 1400])
b.call(3)
start = time.monotonic()
b.call(4)
print(json.dumps({'uploaded': len(package), 'activate_sent': time.monotonic() - start}), flush=True)
b.s.settimeout(0.3)
end = time.monotonic() + 8
statuses = []
replies = []
while time.monotonic() < end:
    try:
        data, remote = b.s.recvfrom(65536)
    except TimeoutError:
        continue
    if remote != b.peer:
        continue
    if len(data) == 48 and struct.unpack_from('<I', data)[0] == 0x31545343:
        st = struct.unpack('<11Ii', data)
        entry = {'t': round(time.monotonic() - start, 3), 'flags': st[2], 'frame': st[3], 'errors': st[10],
                 'capture_us': st[4], 'conversion_us': st[5],
                 'inference_us': st[6], 'transfer_us': st[7], 'cycle_us': st[8]}
        statuses.append(entry)
        print(json.dumps(entry), flush=True)
    elif len(data) == 124 and struct.unpack_from('<I', data)[0] == 0x3152444d:
        replies.append({'result': struct.unpack_from('<I', data, 8)[0]})
print(json.dumps({'count': len(statuses), 'replies': replies}, ensure_ascii=False))
print(json.dumps(b.call(0), ensure_ascii=False))
