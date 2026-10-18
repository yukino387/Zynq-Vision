"""Control and verify the PS firmware without taking port 5002 from CNN Studio."""
import argparse,hashlib,json,socket,struct,time,zlib
from pathlib import Path
FW_MAGIC,FW_REPLY_MAGIC,FW_ARM_TOKEN=0x314d5246,0x31524d46,0x41524d31
FW_NONE,FW_MAX_ATTEMPTS=0xffffffff,3
class Board:
 def __init__(self,host='169.254.140.110',local_port=5003):
  self.peer=(host,5001);self.s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024);self.s.bind(('0.0.0.0',local_port));self.sequence=100
 def call(self,operation,offset=0,data=b'',attempts=4):
  self.sequence+=1;request=self.sequence;packet=struct.pack('<5I',0x314c444d,request,operation,offset,len(data))+data
  for _ in range(attempts):
   self.s.sendto(packet,self.peer);end=time.monotonic()+5
   while time.monotonic()<end:
    self.s.settimeout(max(.01,end-time.monotonic()))
    try:b,remote=self.s.recvfrom(65536)
    except TimeoutError:break
    if remote==self.peer and len(b)==124 and struct.unpack_from('<II',b)==(0x3152444d,request):
     magic,req,result,received,total,generation,flags=struct.unpack_from('<7I',b)
     info={'result':result,'received':received,'total':total,'generation':generation,'flags':flags,'version':b[28:92].split(b'\0')[0].decode('ascii'),'sha256':b[92:124].hex()}
     if result:raise RuntimeError(f'Model operation {operation} rejected: {info}')
     return info
  raise TimeoutError(f'No model response for operation {operation}')
 def fw_call(self,operation,offset=0,size=0,data=b'',attempts=4,timeout=5):
  self.sequence+=1;request=self.sequence;packet=struct.pack('<5I',FW_MAGIC,request,operation,offset,size)+data
  for _ in range(attempts):
   self.s.sendto(packet,self.peer);end=time.monotonic()+timeout
   while time.monotonic()<end:
    self.s.settimeout(max(.01,end-time.monotonic()))
    try:b,remote=self.s.recvfrom(65536)
    except TimeoutError:break
    if remote==self.peer and len(b)==160 and struct.unpack_from('<II',b)==(FW_REPLY_MAGIC,request):
     magic,req,result,received,total,generation,flags,running_slot,active_slot,previous_slot,pending_slot,attempts_used,max_attempts,stage=struct.unpack_from('<14I',b)
     info={'result':result,'received':received,'total':total,'generation':generation,'flags':flags,'runningSlot':running_slot,'activeSlot':active_slot,'previousSlot':previous_slot,'pendingSlot':pending_slot,'attempts':attempts_used,'maxAttempts':max_attempts,'stage':stage,'version':b[56:112].split(b'\0')[0].decode('ascii'),'sha256':b[112:144].hex(),'slotSizes':list(struct.unpack_from('<2I',b,144))}
     if result:raise RuntimeError(f'Firmware operation {operation} rejected: {info}')
     return info
  raise TimeoutError(f'No firmware response for operation {operation}')
 def firmware_info(self):
  self.command(1);return self.fw_call(0)
 def firmware_install(self,package):
  magic,fmt,header_size,entry,load_addr,image_size,count,version_len,payload_crc,header_crc=struct.unpack_from('<10I',package)
  assert magic==0x31474b50 and fmt==1 and entry==0x100000 and load_addr==0x100000
  assert 1<=count<=4 and header_size==128+16*count and version_len in range(1,56)
  assert len(package)==header_size+image_size and package[72+version_len]==0
  version=package[72:72+version_len].decode('ascii');segments=package[128:128+16*count];payload=package[128+16*count:]
  assert zlib.crc32(package[:36]+package[40:128]+segments)==header_crc
  assert zlib.crc32(payload)==payload_crc
  digest=hashlib.sha256(payload).digest();assert digest==package[40:72]
  expected=0
  for index in range(count):
   paddr,offset,size,flags=struct.unpack_from('<4I',segments,index*16)
   assert offset==expected and size and 0x100000<=paddr<0x200000 and size<=0x200000-paddr
   expected+=size
  assert expected==image_size
  self.command(1);info=self.fw_call(0)
  assert info['flags']&1,'Board firmware does not support PS application OTA'
  assert info['pendingSlot']==FW_NONE and not info['flags']&0x18,'Board has a pending firmware trial'
  target=1 if info['activeSlot']==0 else 0
  started=time.monotonic();self.fw_call(1,FW_ARM_TOKEN,len(package))
  for offset in range(0,len(package),1400):
   chunk=package[offset:offset+1400];reply=self.fw_call(2,offset,len(chunk),chunk,attempts=3)
   assert reply['received']>=offset+len(chunk)
  self.fw_call(3)
  end=time.monotonic()+30
  while time.monotonic()<end:
   info=self.fw_call(0)
   if info['flags']&4:break
   time.sleep(.2)
  else:raise RuntimeError(f'Firmware verification failed: {info}')
  self.fw_call(4);end=time.monotonic()+90;info={}
  while time.monotonic()<end:
   try:info=self.fw_call(0,attempts=1,timeout=2)
   except TimeoutError:continue
   if info['version']==version and info['pendingSlot']==FW_NONE and info['activeSlot']==target:
    print(json.dumps({'installed':info,'seconds':round(time.monotonic()-started,2)}),flush=True);return info
   time.sleep(.5)
  raise RuntimeError(f'Firmware activation failed: {info}')
 def firmware_rollback(self,target):
  self.command(1);info=self.fw_call(0)
  if target=='GOLDEN':slot,code=2,2
  elif info['previousSlot'] in (0,1):slot,code=info['previousSlot'],0
  else:raise RuntimeError('No previous application slot; use GOLDEN')
  self.fw_call(5,code);end=time.monotonic()+90;info={}
  while time.monotonic()<end:
   try:info=self.fw_call(0,attempts=1,timeout=2)
   except TimeoutError:continue
   if info['runningSlot']==slot and info['pendingSlot']==FW_NONE:
    print(json.dumps({'rolledBack':info,'target':target}),flush=True);return info
   time.sleep(.5)
  raise RuntimeError(f'Firmware rollback failed: {info}')
 def command(self,command,value=0):
  self.sequence+=1;req=self.sequence;self.s.sendto(struct.pack('<IIIi',0x31434e43,req,command,value),self.peer);end=time.monotonic()+3
  while time.monotonic()<end:
   self.s.settimeout(max(.01,end-time.monotonic()))
   b,remote=self.s.recvfrom(65536)
   if remote==self.peer and len(b)==48 and struct.unpack_from('<II',b)==(0x31545343,req):return struct.unpack('<11Ii',b)
  raise TimeoutError('No command acknowledgement')
 def install(self,package):
  magic,fmt,w,m,generation,committed=struct.unpack_from('<6I',package)
  assert (magic,fmt,w,m,generation,committed)==(0x314e4e43,1,6350208,66024,0,0)
  assert len(package)==128+w+m and zlib.crc32(package[:120])==struct.unpack_from('<I',package,120)[0]
  digest=hashlib.sha256(package[128:]).digest();assert digest==package[88:120]
  version=package[24:88].split(b'\0')[0].decode('ascii')
  self.command(1);self.command(2,0);self.call(1)
  start=time.monotonic()
  for offset in range(0,len(package),1400):
   reply=self.call(2,offset,package[offset:offset+1400]);assert reply['received']>=min(offset+1400,len(package))
   if offset and offset%1400000==0:print(json.dumps({'uploaded':offset,'total':len(package),'seconds':round(time.monotonic()-start,1)}),flush=True)
  self.call(3);self.call(4)
  end=time.monotonic()+15
  while time.monotonic()<end:
   info=self.call(0)
   if info['version']==version and info['sha256']==digest.hex() and info['flags']&10==10 and not info['flags']&16:
    print(json.dumps({'installed':info,'seconds':round(time.monotonic()-start,2)}),flush=True);self.command(2,1);return info
   time.sleep(.05)
  raise RuntimeError(f'Activation failed: {info}')
 def slots(self):
  self.command(1);info=self.call(0);models=[]
  for slot in range(info['total']):
   entry=self.call(7,slot)
   if not entry['version']:continue
   models.append({'slot':slot,'version':entry['version'],'sha256':entry['sha256'][:16],'active':bool(entry['flags']&0x20),'previous':bool(entry['flags']&0x40)})
  return {'mounted':bool(info['flags']&1),'sdResult':(info['flags']>>8)&0xff,'lastError':(info['flags']>>16)&0xff,'activeSlot':None if info['received']==0xffffffff else info['received'],'capacity':info['total'],'models':models}
 def select(self,slot):
  self.command(1);start=time.monotonic();self.call(8,slot);end=time.monotonic()+15
  while time.monotonic()<end:
   info=self.call(0)
   if info['flags']&8 and not info['flags']&16:
    return {'slot':slot,'version':info['version'],'seconds':round(time.monotonic()-start,2)}
   time.sleep(.05)
  raise RuntimeError(f'Selection failed: {info}')
 def measure(self,seconds,preview_only):
  self.command(1);self.command(3,int(preview_only));self.command(2,1)
  frames={};completed=[];statuses=[];errors=[];start=time.monotonic();end=start+seconds
  self.s.settimeout(.5)
  while time.monotonic()<end:
   try:b,remote=self.s.recvfrom(65536)
   except TimeoutError:continue
   if remote!=self.peer:continue
   if len(b)==48 and struct.unpack_from('<I',b)[0]==0x31545343:
    st=struct.unpack('<11Ii',b);statuses.append(st)
    if st[10]:errors.append(st[10])
   elif len(b)>=20 and struct.unpack_from('<I',b)[0]==0x314f4c59:
    _,frame,kind,total,offset=struct.unpack_from('<5I',b)
    if kind!=2 or total!=346112:continue
    entry=frames.setdefault(frame,set());entry.add(offset)
    if len(entry)==248:
     completed.append((frame,time.monotonic()));del frames[frame]
    if len(frames)>8:del frames[next(iter(frames))]
  fps=(len(completed)-1)/(completed[-1][1]-completed[0][1]) if len(completed)>1 else 0
  result={'mode':'preview' if preview_only else 'inference','seconds':seconds,'complete_frames':len(completed),'fps':round(fps,3),'status_packets':len(statuses),'board_errors':errors,'mean_inference_ms':round(sum(s[7] for s in statuses)/max(1,len(statuses))/1000,3),'mean_cycle_ms':round(sum(s[9] for s in statuses)/max(1,len(statuses))/1000,3)}
  print(json.dumps(result),flush=True);self.command(2,0);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['info','list','install','select','delete','rollback','measure','fw-info','fw-install','fw-rollback']);p.add_argument('--file',type=Path);p.add_argument('--slot',type=int);p.add_argument('--target',choices=['PREVIOUS','GOLDEN'],default='PREVIOUS');p.add_argument('--seconds',type=int,default=15);p.add_argument('--preview-only',action='store_true');p.add_argument('--local-port',type=int,default=5003);a=p.parse_args();b=Board(local_port=a.local_port)
 try:
  if a.action=='info':print(json.dumps(b.call(0)))
  elif a.action=='list':print(json.dumps(b.slots(),ensure_ascii=False))
  elif a.action=='install':b.install(a.file.read_bytes());print(json.dumps(b.slots(),ensure_ascii=False))
  elif a.action=='select':print(json.dumps(b.select(a.slot)))
  elif a.action=='delete':b.command(1);print(json.dumps(b.call(9,a.slot)))
  elif a.action=='measure':b.measure(a.seconds,a.preview_only)
  elif a.action=='fw-info':print(json.dumps(b.firmware_info(),ensure_ascii=False))
  elif a.action=='fw-install':b.firmware_install(a.file.read_bytes())
  elif a.action=='fw-rollback':b.firmware_rollback(a.target)
  else:b.command(1);print(json.dumps(b.call(5)))
 finally:b.s.close()
