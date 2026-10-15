import argparse,json,socket,struct,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--tag',default='current');a=p.parse_args()
b=Path(__file__).resolve().parent/'build';b.mkdir(exist_ok=True)
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('169.254.140.109',5003));s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4194304);s.settimeout(.5)
peer=('169.254.140.110',5001);request=0;frames={};status=[]
def receive():
 try: data,addr=s.recvfrom(2048)
 except socket.timeout:return
 if addr!=peer:return
 if len(data)==48 and data[:4]==b'CST1':
  row=struct.unpack('<11Ii',data);status.append(row)
  if row[10]:raise RuntimeError(('board error',row))
  return row
 if len(data)>20 and data[:4]==b'YLO1':
  _,frame,kind,size,offset=struct.unpack('<5I',data[:20])
  if kind!=2:return
  assert size==346112 and offset%1400==0 and len(data)-20==min(1400,size-offset)
  image,offsets=frames.setdefault(frame,(bytearray(size),set()))
  image[offset:offset+len(data)-20]=data[20:];offsets.add(offset)
def command(n,v):
 global request
 request+=1;s.sendto(struct.pack('<IIIi',0x31434e43,request,n,v),peer)
 end=time.monotonic()+3
 while time.monotonic()<end:
  row=receive()
  if row and row[1]==request:return row
 raise TimeoutError(n)
try:
 command(1,0)
 for mode in (1,0):
  command(3,mode);frames.clear();end=time.monotonic()+2
  while time.monotonic()<end:receive()
  complete=[(n,im) for n,(im,offsets) in frames.items() if len(offsets)==248]
  assert len(complete)>=3,(mode,len(complete))
  for n,im in complete[-3:]:
   name=f'{a.tag}_{mode}_{n}';(b/(name+'.rgb565')).write_bytes(im)
   rgb=bytearray()
   for (v,) in struct.iter_unpack('<H',im):
    r=v>>11;g=(v>>5)&63;bl=v&31;rgb.extend(((r<<3)|(r>>2),(g<<2)|(g>>4),(bl<<3)|(bl>>2)))
   (b/(name+'.ppm')).write_bytes(b'P6\n416 416\n255\n'+rgb)
  print('mode',mode,'complete',len(complete),'files',[n for n,_ in complete[-3:]],flush=True)
 command(3,0);command(2,0)
finally:
 (b/(a.tag+'_status.json')).write_text(json.dumps(status,indent=2));s.close()
