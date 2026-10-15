import json
import re
import xml.etree.ElementTree as E
from pathlib import Path

build = Path(__file__).resolve().parent / 'build'
rows = {}
for name in ('a', 'b', 'c', 'd'):
    report = build / name / 'hls/syn/report/conv_csynth.xml'
    if not report.exists():
        continue
    tree = E.parse(report)
    resources = tree.find('.//AreaEstimates/Resources')
    log = (build / f'hls_{name}.log').read_text(errors='replace')
    bursts = [line for line in log.splitlines() if '[HLS 214-115]' in line]
    rows[name] = dict(resources={k: int(resources.findtext(k)) for k in ('LUT', 'FF', 'DSP', 'BRAM_18K')},
                      estimated_clock_ns=tree.findtext('.//EstimatedClockPeriod'),
                      non_ii1=[line for line in log.splitlines() if re.search(r'Final II = (?!1\b)\d+', line)],
                      bursts=bursts)
(build / 'screen.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(json.dumps({k: dict(resources=v['resources'], non_ii1_count=len(v['non_ii1']),
                        burst_count=len(v['bursts'])) for k, v in rows.items()}))
