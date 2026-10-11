"""Measure operator-cycle changes; this is not a PS DDR or whole-frame model."""
from pathlib import Path
import re

base = Path(__file__).resolve().parent / 'build'
cases = (
    'CASE h=26 ci=3 co=64 k=3 stride=2 act=1 saturate=0 errors=0',
    'CASE h=13 ci=32 co=128 k=3 stride=1 act=1 saturate=0 errors=0',
    'CASE h=26 ci=8 co=32 k=3 stride=1 act=0 saturate=0 errors=0',
    'CASE h=13 ci=64 co=75 k=1 stride=1 act=0 saturate=1 errors=0',
    'RESIZE kernel=2 channels=4 h=104 errors=0',
    'RESIZE kernel=0 channels=128 h=13 errors=0',
)
data = []
for name in ('shared44_single', 'shared44_single_fast'):
    log = (base / f'{name}_mixed_stall_cosim_console.log').read_text(errors='replace')
    assert 'C/RTL co-simulation finished: PASS' in log
    assert all(case in log for case in cases)
    values = [int(v) for v in re.findall(r'transaction\s+\d+:\s+(\d+)',
              (base / f'{name}_mixed_stall.transaction.rpt').read_text())]
    assert len(values) == len(cases) and min(values) > 0
    data.append(values)
for case, old, new in zip(cases, *data):
    print(f'{case}: {old} -> {new} cycles, change={100*(new/old-1):+.3f}%')
print('Max observed cycle growth:', max(new/old-1 for old,new in zip(*data)))
print('Matching randomized interface-stall cases; no board FPS claim. Physical timing qualification is separate.')
