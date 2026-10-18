from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import hashlib, json, mmap, os, struct, zlib

def registers(address, offsets):
    fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=address) as memory:
            return {hex(offset):struct.unpack_from('<I',memory,offset)[0] for offset in offsets}
    finally: os.close(fd)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,body):
        self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def allowed(self):
        if self.client_address[0]!='169.254.140.109':
            self.send_error(403);return False
        return True
    def do_GET(self):
        if not self.allowed(): return
        if self.path=='/metrics':
            gray=registers(0x41210000,[0])['0x0'];binary=0;value=gray
            while value: binary^=value;value>>=1
            self.send(json.dumps({'underflows':binary,'gray':gray,'vdma':registers(0x43000000,[0,4,0x28,0x50,0x54,0x58,0x5c,0x60])}).encode())
        elif self.path=='/framebuffer':
            with open('/dev/fb0','rb') as stream: self.send(zlib.compress(stream.read(7372800),1))
        else: self.send_error(404)
    def do_PUT(self):
        if not self.allowed(): return
        length=int(self.headers.get('Content-Length','0'))
        if self.path!='/panel' or not 0<length<32*1024*1024:
            self.send_error(400);return
        data=self.rfile.read(length)
        digest=hashlib.sha256(data).hexdigest()
        if len(data)!=length or data[:5]!=b'\x7fELF\x01' or digest!=self.headers.get('X-SHA256'):
            self.send_error(400);return
        path=Path('/tmp/vision-panel-upload')
        path.write_bytes(data);path.chmod(0o755)
        self.send(json.dumps({'bytes':length,'sha256':digest}).encode())

HTTPServer.allow_reuse_address=True
HTTPServer(('169.254.140.110',9088),Handler).serve_forever()
