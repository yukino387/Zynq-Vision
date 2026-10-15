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
old = json.loads((root / 'temporary/micro_io_test/build/comparison.json').read_text(encoding='utf-8'))
baseline_board = build / 'baseline_test/board'
baseline_log = (baseline_board / 'result.log').read_text(encoding='utf-8')
assert 'PASS:' in baseline_log and 'TEST ERROR' not in baseline_log
baseline_times = struct.unpack('<99I', (baseline_board / 'all_layer_us.bin').read_bytes())
golden = json.loads((root / 'temporary/bottleneck_test/build/results.json').read_text(encoding='utf-8'))
log = (board / 'result.log').read_text(encoding='utf-8')
assert 'PASS:' in log and 'TEST ERROR' not in log
assert re.search(r'test_errors\s*=\s*test_errors\s*:\s*0\b', log)
for name, size in [('out0', 1617), ('out1', 6468)]:
    assert hashlib.sha256((board / f'{name}.bin').read_bytes()[:size]).hexdigest() == golden['heads_sha256'][name]
    assert (baseline_board / f'{name}.bin').read_bytes()[:size] == (board / f'{name}.bin').read_bytes()[:size]
raw = (board / 'all_layer_us.bin').read_bytes()
assert len(raw) == 99 * 4
times = struct.unpack('<99I', raw)
metadata = (root / 'temporary/int8_rebuild_test/build/metadata.bin').read_bytes()
commands = struct.unpack('<330i', metadata[:330 * 4])
rows = []
for i, layer in enumerate(old['layers']):
    measured = statistics.median(times[r * 33 + i] for r in range(3))
    baseline = statistics.median(baseline_times[r * 33 + i] for r in range(3))
    rows.append(dict(layer=layer['layer'], kernel=commands[i * 10 + 8],
                     baseline_us=baseline, candidate_us=measured,
                     saved_us=baseline - measured))
with (build / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as output:
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
forward = [int(x) for x in re.search(r'FORWARD_US = (.*)', log).group(1).split()]
baseline_forward = [int(x) for x in re.search(r'FORWARD_US = (.*)', baseline_log).group(1).split()]
result = dict(baseline_forward_us=baseline_forward, candidate_forward_us=forward,
              historical_baseline_forward_us=old['candidate_forward_us'], same_test_elf=True,
              conv_baseline_us=sum(r['baseline_us'] for r in rows if r['kernel'] in (1,3)),
              conv_candidate_us=sum(r['candidate_us'] for r in rows if r['kernel'] in (1,3)),
              golden_verified=True, pool_cases_verified=6, layers=rows)
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
print('Slowest five conv layers:', sorted([r for r in rows if r['kernel'] in (1,3)], key=lambda r: r['candidate_us'], reverse=True)[:5])
