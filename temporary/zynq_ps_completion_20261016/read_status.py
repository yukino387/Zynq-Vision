import socket,struct,json
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.bind(('169.254.140.109',5003));s.settimeout(2)
s.sendto(struct.pack('<IIII',0x31434e43,0x161001,0,0),('169.254.140.110',5001))
try:
 data,peer=s.recvfrom(2048)
 if len(data)==48 and struct.unpack_from('<I',data)[0]==0x31545343:
  print(json.dumps(dict(zip(['magic','request','device','flags','frame','capture_us','conversion_us','inference_us','transfer_us','cycle_us','errors','brightness'],struct.unpack('<11Ii',data)))))
 else: print(json.dumps({'peer':peer,'bytes':len(data)}))
except TimeoutError: print('NO_STATUS_REPLY')
finally:s.close()
