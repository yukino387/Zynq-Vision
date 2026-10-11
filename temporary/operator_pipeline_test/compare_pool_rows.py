"""Report matched RTL pooling cases, without converting them into frame FPS."""
import json
from pathlib import Path
import re

base = Path(__file__).resolve().parent / 'build'

def cycles(name):
    log = (base / f'{name}_cosim_console.log').read_text(errors='replace')
    assert 'C/RTL co-simulation finished: PASS' in log, name
    cases = re.findall(r'RESIZE kernel=2 channels=(\d+) h=(\d+) errors=(\d+)', log)
    expected = [('8', '26', '0'), ('8', '52', '0'), ('4', '104', '0')]
    assert cases == expected * 2, (name, cases)
    report = (base / f'{name}.transaction.rpt').read_text()
    result = [int(value) for value in re.findall(r'transaction\s+\d+:\s+(\d+)', report)]
    assert len(result) == 3, result
    return result

old = cycles('bias_loop_pool_rows')
new = cycles('pool_rows')
rows = []
for (channels, size), before, after in zip(((8,26), (8,52), (4,104)), old, new):
    row = dict(channels=channels, size=size, baseline_cycles=before,
               candidate_cycles=after, saved_percent=100*(1-after/before))
    rows.append(row)
    print(f'{channels}x{size}x{size}: {before} -> {after} cycles, saved {row["saved_percent"]:.2f}%')
(base / 'pool_rows_comparison.json').write_text(json.dumps(rows, indent=2))
print('These are operator RTL latencies. Complete-system timing and frame latency remain separate gates.')
