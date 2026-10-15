import socket,struct,time,zlib,json
from pathlib import Path
b=Path(__file__).resolve().parent/'build';peer=('169.254.140.110',5001)
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('169.254.140.109',5003));s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4194304);s.settimeout(.3)
request=0;phase='startup';frames={};seen=set();counts={};references={};differences={};stats=[];completed=[]
sizes={0:1617,1:6468,2:346112}
def receive():
 try:data,addr=s.recvfrom(2048)
 except socket.timeout:return
 if addr!=peer:return
 if len(data)==48 and data[:4]==b'CST1':
  row=struct.unpack('<11Ii',data);stats.append((phase,row))
  if row[10]:raise RuntimeError(('board',row))
  return row
 if len(data)>20 and data[:4]==b'YLO1':
  _,frame,kind,size,offset=struct.unpack('<5I',data[:20]);assert size==sizes[kind] and offset%1400==0 and len(data)-20==min(1400,size-offset)
  if (frame,kind) in seen:return
  buf,offsets=frames.setdefault((frame,kind),(bytearray(size),set()));buf[offset:offset+len(data)-20]=data[20:];offsets.add(offset)
  if len(offsets)!=(size+1399)//1400:return
  seen.add((frame,kind));del frames[(frame,kind)]
  if phase=='startup' or phase=='preview' and kind!=2:return
  key=f'{phase}_{kind}';counts[key]=counts.get(key,0)+1
  if counts[key]<=3:return
  if key not in references:references[key]=bytes(buf)
  errors=sum(x!=y for x,y in zip(buf,references[key]))
  differences[key]=differences.get(key,0)+errors
  if errors and not (b/(key+'_mismatch.bin')).exists():
   (b/(key+'_mismatch.bin')).write_bytes(buf);(b/(key+'_expected.bin')).write_bytes(references[key])
  if kind==2:completed.append((phase,frame,time.monotonic()))
def command(n,v):
 global request
 request+=1
 for attempt in range(5):
  s.sendto(struct.pack('<IIIi',0x31434e43,request,n,v),peer);end=time.monotonic()+1
  while time.monotonic()<end:
   r=receive()
   if r and r[1]==request:return r
 raise TimeoutError(n)
try:
 command(1,0)
 for phase,mode,duration in [('preview',1,3),('detect',0,5)]:
  command(3,mode);frames.clear();end=time.monotonic()+duration
  while time.monotonic()<end:receive()
  print(phase,{k:v for k,v in counts.items() if k.startswith(phase)},{k:v for k,v in differences.items() if k.startswith(phase)},flush=True)
 command(2,0)
finally:
 result={'frames':counts,'differing_bytes':differences,'status':stats,'completed':completed}
 (b/'full_path_colorbar.json').write_text(json.dumps(result,indent=2))
 for key,value in references.items():(b/(key+'_reference.bin')).write_bytes(value)
 s.close()
assert counts.get('preview_2',0)>60 and counts.get('detect_2',0)>50
assert all(v==0 for v in differences.values()),differences
print('PASS: fixed image and both prediction tensors remain byte-identical on the complete FPGA/UDP path')
