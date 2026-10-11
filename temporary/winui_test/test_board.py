import socket,struct,time,json
from pathlib import Path
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('',5002));s.settimeout(1);s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4194304)
peer=('169.254.140.110',5001);rid=0
stats=[];frames={};completed=[]
def command(c,v):
 global rid
 rid+=1;s.sendto(struct.pack('<IIIi',0x31434e43,rid,c,v),peer)
 end=time.monotonic()+4
 while time.monotonic()<end:
  status=receive()
  if status and status[1]==rid:return status
 raise TimeoutError((c,v))
def receive():
 try:data,_=s.recvfrom(2048)
 except socket.timeout:return
 if len(data)==48 and data[:4]==b'CST1':
  status=struct.unpack('<11Ii',data);stats.append(status);return status
 if len(data)>20 and data[:4]==b'YLO1':
  _,f,k,n,o=struct.unpack('<5I',data[:20]);entry=frames.setdefault(f,{})
  a=entry.setdefault(k,[bytearray(n),set()]);a[0][o:o+len(data)-20]=data[20:];a[1].add(o)
  need=[2] if phase=='preview' else [0,1,2]
  if all(k in entry and len(entry[k][1])==(len(entry[k][0])+1399)//1400 for k in need):
   completed.append((phase,f,time.monotonic()));
   for k in need:Path(f'temporary/winui_test/{phase}_{k}.bin').write_bytes(entry[k][0])
   for old in list(frames):
    if old<=f:del frames[old]
phase='detect';print('discover',command(0,0),flush=True);print('connect',command(1,0),flush=True)
for phase,mode in [('detect',0),('preview',1)]:
 print('mode',command(3,mode),flush=True);frames.clear();start=time.monotonic()
 while time.monotonic()-start<12:receive()
 print(phase,[(p,f) for p,f,t in completed if p==phase],flush=True)
print('brightness',command(4,1),flush=True);print('brightness reset',command(4,0),flush=True)
print('pause',command(2,0),flush=True);print('resume',command(2,1),flush=True);print('detect restore',command(3,0),flush=True)
Path('temporary/winui_test/board_results.json').write_text(json.dumps({'stats':stats,'frames':completed},indent=2));s.close()
