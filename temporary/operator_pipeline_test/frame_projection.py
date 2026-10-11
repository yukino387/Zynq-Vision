"""Calibrated sensitivity analysis, not an RTL simulation of an entire frame."""
import json
import statistics
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
new_pool = blocks * (10519/2) / 125000
# Keep a conservative common upsampling cost in both variants.
upsample = 183903 / 100000
residual = inference - old[3]/100000 - old_pool - upsample
assert residual > 0
print(f'Calibration: {len(rows)} board records, inference={inference:.3f}ms cycle={cycle:.3f}ms')
print('125MHz requires complete-system timing closure. Projection gives no timing credit for the PS cache optimization.')
for name, pointwise in (('output_phases',16), ('pw24',24)):
    new = traffic.count(26,64,pointwise,True)
    ratio = sum(new[:3]) / sum(old[:3])
    for fixed_share in (0,0.25,0.5,1):
        projected = new[3]/125000 + new_pool + upsample + (cycle-inference)
        projected += residual*(fixed_share+(1-fixed_share)*ratio)
        print(f'{name}: residual fixed share={fixed_share:.0%}: frame={projected:.3f}ms FPS={1000/projected:.3f}')
print('No candidate establishes sub-400ms across overhead assumptions or passes complete-system timing yet.')
