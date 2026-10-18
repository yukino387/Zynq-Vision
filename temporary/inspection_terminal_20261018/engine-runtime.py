import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
import uuid
import zipfile

task=Path('/workspace/temporary/inspection_terminal_20261018')
root=Path('/opt/vision/engine-fixture-'+str(time.time_ns()))
root.mkdir();(root/'jobs').mkdir();(root/'frame').write_text('1')
run=sorted(task.glob('run-*'))[-1]
with zipfile.ZipFile(run/'job.zip') as archive:
    job=json.loads(archive.read('job.json'));folder=root/'jobs'/job['id'];folder.mkdir();archive.extractall(folder)
log=open(task/'engine-runtime.stdout.log','w')
process=None
server=None
transport={'valid':False,'unavailable':False,'requests':0}

class Receiver(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        assert self.path=='/api/terminal/records' and self.headers['Authorization']=='Bearer fixture-token'
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])));transport['requests']+=1
        receipt={'id':'terminal:'+job['deviceId']+':'+payload['bootId']+':'+str(payload['sequence']),'rawSha256':payload['rawSha256']}
        if not transport['valid']:receipt['id']='incorrect-acknowledgement'
        self.send_response(503 if transport['unavailable'] else 201);self.end_headers();self.wfile.write(json.dumps(receipt).encode())

def wait_state(condition):
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        state=request('/state')[1]
        if condition(state):return state
        time.sleep(.15)
    raise RuntimeError('Expected transport state did not arrive: '+str(state))

def start():
    global process
    env=dict(os.environ,VISION_ENGINE_TEST_ROOT=str(root))
    process=subprocess.Popen(['qemu-arm','-cpu','cortex-a9','-L','/usr/arm-linux-gnueabihf',str(task/'vision-engine-fixture'),str(root),str(root/'jobs')],env=env,stdout=log,stderr=log)
    for _ in range(100):
        if process.poll() is not None:raise RuntimeError('Fixture engine exited')
        try:
            status,_=request('/state')
            if status==200:return
        except (URLError,ConnectionError):pass
        time.sleep(.05)
    raise RuntimeError('Engine startup timed out')

def stop():
    if process and process.poll() is None:
        process.send_signal(signal.SIGTERM);process.wait(timeout=15)

def request(path,payload=None):
    req=Request('http://127.0.0.1:8877'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'content-type':'application/json'})
    try:
        with urlopen(req,timeout=5) as response:return response.status,json.load(response)
    except HTTPError as error:return error.code,json.load(error)

def advance(generation):
    (root/'frame').write_text(str(generation))
    for _ in range(50):
        _,state=request('/state')
        if state['frameId']==generation and state['fresh']:return
        time.sleep(.03)
    raise RuntimeError('Frame did not advance')

try:
    start();assert request('/select',{'id':job['id']})[0]==200;advance(1)
    operation=str(uuid.uuid4());status,first=request('/check',{'requestId':operation});assert status==200 and first['saved']
    assert request('/check',{'requestId':operation})==(200,first)
    status,rejected=request('/check',{'requestId':str(uuid.uuid4())});assert status==409 and rejected['mayHaveSaved'] is False
    boot=next((root/'records').glob('*.json')).name.rsplit('-',1)[0]
    blocked=root/'records'/(boot+'-2.json');blocked.mkdir();advance(2)
    pending=str(uuid.uuid4());status,error=request('/check',{'requestId':pending});assert status==409 and error['mayHaveSaved'] is True
    assert request('/state')[1]['total']==1
    assert request('/check',{'requestId':str(uuid.uuid4())})[0]==409
    blocked.rmdir();status,recovered=request('/check',{'requestId':pending});assert status==200 and recovered['sequence']==2 and recovered['findings']
    assert request('/state')[1]['total']==2 and request('/state')[1]['last']['sequence']==2
    stop();start();assert request('/check',{'requestId':pending})==(200,recovered);assert request('/state')[1]['total']==2
    (root/'fail-model').touch();assert request('/select',{'id':job['id']})[0]==409
    state=request('/state')[1];assert state['job'] is None and state['paused'] and not state['fresh']
    assert request('/check',{'requestId':str(uuid.uuid4())})[0]==409
    (root/'fail-model').unlink();assert request('/select',{'id':job['id']})[0]==200
    HTTPServer.allow_reuse_address=True
    server=HTTPServer(('127.0.0.1',38882),Receiver);threading.Thread(target=server.serve_forever,daemon=True).start()
    (root/'connection.json').write_text(json.dumps({'server':'http://127.0.0.1:38882','token':'fixture-token','deviceId':job['deviceId']}))
    state=wait_state(lambda s:'acknowledgement mismatch' in s['syncError']);assert state['pendingSync']==2
    transport['valid']=True;wait_state(lambda s:s['pendingSync']==0)
    stop();transport['unavailable']=True
    ack=next((root/'records').glob('*.ack'));receipt=json.loads(ack.read_text());receipt['rawSha256']='0'*64;ack.write_text(json.dumps(receipt))
    start();state=wait_state(lambda s:bool(s['syncError']));assert state['pendingSync']==1
    transport['unavailable']=False;wait_state(lambda s:s['pendingSync']==0);assert transport['requests']>=5
    stop()
    evidence=next((root/'records').glob('*.json'));saved=json.loads(evidence.read_text());saved['requestId']=str(uuid.uuid4());evidence.write_text(json.dumps(saved))
    env=dict(os.environ,VISION_ENGINE_TEST_ROOT=str(root))
    corrupt=subprocess.run(['qemu-arm','-cpu','cortex-a9','-L','/usr/arm-linux-gnueabihf',str(task/'vision-engine-fixture'),str(root),str(root/'jobs')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert corrupt.returncode!=0 and b'checksum mismatch' in corrupt.stderr
    print('ARM engine fixture passed: idempotency, duplicate-frame guard, storage failure/retry, restart recovery, model-switch failure, acknowledgement mismatch/retry, corrupt receipt recovery and checksum rejection')
finally:
    stop();log.close()
    if server:server.shutdown();server.server_close()
