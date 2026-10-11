import hashlib
import json
from pathlib import Path
import re
import numpy as np

HERE = Path(__file__).resolve().parent
log = (HERE / 'result.log').read_text()
if 'PASS:' not in log or 'TEST ERROR:' in log:
    raise RuntimeError('Board test did not pass')
stats = {}
for name in ('test_errors', 'test_loaded', 'test_verified', 'input_min', 'input_max',
             'out0_min', 'out0_max', 'out1_min', 'out1_max', 'forward_us',
             'timer_counts_per_second', 'out0_changed', 'out1_changed'):
    match = re.search(r'^' + name + r'\s*=.*?:\s*(-?\d+)\s*$', log, re.MULTILINE)
    if not match:
        raise ValueError(f'Missing target statistic {name}')
    stats[name] = int(match.group(1))
report = dict(input=json.loads((HERE / 'input_report.json').read_text()),
              target=stats, outputs=[], forward_ms=stats['forward_us'] / 1000.0,
              timing_scope='Yolo4_Tiny::forward only, including its cache maintenance',
              validation='Execution, weight/input checksums, output sizes/stats and buffer guards; no numerical reference or detection accuracy check')
for name, shape in (('out0', (75, 13, 13)), ('out1', (75, 26, 26))):
    path = HERE / (name + '.bin')
    required = int(np.prod(shape)) * 2
    raw = path.read_bytes()
    if len(raw) not in (required, (required + 3) // 4 * 4):
        raise ValueError(f'{name}: unexpected export size {len(raw)}')
    raw = raw[:required]
    values = np.frombuffer(raw, dtype='<i2')
    low, high = int(values.min()), int(values.max())
    if (low, high) != (stats[name + '_min'], stats[name + '_max']):
        raise ValueError(f'{name}: exported data differs from target min/max')
    path.write_bytes(raw)
    report['outputs'].append(dict(file=str(path), shape=shape, layout='CHW', dtype='little-endian int16',
                                  count=len(values), bytes=len(raw), min=low, max=high,
                                  zero_count=int(np.count_nonzero(values == 0)),
                                  sha256=hashlib.sha256(raw).hexdigest()))
    print(f'{name}: {shape}; {len(values)} values, {len(raw)} bytes, int16 [{low}, {high}]')
(HERE / 'inference_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"forward: {stats['forward_us']} us ({report['forward_ms']:.3f} ms)")
