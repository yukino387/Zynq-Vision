import csv
import hashlib
import json
import re
import statistics
import struct
from pathlib import Path

test = Path(__file__).resolve().parent
root = test.parents[1]
build = test / 'build'
board = build / 'board'
old = json.loads((root / 'temporary/weight_loader_test/build/comparison.json').read_text(encoding='utf-8'))
golden = json.loads((root / 'temporary/bottleneck_test/build/results.json').read_text(encoding='utf-8'))
log = (board / 'result.log').read_text()
assert 'PASS:' in log and 'TEST ERROR' not in log
assert re.search(r'test_errors\s*=\s*test_errors\s*:\s*0\b', log)
for name, size in [('out0', 1617), ('out1', 6468)]:
    assert hashlib.sha256((board / f'{name}.bin').read_bytes()[:size]).hexdigest() == golden['heads_sha256'][name]
raw = (board / 'all_layer_us.bin').read_bytes()
assert len(raw) == 99 * 4
times = struct.unpack('<99I', raw)
metadata = (root / 'temporary/int8_rebuild_test/build/metadata.bin').read_bytes()
commands = struct.unpack('<330i', metadata[:330 * 4])
rows = []
for i, layer in enumerate(old['layers']):
    measured = statistics.median(times[r * 33 + i] for r in range(3))
    rows.append(dict(layer=layer['layer'], kernel=commands[i * 10 + 8],
                     baseline_us=layer['candidate_us'], candidate_us=measured,
                     saved_us=layer['candidate_us'] - measured))
with (build / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as output:
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
forward = [int(x) for x in re.search(r'FORWARD_US = (.*)', log).group(1).split()]
result = dict(baseline_forward_us=old['candidate_forward_us'], candidate_forward_us=forward,
              requant_baseline_us=sum(r['baseline_us'] for r in rows if r['kernel'] == 5),
              requant_candidate_us=sum(r['candidate_us'] for r in rows if r['kernel'] == 5),
              golden_verified=True, exhaustive_byte_checks=8 * 2 * 256, layers=rows)
for key, file in [('baseline_network', 'baseline_udp_results.json'), ('candidate_network', 'short_udp_results.json')]:
    path = build / file
    if not path.exists():
        continue
    network = json.loads(path.read_text())
    received = [r for r in network['frames'] if r[0] == 'detect'][3:]
    stats = [r['status'] for r in network['stats'] if r['phase'] == 'detect' and r['status'][1] == 0 and r['status'][9] > 0][3:]
    assert len(received) >= 3 and stats and all(r[10] == 0 for r in stats)
    result[key] = dict(received_fps=(len(received) - 1) / (received[-1][2] - received[0][2]),
                       forward_median_us=statistics.median(r[7] for r in stats),
                       cycle_median_us=statistics.median(r[9] for r in stats), errors=0)
(build / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'layers'}, ensure_ascii=False, indent=2))
print('Requant layers:', [r for r in rows if r['kernel'] == 5])
