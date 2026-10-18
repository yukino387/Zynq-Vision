import subprocess,hashlib
from pathlib import Path
exe='temporary/zynq_ps_completion_20261016/sha_test.exe'
for data in [b'',b'abc',b'a'*1000000,bytes(range(256))*273,Path('camera/int8/weights.bin').read_bytes()]:
 r=subprocess.run([exe],input=data,capture_output=True,check=True);assert r.stdout.decode()==hashlib.sha256(data).hexdigest(),(len(data),r.stdout)
print('SHA256: 5 reference vectors passed')
