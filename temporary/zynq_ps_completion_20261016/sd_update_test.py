import sys,time,json,struct,zlib
from pathlib import Path
sys.path.insert(0,str(Path('camera').resolve()))
from board_control import Board
b=Board()
try:
 original=b.call(0);assert original['flags']&10==10,original
 package=bytearray(Path('camera/build/models/factory/model.bin').read_bytes());version=original['version']+'-CHECK';package[24:88]=version.encode().ljust(64,b'\0');struct.pack_into('<I',package,120,zlib.crc32(package[:120]));b.install(bytes(package))
 second=b.call(0);assert second['version']==version and second['generation']>original['generation']
 b.command(2,0);b.call(5)
 for _ in range(100):
  restored=b.call(0)
  if restored['version']==original['version'] and restored['generation']>second['generation'] and restored['flags']&10==10:break
  time.sleep(.1)
 else:raise AssertionError(restored)
 print(json.dumps({'rollback':'PASS','active':restored}),flush=True)
 bad=bytearray(Path('camera/build/models/factory/model.bin').read_bytes());bad[128]^=1
 b.call(1)
 for offset in range(0,len(bad),1400):b.call(2,offset,bytes(bad[offset:offset+1400]))
 try:b.call(3)
 except RuntimeError as error:
  assert "'result': 4" in str(error),error
 else:raise AssertionError('Bad checksum was accepted')
 after=b.call(0);assert after['version']==restored['version'] and after['sha256']==restored['sha256'] and after['flags']&10==10,after
 print(json.dumps({'checksum_rejection':'PASS','current_model_retained':True,'active':after}),flush=True)
 b.call(6);b.command(2,1)
finally:b.s.close()
