from pathlib import Path
import json,os
lines=[]
for name in ('/run/armpl_board.log','/run/arm-pl-stats-20261027/benchmark.stdout.txt'):
    p=Path(name)
    if p.exists():
        t=p.read_text(errors='replace').strip().splitlines()
        lines.append('--- %s (%d lines) ---'%(name,len(t)))
        lines.extend(t[-4:])
pid=Path('/run/armpl_board.pid')
alive=pid.exists() and Path('/proc',pid.read_text().strip()).exists()
csv=Path('/run/arm-pl-stats-20261027/results/raw_trials.csv')
n=sum(1 for _ in csv.open()) if csv.exists() else 0
print('EXP_POLL alive=%s trial_rows=%d'%(alive,n),flush=True)
for l in lines:print('EXP_POLL '+l,flush=True)
