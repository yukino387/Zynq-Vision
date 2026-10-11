import socket,struct,time,json
from pathlib import Path
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('',5002));s.settimeout(.5);peer=('169.254.140.110',5001);request=0
results=[]
def send(c,v):
 global request
 request+=1;s.sendto(struct.pack('<IIIi',0x31434e43,request,c,v),peer)
 end=time.monotonic()+4
 while time.monotonic()<end:
  try:d,_=s.recvfrom(2048)
  except socket.timeout:continue
  if len(d)==48 and d[:4]==b'CST1':
   a=struct.unpack('<11Ii',d)
   if a[1]==request:return a
 raise Exception('No acknowledgement')
send(1,0);send(3,1)
for value in [2,0]:
 send(4,value);end=time.monotonic()+3;actual=None
 while time.monotonic()<end:
  try:d,_=s.recvfrom(2048)
  except socket.timeout:continue
  if len(d)==48 and d[:4]==b'CST1':
   a=struct.unpack('<11Ii',d)
   if a[-1]==value:actual=a;break
 assert actual and actual[-2]==0,actual
 results.append({'brightness':actual[-1],'errors':actual[-2]})
send(3,0);s.close();Path('temporary/winui_test/build/brightness.json').write_text(json.dumps(results));print('Brightness applied on board: PASS',results)
