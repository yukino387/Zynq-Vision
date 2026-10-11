"""Calibrated sensitivity analysis, not an RTL simulation of an entire frame."""
import json
import statistics
import re
from pathlib import Path
import traffic

root = Path(__file__).resolve().parents[2]
rows = json.loads((root / 'temporary/winui_test/board_results.json').read_text())['stats']
rows = [r for r in rows if len(r) == 12 and r[1] == 0 and r[3] & 1 and not r[3] & 2 and r[7] > 0]
assert rows
inference = statistics.median(r[7] for r in rows) / 1000
cycle = statistics.median(r[9] for r in rows) / 1000
old = traffic.count(13,32,8)
# Same 26x26, eight-channel pooling case: baseline 10488 cycles;
# candidate four-transaction sequence 10519 cycles. Two 4-channel blocks.
blocks = sum((2*co//4)*(h//26)*(w//26)
             for _, (h,w,ci,co) in traffic.constructors('cspdarknet.cpp','Resblock_body'))
old_pool = blocks * (10488/2) / 100000
frequency = 142857.132
new_pool = blocks * (10521/2) / frequency
test = Path(__file__).resolve().parent / 'build'
pool_rows = [int(value) for value in re.findall(r'transaction\s+\d+:\s+(\d+)',
             (test / 'pool_rows.transaction.rpt').read_text())]
assert len(pool_rows) == 3
row_cost = dict(zip((26,52,104), (pool_rows[0]/8,pool_rows[1]/8,pool_rows[2]/4)))
row_pool = sum(2*co*row_cost[h] for _, (h,w,ci,co) in
               traffic.constructors('cspdarknet.cpp','Resblock_body')) / frequency
# Keep a conservative common upsampling cost in both variants.
upsample = 183903 / 100000
residual = inference - old[3]/100000 - old_pool - upsample
assert residual > 0
print(f'Calibration: {len(rows)} board records, inference={inference:.3f}ms cycle={cycle:.3f}ms')
print('Actual candidate clock: 142.857132MHz. Projection gives no timing credit for the PS cache optimization.')
for name, config, pooling in (('shared_dsp',(26,64,64,True,True),new_pool),
                              ('pool_rows',(26,64,64,True,True),row_pool),
                              ('shared44',(26,88,88,True,True,44,True),row_pool)):
    gate = test / f'{name}_area_system_142/build/postroute_timing.rpt'
    if gate.is_file():
        summary = gate.read_text().split('WNS(ns)',1)[1].splitlines()[2].split()
        qualified = min(float(summary[i]) for i in (0,4,8)) >= 0
        print(f'{name}: complete-system timing pass={qualified}, WNS={summary[0]}ns')
    else:
        print(f'{name}: complete-system timing is not qualified yet')
    new = traffic.count(*config)
    ratio = sum(new[:3]) / sum(old[:3])
    for fixed_share in (0,0.25,0.5,1):
        projected = new[3]/frequency + pooling + upsample + (cycle-inference)
        projected += residual*(fixed_share+(1-fixed_share)*ratio)
        print(f'{name}: residual fixed share={fixed_share:.0%}: frame={projected:.3f}ms FPS={1000/projected:.3f}')
print('No whole-frame RTL or board measurement. The residual model includes control/memory stalls and cache work; scaling it by scheduled traffic is an assumption.')
print('No candidate establishes sub-400ms across all residual-overhead assumptions.')
