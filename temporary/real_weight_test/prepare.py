import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent
dest = root / 'pc_files'
dest.mkdir(exist_ok=True)
report = {'source': str(args.directory.resolve()), 'quantization': 'round(float32 * 512) -> int16'}
for name, count in [('w.bin', 864), ('b.bin', 32)]:
    source = args.directory / name
    raw = source.read_bytes()
    if len(raw) != count * 4:
        raise ValueError(f'{source}: expected {count * 4} bytes, found {len(raw)}')
    values = struct.unpack('<' + 'f' * count, raw)
    if not all(math.isfinite(x) for x in values):
        raise ValueError(f'{source}: non-finite value')
    # float32 scaling by 2**9 is exact for these finite values.
    quantized = [math.floor(x * 512 + 0.5) if x >= 0 else math.ceil(x * 512 - 0.5) for x in values]
    if any(x < -32768 or x > 32767 for x in quantized):
        raise ValueError(f'{source}: int16 overflow after quantization')
    report[name] = {'count': count, 'bytes': len(raw), 'float_min': min(values),
                    'float_max': max(values), 'int16_min': min(quantized),
                    'int16_max': max(quantized), 'sha256': hashlib.sha256(raw).hexdigest()}
    shutil.copyfile(source, dest / name)
directory = str(args.directory.resolve()).replace('\\', '/').encode('utf-8') + b'\0'
if len(directory) > 1024:
    raise ValueError('Directory path is too long for test adapter')
(dest / 'directory.bin').write_bytes(directory)
(root / 'weight_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
