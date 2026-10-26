from pathlib import Path
import os,signal,time,subprocess,json,hashlib,urllib.request,tarfile,io,mmap,struct
HOST='http://169.254.140.109:28471';http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
root=Path('/run/headless-arm-pl-20261026');root.mkdir(exist_ok=False)
def upload(name,value):
    data=value if isinstance(value,bytes) else json.dumps(value,indent=2).encode()
    http.open(urllib.request.Request(HOST+'/upload/'+name,data=data,method='POST'),timeout=25).read()
def state():return json.load(http.open('http://127.0.0.1:8877/state',timeout=5))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def reg(a,value=None):
    fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC)
    try:
        with mmap.mmap(fd,4096,offset=a&~4095) as m:
            if value is not None:struct.pack_into('<I',m,a&4095,value)
            return struct.unpack_from('<I',m,a&4095)[0]
    finally:os.close(fd)
def service_pids():
    found=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            comm=(p/'comm').read_text().strip();cmd=(p/'cmdline').read_bytes()
            if comm in ('vision-engine','vision-panel') or b'/usr/local/bin/vision-manager.py' in cmd:found.append(int(p.name))
        except OSError:pass
    return found
original=state();assert original['fresh'] and not original['production'] and not original['error'] and not original.get('pendingRequestId')
plan=json.load(http.open(HOST+'/plan.json'));assert original['model']['weightsSha256']==plan['modelSha256']
assert reg(0xf800000c)==0 and reg(0xf8000170)==0x200400
original_log=subprocess.check_output(['dmesg'],text=True)
assert 'I/O error' not in original_log,'Prior SD error present; do not benchmark an unresolved active fault'
persistent={p:sha(p) for p in ('/boot/BOOT.bin','/usr/local/bin/vision-panel','/usr/local/bin/vision-engine','/var/lib/vision/model/model.bin','/var/lib/vision/product.json','/etc/inittab')}
data=http.open(HOST+'/fixed_bench.arm').read();assert hashlib.sha256(data).hexdigest()==plan['binarySha256'];binary=root/'fixed_bench.arm';binary.write_bytes(data);binary.chmod(0o755)
manifest=json.load(http.open(HOST+'/input_manifest.json'));frames=root/'inputs';frames.mkdir()
with tarfile.open(fileobj=io.BytesIO(http.open(HOST+'/inputs.tar.gz').read()),mode='r:gz') as tar:
    for member in tar.getmembers():
        assert member.isfile() and '/' not in member.name
        (frames/member.name).write_bytes(tar.extractfile(member).read())
for c in manifest['cases']:assert sha(frames/(c['name']+'.rgb565'))==c['rgb565Sha256']
(frames/'manifest.json').write_text(json.dumps(manifest))
init=Path('/etc/inittab');saved=init.read_bytes();filtered=root/'inittab.filtered';filtered.write_bytes(b'\n'.join(x for x in saved.splitlines() if not any(n in x for n in (b'vision-engine',b'vision-panel',b'vision-manager')))+b'\n')
gov=Path('/sys/devices/system/cpu/cpufreq/policy0/scaling_governor');saved_gov=gov.read_text().strip()
cfg={'runner':os.getpid(),'child':None,'mounted':False,'governor':saved_gov}
def guard_save():(root/'guard.json').write_text(json.dumps(cfg))
guard_save()
guard_code=r'''
import os,time,json,signal,subprocess
from pathlib import Path
root=Path('/run/headless-arm-pl-20261026');end=time.monotonic()+650
while not (root/'done').exists():
 try:c=json.loads((root/'guard.json').read_text())
 except Exception:time.sleep(1);continue
 if not Path('/proc',str(c['runner'])).exists() or time.monotonic()>end:
  if c.get('child'):
   try:os.kill(c['child'],signal.SIGTERM)
   except ProcessLookupError:pass
   time.sleep(2)
  if not Path('/sys/module/vision_fb').exists():subprocess.run(['modprobe','vision_fb'])
  if c.get('mounted'):subprocess.run(['umount','/etc/inittab'])
  Path('/sys/devices/system/cpu/cpufreq/policy0/scaling_governor').write_text(c['governor'])
  os.kill(1,signal.SIGHUP);(root/'watchdog-restored').write_text('restored');break
 time.sleep(1)
'''
(root/'guard.py').write_text(guard_code);guard_log=(root/'guard.log').open('wb');guard=subprocess.Popen(['python3',str(root/'guard.py')],stdout=guard_log,stderr=guard_log,start_new_session=True)
child=None;unloaded=False;stopped_gpio=None
upload('before.json',{'state':original,'persistentHashes':persistent,'governor':saved_gov,'dmesg':original_log})
try:
    subprocess.run(['mount','--bind',str(filtered),str(init)],check=True);cfg['mounted']=True;guard_save();os.kill(1,signal.SIGHUP);time.sleep(.5)
    for pid in service_pids():
        try:os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:pass
    deadline=time.monotonic()+20
    while service_pids():
        if time.monotonic()>deadline:raise RuntimeError('Runtime services did not stop')
        time.sleep(.2)
    assert reg(0x40400030)&1==0,'Capture DMA still running'
    stopped_gpio=reg(0x41200000);reg(0x41200000,(stopped_gpio|8)&~16)
    subprocess.run(['modprobe','-r','vision_fb'],check=True);unloaded=True
    assert not Path('/sys/module/vision_fb').exists() and reg(0x43000000)&1==0
    gov.write_text('performance');time.sleep(.2)
    env={'cpuCurrentKHz':Path('/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq').read_text().strip(),'governor':'performance','captureDmaControl':reg(0x40400030),'displayDmaControl':reg(0x43000000),'gpioControl':reg(0x41200000),'fclk0':reg(0xf8000170),'framebufferDriverLoaded':False,'runtimeServicePids':service_pids(),'scope':plan['scope'],'benchmarkSha256':sha(binary),'modelSha256':sha('/var/lib/vision/model/model.bin')}
    upload('environment.json',env);print('EXP_HEADLESS_READY',json.dumps(env),flush=True)
    out=root/'results';child=subprocess.Popen([str(binary),'/var/lib/vision/model/model.bin',str(frames/'manifest.json'),str(out)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
    cfg['child']=child.pid;guard_save()
    with (root/'benchmark.stdout.txt').open('w') as log:
        for line in child.stdout:log.write(line);log.flush();print(line.strip(),flush=True)
    code=child.wait();cfg['child']=None;guard_save()
    upload('benchmark.stdout.txt',(root/'benchmark.stdout.txt').read_bytes())
    if out.exists():
        for p in out.iterdir():
            if p.is_file():upload(p.name,p.read_bytes())
    assert code==0,'Benchmark failed'
    result=json.loads((out/'fixed_results.json').read_text());assert len(result['cases'])==3 and all(c['mismatches']==0 for c in result['cases'])
    upload('completed.json',{'cases':3,'int8Equal':True,'bytesPerOutput':8085,'headless':True,'allMeasuredSamplesRetained':True})
finally:
    if child is not None and child.poll() is None:child.terminate();child.wait(timeout=10)
    if stopped_gpio is not None:reg(0x41200000,stopped_gpio&~16)
    if unloaded and not Path('/sys/module/vision_fb').exists():subprocess.run(['modprobe','vision_fb'],check=True)
    if cfg['mounted']:subprocess.run(['umount',str(init)],check=True);cfg['mounted']=False;guard_save()
    gov.write_text(saved_gov);os.kill(1,signal.SIGHUP)
    end=time.monotonic()+35;after=None
    while time.monotonic()<end:
        try:
            after=state()
            if after['fresh'] and not after['error']:break
        except Exception:pass
        time.sleep(.3)
    assert after and after['fresh'] and not after['error'] and not after['production']
    for k in ('model','product','counts','total'):assert after[k]==original[k],k
    assert all(sha(p)==v for p,v in persistent.items()) and init.read_bytes()==saved
    new_log=subprocess.check_output(['dmesg'],text=True)
    upload('restored.json',{'state':after,'governor':gov.read_text().strip(),'persistentHashes':persistent,'framebufferDriverLoaded':Path('/sys/module/vision_fb').exists(),'slcrLock':reg(0xf800000c),'newSdIoError':'I/O error' in new_log,'dmesg':new_log,'watchdogTriggered':(root/'watchdog-restored').exists()})
    (root/'done').write_text('restored');guard.wait(timeout=4);print('RESTORE_HEADLESS_PASS',flush=True)
