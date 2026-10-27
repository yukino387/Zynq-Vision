from pathlib import Path
import urllib.request,json,hashlib
HOST='http://169.254.140.109:28471';http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
ROOT=Path('/run/arm-pl-stats-20261027')
def push(name,data):
    http.open(urllib.request.Request(HOST+'/upload/'+name,data=data,method='POST'),timeout=60).read()
items=[]
res=ROOT/'results'
if res.exists():items+=sorted(res.iterdir())
for extra in ('benchmark.stdout.txt','guard.log'):
    p=ROOT/extra
    if p.exists():items.append(p)
if not items:
    print('EXP_FETCH_EMPTY',flush=True)
for p in items:
    if not p.is_file():continue
    data=p.read_bytes();push(p.name,data)
    print('EXP_FETCHED %s %d %s'%(p.name,len(data),hashlib.sha256(data).hexdigest()[:16]),flush=True)
print('EXP_FETCH_DONE %d'%len(items),flush=True)
