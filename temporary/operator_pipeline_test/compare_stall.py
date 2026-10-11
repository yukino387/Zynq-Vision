"""Compare matching RTL convolution cases with randomized interface stalls."""
from pathlib import Path
import json
import re

base = Path(__file__).resolve().parent / 'build'
data = {}
for variant in ('bias_loop','shared44'):
    name = variant + '_wide_stall'
    log = (base / f'{name}_cosim_console.log').read_text(errors='replace')
    assert 'C/RTL co-simulation finished: PASS' in log
    for h in (13,26):
        assert f'CASE h={h} ci=32 co=128 k=3 stride=1 act=1 saturate=0 errors=0' in log
    values = [int(v) for v in re.findall(r'transaction\s+\d+:\s+(\d+)',
              (base / f'{name}.transaction.rpt').read_text())]
    assert len(values) == 2
    data[variant] = values
rows = []
for h, old, new in zip((13,26),data['bias_loop'],data['shared44']):
    row = dict(h=h, ci=32, co=128, baseline_cycles=old, candidate_cycles=new,
               saved_percent=100*(1-new/old))
    rows.append(row)
    print(f'{h}x{h}: {old} -> {new} cycles; saved {row["saved_percent"]:.2f}%')
(base / 'stall_comparison.json').write_text(json.dumps(rows,indent=2))
print('Randomized top-interface stalls, not a model of PS DDR contention. Shared44 still fails the complete-system placement gate.')
