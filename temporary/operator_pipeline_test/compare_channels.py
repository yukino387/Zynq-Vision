"""Compare completed paired RTL cases; these are not whole-frame measurements."""
from pathlib import Path
import json
import re

build = Path(__file__).resolve().parent / 'build'
cases = ('CASE h=26 ci=64 co=64 k=3 stride=1 act=1 saturate=0 errors=0',
         'CASE h=13 ci=256 co=75 k=1 stride=1 act=0 saturate=1 errors=0')
results = {}
for variant in ('bias_loop', 'compact'):
    log = (build / (variant+'_channels_cosim_console.log')).read_text(encoding='utf-8')
    assert 'C/RTL co-simulation finished: PASS' in log
    assert all(case in log for case in cases)
    report = (build / (variant+'_channels.transaction.rpt')).read_text()
    rows = re.findall(r'transaction\s+(\d+):\s+(\d+)', report)
    assert [int(index) for index, _ in rows] == [0, 1]
    results[variant] = [int(cycles) for _, cycles in rows]
comparison = []
timing = (build / 'compact_area_system_125/build/timing.rpt').read_text()
summary = timing.split('WNS(ns)', 1)[1].splitlines()[2].split()
wns, whs, wpws = (float(summary[index]) for index in (0, 4, 8))
for case, baseline, candidate in zip(cases, results['bias_loop'], results['compact']):
    saved = 100*(1-candidate/baseline)
    print(f'{case}: baseline={baseline}, candidate={candidate}, cycles saved={saved:.2f}%')
    comparison.append({'case': case, 'baseline_cycles': baseline,
                       'candidate_cycles': candidate, 'saved_percent': saved})
(build / 'channels_comparison.json').write_text(json.dumps({
    'scope': 'Two representative layers, independent AXI testbench ports, no injected DDR stalls',
    'full_system_125mhz_pass': min(wns, whs, wpws) >= 0,
    'full_system_wns_ns': wns,
    'cases': comparison}, indent=2)+'\n')
print(f'No whole-frame FPS claim; compact complete-system WNS={wns:+.3f}ns at 125MHz.')
