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
test = Path(__file__).resolve().parent / 'build'
pool_rows = [int(value) for value in re.findall(r'transaction\s+\d+:\s+(\d+)',
             (test / 'pool_rows.transaction.rpt').read_text())]
assert len(pool_rows) == 3
row_cost = dict(zip((26,52,104), (pool_rows[0]/8,pool_rows[1]/8,pool_rows[2]/4)))
row_pool_cycles = sum(2*co*row_cost[h] for _, (h,w,ci,co) in
                      traffic.constructors('cspdarknet.cpp','Resblock_body'))
fast_log = (test / 'shared44_single_fast_boundary_stall_cosim_console.log').read_text(errors='replace')
assert 'C/RTL co-simulation finished: PASS' in fast_log
fast = [int(value) for value in re.findall(r'transaction\s+\d+:\s+(\d+)',
        (test / 'shared44_single_fast_boundary_stall.transaction.rpt').read_text())]
assert len(fast) == 6
for channels,h in ((8,26),(8,52),(4,104)):
    assert f'RESIZE kernel=2 channels={channels} h={h} errors=0' in fast_log
fast_row_cost = dict(zip((26,52,104), (fast[3]/8,fast[4]/8,fast[5]/4)))
fast_pool_cycles = sum(2*co*fast_row_cost[h] for _, (h,w,ci,co) in
                       traffic.constructors('cspdarknet.cpp','Resblock_body'))
read_log = (test / 'shared44_read_lanes_pool_stall_cosim_console.log').read_text(errors='replace')
assert 'C/RTL co-simulation finished: PASS' in read_log
read_pool = [int(value) for value in re.findall(r'transaction\s+\d+:\s+(\d+)',
             (test / 'shared44_read_lanes_pool_stall.transaction.rpt').read_text())]
assert len(read_pool) == 3
for channels,h in ((8,26),(8,52),(4,104)):
    assert f'RESIZE kernel=2 channels={channels} h={h} errors=0' in read_log
read_row_cost = dict(zip((26,52,104), (read_pool[0]/8,read_pool[1]/8,read_pool[2]/4)))
read_pool_cycles = sum(2*co*read_row_cost[h] for _, (h,w,ci,co) in
                       traffic.constructors('cspdarknet.cpp','Resblock_body'))
rows_log = (test / 'shared44_read_rows_pool_stall_cosim_console.log').read_text(errors='replace')
assert 'C/RTL co-simulation finished: PASS' in rows_log
rows_pool = [int(value) for value in re.findall(r'transaction\s+\d+:\s+(\d+)',
             (test / 'shared44_read_rows_pool_stall.transaction.rpt').read_text())]
assert len(rows_pool) == 3
for channels,h in ((8,26),(8,52),(4,104)):
    assert f'RESIZE kernel=2 channels={channels} h={h} errors=0' in rows_log
rows_cost = dict(zip((26,52,104), (rows_pool[0]/8,rows_pool[1]/8,rows_pool[2]/4)))
rows_pool_cycles = sum(2*co*rows_cost[h] for _, (h,w,ci,co) in
                       traffic.constructors('cspdarknet.cpp','Resblock_body'))
# Keep a conservative common upsampling cost in both variants.
upsample = 183903 / 100000
residual = inference - old[3]/100000 - old_pool - upsample
assert residual > 0
print(f'Calibration: {len(rows)} board records, inference={inference:.3f}ms cycle={cycle:.3f}ms')
print('Projection gives no timing credit for the PS cache optimization.')
for name, config, pool_cycles, mhz in (
        ('shared_dsp',(26,64,64,True,True),blocks*(10521/2),142.857132),
        ('pool_rows',(26,64,64,True,True),row_pool_cycles,142.857132),
        ('shared44',(26,88,88,True,True,44,True),row_pool_cycles,142.857132),
        ('shared44_narrow',(26,88,88,True,True,44,True),row_pool_cycles,166.666672),
        ('shared44_single',(26,44,44,True,True,44,True),row_pool_cycles,166.666672),
        ('shared44_single_fast',(26,44,44,True,True,44,True),fast_pool_cycles,166.666672),
        ('shared44_read_lanes',(26,44,44,True,True,44,True),read_pool_cycles,166.666672),
        ('shared44_read_rows',(26,44,44,True,True,44,True),rows_pool_cycles,166.666672)):
    frequency = mhz * 1000
    pooling = pool_cycles / frequency
    gate = test / f'{name}_area_system_{int(mhz)}/build/postroute_timing.rpt'
    if gate.is_file():
        summary = gate.read_text().split('WNS(ns)',1)[1].splitlines()[2].split()
        qualified = min(float(summary[i]) for i in (0,4,8)) >= 0
        print(f'{name}: complete-system timing pass={qualified}, WNS={summary[0]}ns')
    else:
        print(f'{name}: complete-system timing is not qualified yet')
    new = traffic.count(*config)
    ratio = sum(new[:3]) / sum(old[:3])
    # Observed retiming growth is below 1% in matching RTL cases. This 2%
    # allowance is engineering margin, not a proven bound on untested layers.
    retiming_margin = new[3]/frequency * 0.02 if name in ('shared44_single_fast','shared44_read_lanes','shared44_read_rows') else 0
    print(f'{name}: clock={mhz:.6f}MHz, ideal convolution={new[3]/frequency:.3f}ms, pooling={pooling:.3f}ms')
    if retiming_margin:
        print(f'{name}: additional empirical retiming allowance={retiming_margin:.3f}ms')
    for fixed_share in (0,0.25,0.5,1):
        projected = new[3]/frequency + retiming_margin + pooling + upsample + (cycle-inference)
        projected += residual*(fixed_share+(1-fixed_share)*ratio)
        print(f'{name}: residual fixed share={fixed_share:.0%}: frame={projected:.3f}ms FPS={1000/projected:.3f}')
    print(f'{name}: margin below 400ms with all old overhead retained={400-projected:.3f}ms')
print('No whole-frame RTL or board measurement. The residual model includes control/memory stalls and cache work; scaling it by scheduled traffic is an assumption.')
print('A sub-400ms projection still requires physical qualification and assumes the new memory/control overhead does not exceed the retained baseline overhead.')
