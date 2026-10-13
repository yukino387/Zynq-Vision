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
baseline = json.loads((root / 'temporary/bottleneck_test/build/results.json').read_text(encoding='utf-8'))
log = (board / 'result.log').read_text()
assert 'PASS:' in log and 'TEST ERROR' not in log
assert re.search(r'test_errors\s*=\s*test_errors\s*:\s*0\b', log)

def words(path, count):
    raw = path.read_bytes()
    assert len(raw) == count * 4
    return struct.unpack('<' + 'I' * count, raw)

for name, size in [('out0', 1617), ('out1', 6468)]:
    digest = hashlib.sha256((board / f'{name}.bin').read_bytes()[:size]).hexdigest()
    assert digest == baseline['heads_sha256'][name], (name, digest)

times = words(board / 'all_layer_us.bin', 99)
forward = [int(x) for x in re.search(r'FORWARD_US = (.*)', log).group(1).split()]
rows = []
for i, old in enumerate(baseline['layers']):
    measured = statistics.median(times[r * 33 + i] for r in range(3))
    rows.append(dict(layer=old['name'], baseline_us=old['median_us'], candidate_us=measured,
                     saved_us=old['median_us'] - measured))
with (build / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as output:
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
result = dict(baseline_forward_us=baseline['quiet_forward_us'], candidate_forward_us=forward,
              saved_forward_us=statistics.median(baseline['quiet_forward_us']) - statistics.median(forward),
              golden_verified=True, layers=rows)
network_path = build / 'short_udp_results.json'
if network_path.exists():
    network = json.loads(network_path.read_text())
    received = [r for r in network['frames'] if r[0] == 'detect'][3:]
    stats = [r['status'] for r in network['stats'] if r['phase'] == 'detect' and r['status'][1] == 0 and r['status'][9] > 0][3:]
    assert len(received) >= 3 and stats and all(r[10] == 0 for r in stats)
    result.update(received_fps=(len(received) - 1) / (received[-1][2] - received[0][2]),
                  cycle_median_us=statistics.median(r[9] for r in stats))
baseline_network_path = build / 'baseline_udp_results.json'
if baseline_network_path.exists():
    network = json.loads(baseline_network_path.read_text())
    received = [r for r in network['frames'] if r[0] == 'detect'][3:]
    stats = [r['status'] for r in network['stats'] if r['phase'] == 'detect' and r['status'][1] == 0 and r['status'][9] > 0][3:]
    assert len(received) >= 3 and stats and all(r[10] == 0 for r in stats)
    result.update(matched_baseline_fps=(len(received) - 1) / (received[-1][2] - received[0][2]),
                  matched_baseline_cycle_us=statistics.median(r[9] for r in stats))
(build / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'layers'}, ensure_ascii=False, indent=2))
print('Largest changes:', sorted(rows, key=lambda r: r['saved_us'], reverse=True)[:6])
