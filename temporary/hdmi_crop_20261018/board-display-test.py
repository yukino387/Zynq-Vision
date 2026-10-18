from pathlib import Path
import json,mmap,os,signal,struct,subprocess,time,urllib.request

fd=os.open('/dev/mem',os.O_RDONLY|os.O_SYNC)
memory=mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ,offset=0x41210000)
def counter():
    gray=struct.unpack_from('<I',memory)[0];value=0
    while gray: value^=gray;gray>>=1
    return value
def state():
    return json.load(urllib.request.urlopen('http://127.0.0.1:8877/state',timeout=5))
def sample(seconds):
    first=counter();time.sleep(seconds);last=counter()
    return {'seconds':seconds,'before':first,'after':last,'delta':(last-first)&0xffffffff}

try:
    assert state()['job'] is None
    idle=sample(3)
    print('DISPLAY_IDLE_SAMPLE '+json.dumps(idle),flush=True)
    assert idle['delta']==0,'Display stream still fails at idle'
    before=counter()
    smoke=subprocess.run(['python3','/tmp/board-smoke.py'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=50,text=True)
    print(smoke.stdout,flush=True)
    assert smoke.returncode==0,'Camera/model smoke test failed'
    inference={'before':before,'after':counter()}
    inference['delta']=(inference['after']-before)&0xffffffff
    print('DISPLAY_INFERENCE_SAMPLE '+json.dumps(inference),flush=True)
    # Reset the RAM-only engine fixture before reporting any display error.
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():continue
        try: program=(process/'cmdline').read_bytes().split(b'\0')[0]
        except OSError:continue
        if program==b'/usr/local/bin/vision-engine':os.kill(int(process.name),signal.SIGTERM)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:
            current=state()
            if current['job'] is None and current['total']==0 and current['pendingSync']==0 and not current['error']:break
        except Exception:pass
        time.sleep(.25)
    else:raise RuntimeError('Engine did not return to idle')
    assert inference['delta']==0,'Display stream fails during PL inference'
    settled=sample(30)
    assert settled['delta']==0,'Display stream fails during settled idle'
    print('HDMI_STREAM_TEST_PASSED '+json.dumps({'idle':idle,'inference':inference,'settled':settled,'engineRestored':True}),flush=True)
finally:
    memory.close();os.close(fd)
