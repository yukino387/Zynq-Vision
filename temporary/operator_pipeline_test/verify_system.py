"""Gate a routed candidate against the actual clock and XC7Z020 resources."""
from pathlib import Path
import re
import sys

base = Path(__file__).resolve().parent / 'build'
variant = sys.argv[1]
mhz = int(sys.argv[2])
target = {142:142.857132,166:166.666672}[mhz]
stage = base / f'{variant}_area_system_{mhz}/build'
assert (stage / 'postroute.dcp').is_file()
log = (base / f'{variant}_area_system_{mhz}_console.log').read_text(errors='replace')
actual = float(re.search(r'^ACTUAL_FCLK_MHZ=([\d.]+)$', log, re.MULTILINE)[1])
assert abs(actual - target) < 0.001
timing = (stage / 'postroute_timing.rpt').read_text()
assert 'Design State : Routed' in timing
summary = timing.split('WNS(ns)',1)[1].splitlines()[2].split()
slack = [float(summary[i]) for i in (0,4,8)]
assert min(slack) >= 0, slack
assert all(int(summary[i]) == 0 for i in (2,6,10)), summary
util = (stage / 'postroute_utilization.rpt').read_text()
resources = {}
for name, limit in (('Slice LUTs',53200), ('Block RAM Tile',140), ('DSPs',220)):
    value = float(re.search(r'\| '+name+r'\s*\|\s*([\d.]+)', util)[1])
    assert value <= limit, (name,value)
    resources[name] = value
skew = (stage / 'postroute_bus_skew.rpt').read_text()
assert 'VIOLATED' not in skew
skew_slack = [float(v) for v in re.findall(r'Slack \(MET\)\s*:\s*([\d.]+)ns',skew)]
assert len(skew_slack) == 2 and min(skew_slack) >= 0
print(f'PASS {variant}: clock={actual}MHz, setup/hold/pulse slack={slack}, bus skew slack={skew_slack}, resources={resources}')
print('Physical implementation gate only; this does not certify frame FPS.')
