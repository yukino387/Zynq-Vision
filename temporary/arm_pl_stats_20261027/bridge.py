from pathlib import Path
import argparse,base64,gzip,http.server,json,sys,time,threading,urllib.request,urllib.parse

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'board_experiments_20261025/python_deps'))
import serial
HOST='169.254.140.109';PORT=28471
def serve():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            name=urllib.parse.urlsplit(self.path).path.lstrip('/')
            p=(ROOT/name).resolve()
            if not p.is_relative_to(ROOT) or not p.is_file() or 'python_deps' in p.parts:
                self.send_error(404);return
            data=p.read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_POST(self):
            name=urllib.parse.urlsplit(self.path).path.removeprefix('/upload/')
            if self.path.startswith('/upload/') and name and '/' not in name and '\\' not in name:
                length=int(self.headers.get('Content-Length','0'))
                if length>32*1024*1024:self.send_error(413);return
                p=ROOT/'download'/name;p.parent.mkdir(exist_ok=True)
                staged=p.with_name(p.name+'.upload.tmp');staged.write_bytes(self.rfile.read(length));staged.replace(p)
                self.send_response(200);self.end_headers();self.wfile.write(b'OK');return
            self.send_error(404)
        def log_message(self,*_):pass
    server=http.server.ThreadingHTTPServer((HOST,PORT),Handler)
    (ROOT/'bridge.pid').write_text(str(__import__('os').getpid()));print('BRIDGE_READY',HOST,PORT,flush=True);server.serve_forever()

def execute(name,seconds):
    assert '/' not in name and '\\' not in name
    command="python3 -c \"import urllib.request;op=urllib.request.build_opener(urllib.request.ProxyHandler({}));exec(op.open('http://"+HOST+":"+str(PORT)+"/"+name+"',timeout=10).read())\"; echo BOARD_EXPERIMENT_EXIT=$?"
    output=b''
    with serial.Serial('COM15',115200,timeout=.2) as port:
        port.write(b'\r');port.flush();time.sleep(.2);port.read(16384)
        port.write(command.encode()+b'\r');port.flush();end=time.monotonic()+seconds
        while time.monotonic()<end:
            block=port.read(32768)
            if block:
                output+=block
                for line in block.decode('utf8','replace').splitlines():
                    if line.startswith(('EXP_','SNAP_','RESTORE_','BENCH_','Traceback','  File','AssertionError','RuntimeError')):print(line,flush=True)
                if b'BOARD_EXPERIMENT_EXIT=0' in output or b'BOARD_EXPERIMENT_EXIT=1' in output:break
    (ROOT/(name+'.serial.log')).write_bytes(output)
    if b'BOARD_EXPERIMENT_EXIT=0' not in output:
        print(output.decode('utf8','replace')[-3500:],flush=True);raise SystemExit('BOARD_SCRIPT_FAILED_OR_RUNNING')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['serve','exec']);p.add_argument('name',nargs='?');p.add_argument('--timeout',type=int,default=90);a=p.parse_args()
    if a.action=='serve':serve()
    else:execute(a.name,a.timeout)

