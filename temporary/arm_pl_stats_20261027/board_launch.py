from pathlib import Path
import subprocess,urllib.request,json,os
HOST='http://169.254.140.109:28471';http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
src=http.open(HOST+'/board_run.py',timeout=20).read()
p=Path('/run/armpl_board_run.py');p.write_bytes(src)
log=open('/run/armpl_board.log','wb')
proc=subprocess.Popen(['python3',str(p)],stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True,cwd='/run')
Path('/run/armpl_board.pid').write_text(str(proc.pid))
print('LAUNCHED_PID',proc.pid,flush=True)
