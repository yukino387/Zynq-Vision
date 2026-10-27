from pathlib import Path
import os,signal,time,subprocess,json,hashlib,urllib.request,tarfile,io,mmap,struct
HOST='http://169.254.140.109:28471';http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
ROOT=Path('/run/arm-pl-stats-20261027')
import shutil
if ROOT.exists(): shutil.rmtree(ROOT,ignore_errors=True)
ROOT.mkdir(parents=True)
def upload(name,value):
    data=value if isinstance(value,bytes) else json.dumps(value,indent=2).encode()
    for _ in range(3):
        try:
            http.open(urllib.request.Request(HOST+'/upload/'+name,data=data,method='POST'),timeout=30).read();return True
        except Exception:
            time.sleep(1)
    print('EXP_UPLOAD_FAIL',name,flush=True);return False
def get(name):
    return http.open(HOST+'/'+name,timeout=40).read()
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
mode=get('mode.txt').decode().strip();assert mode in ('smoke','full'),mode
plan=json.loads(get('plan.json'));schedule_name='schedule_smoke.json' if mode=='smoke' else 'schedule.json'
print('EXP_MODE',mode,schedule_name,flush=True)
original=state();assert original['fresh'] and not original['production'] and not original['error'] and not original.get('pendingRequestId')
assert original['model']['weightsSha256']==plan['modelSha256'],'Model hash mismatch'
assert reg(0xf800000c)==0 and reg(0xf8000170)==0x200400
original_log=subprocess.check_output(['dmesg'],text=True)
assert 'I/O error' not in original_log,'Prior SD error present; do not benchmark an unresolved active fault'
persistent={p:sha(p) for p in ('/boot/BOOT.bin','/usr/local/bin/vision-panel','/usr/local/bin/vision-engine','/var/lib/vision/model/model.bin','/var/lib/vision/product.json','/etc/inittab')}
data=get('bench_stat.arm');assert hashlib.sha256(data).hexdigest()==plan['binarySha256'],'Benchmark binary hash mismatch'
binary=ROOT/'bench_stat.arm';binary.write_bytes(data);binary.chmod(0o755)
schedule_bytes=get(schedule_name)
assert hashlib.sha256(schedule_bytes).hexdigest()==plan[('scheduleSmokeSha256' if mode=='smoke' else 'scheduleSha256')],'Schedule hash mismatch'
(ROOT/'schedule.json').write_bytes(schedule_bytes)
manifest_bytes=get('input_manifest.json');manifest=json.loads(manifest_bytes);frames=ROOT/'inputs';frames.mkdir()
with tarfile.open(fileobj=io.BytesIO(get('inputs.tar.gz')),mode='r:gz') as tar:
    for member in tar.getmembers():
        assert member.isfile() and '/' not in member.name
        (frames/member.name).write_bytes(tar.extractfile(member).read())
for c in manifest['cases']:assert sha(frames/(c['name']+'.rgb565'))==c['rgb565Sha256']
(frames/'manifest.json').write_bytes(manifest_bytes)
init=Path('/etc/inittab');saved=init.read_bytes()
filtered=ROOT/'inittab.filtered'
filtered.write_bytes(b'\n'.join(x for x in saved.splitlines() if not any(n in x for n in (b'vision-engine',b'vision-panel',b'vision-manager')))+b'\n')
gov=Path('/sys/devices/system/cpu/cpufreq/policy0/scaling_governor');saved_gov=gov.read_text().strip()
cfg={'runner':os.getpid(),'child':None,'mounted':False,'governor':saved_gov}
def guard_save():(ROOT/'guard.json').write_text(json.dumps(cfg))
guard_save()
guard_code=r'''
import os,time,json,signal,subprocess
from pathlib import Path
root=Path('/run/arm-pl-stats-20261027');end=time.monotonic()+2400
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
(ROOT/'guard.py').write_text(guard_code);guard_log=(ROOT/'guard.log').open('wb')
guard=subprocess.Popen(['python3',str(ROOT/'guard.py')],stdout=guard_log,stderr=guard_log,start_new_session=True)
child=None;unloaded=False;stopped_gpio=None
upload('before.json',{'state':original,'persistentHashes':persistent,'governor':saved_gov,'mode':mode})
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
    env={'mode':mode,'cpuCurrentKHz':Path('/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq').read_text().strip(),
         'governor':'performance','captureDmaControl':reg(0x40400030),'displayDmaControl':reg(0x43000000),
         'gpioControl':reg(0x41200000),'fclk0':reg(0xf8000170),'framebufferDriverLoaded':False,
         'runtimeServicePids':service_pids(),'benchmarkSha256':sha(binary),'modelSha256':sha('/var/lib/vision/model/model.bin'),
         'thermalZone':Path('/sys/class/thermal/thermal_zone0/temp').read_text().strip() if Path('/sys/class/thermal/thermal_zone0/temp').exists() else '',
         'kernel':' '.join(Path('/proc/version').read_text().split()[2:3]),
         'scope':plan['scope']}
    upload('environment.json',env);print('EXP_HEADLESS_READY',json.dumps(env),flush=True)
    out=ROOT/'results'
    child=subprocess.Popen([str(binary),'/var/lib/vision/model/model.bin',str(frames/'manifest.json'),str(out),str(ROOT/'schedule.json')],
                           stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
    cfg['child']=child.pid;guard_save()
    with (ROOT/'benchmark.stdout.txt').open('w') as log:
        for line in child.stdout:
            log.write(line);log.flush()
            if line.startswith(('BENCH_INPUT','BENCH_CAL','BENCH_META','BENCH_ERROR','BENCH_CASE','Traceback')):print(line.strip(),flush=True)
    code=child.wait();cfg['child']=None;guard_save()
    print('EXP_BENCH_EXIT',code,flush=True)
    for p in sorted((ROOT/'results').glob('*')) if (ROOT/'results').exists() else []:
        if p.is_file():upload(p.name,p.read_bytes())
    upload('benchmark.stdout.txt',(ROOT/'benchmark.stdout.txt').read_bytes())
    if code!=0:raise RuntimeError('Benchmark exited with %d'%code)
    meta=json.loads((ROOT/'results'/'run_meta.json').read_text())
    upload('completed.json',{'mode':mode,'counts':meta['counts'],'truncated':meta['truncated'],'macs':meta['macs'],'outputBytes':meta['outputBytes']})
    print('EXP_BENCH_DONE',json.dumps({'counts':meta['counts'],'truncated':meta['truncated']}),flush=True)
    print('EXP_RESULTS_DIR',str(ROOT/'results'),flush=True)
finally:
    if child is not None and child.poll() is None:child.terminate();child.wait(timeout=20)
    if (ROOT/'results').exists():
        for p in sorted((ROOT/'results').glob('*')):
            if p.is_file():
                upload('partial_'+p.name,p.read_bytes())
    if stopped_gpio is not None:reg(0x41200000,stopped_gpio&~16)
    if unloaded and not Path('/sys/module/vision_fb').exists():subprocess.run(['modprobe','vision_fb'],check=True)
    if cfg['mounted']:subprocess.run(['umount',str(init)],check=True);cfg['mounted']=False;guard_save()
    gov.write_text(saved_gov);os.kill(1,signal.SIGHUP)
    end=time.monotonic()+40;after=None
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
    upload('restored.json',{'state':after,'governor':gov.read_text().strip(),'persistentHashes':persistent,
        'framebufferDriverLoaded':Path('/sys/module/vision_fb').exists(),'slcrLock':reg(0xf800000c),
        'newSdIoError':'I/O error' in new_log,'watchdogTriggered':(ROOT/'watchdog-restored').exists()})
    (ROOT/'done').write_text('restored');guard.wait(timeout=5);print('RESTORE_PASS',flush=True)
