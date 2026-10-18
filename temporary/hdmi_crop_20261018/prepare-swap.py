from pathlib import Path
import json, mmap, os, signal, struct, time, urllib.request

state=json.load(urllib.request.urlopen('http://127.0.0.1:8877/state',timeout=5))
assert state['job'] is None and not state['pendingSync'], 'Preserve any active production work'
pids={}
for process in Path('/proc').iterdir():
    if not process.name.isdecimal(): continue
    try: program=(process/'cmdline').read_bytes().split(b'\0')[0].decode()
    except (OSError,UnicodeError): continue
    if program in ('/usr/local/bin/vision-panel','/usr/local/bin/vision-engine'):
        assert program not in pids, 'Multiple terminal processes'
        pids[program]=int(process.name)
assert len(pids)==2, pids
fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC)
stopped=[]
saved=None
try:
    for pid in pids.values():
        os.kill(pid,signal.SIGSTOP);stopped.append(pid)
    deadline=time.monotonic()+3
    for pid in stopped:
        while '\nState:\tT' not in Path('/proc',str(pid),'status').read_text():
            assert time.monotonic()<deadline,'Terminal process did not stop'
            time.sleep(.01)
    with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ|mmap.PROT_WRITE,offset=0x43000000) as registers:
        offsets=(0,0x28,0x50,0x54,0x58,0x5c,0x60)
        saved={str(offset):struct.unpack_from('<I',registers,offset)[0] for offset in offsets}
        Path('/tmp/hdmi-swap-state.json').write_text(json.dumps({'pids':pids,'registers':saved}))
        struct.pack_into('<I',registers,0,saved['0'] & ~1)
        deadline=time.monotonic()+2
        while not struct.unpack_from('<I',registers,4)[0]&1:
            assert time.monotonic()<deadline, 'VDMA did not halt'
            time.sleep(.01)
    print('DISPLAY_SWAP_READY: terminal processes stopped and VDMA halted',flush=True)
except BaseException:
    if saved is not None:
        with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ|mmap.PROT_WRITE,offset=0x43000000) as registers:
            struct.pack_into('<I',registers,0,saved['0'])
    for pid in stopped: os.kill(pid,signal.SIGCONT)
    raise
finally: os.close(fd)
