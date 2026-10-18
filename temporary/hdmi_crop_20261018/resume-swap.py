from pathlib import Path
import json,mmap,os,signal,struct,time

saved=json.loads(Path('/tmp/hdmi-swap-state.json').read_text())
fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC)
try:
    with mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ|mmap.PROT_WRITE,offset=0x43000000) as registers:
        struct.pack_into('<I',registers,0,4)
        deadline=time.monotonic()+2
        while struct.unpack_from('<I',registers,0)[0]&4:
            assert time.monotonic()<deadline,'VDMA reset timeout'
            time.sleep(.01)
        struct.pack_into('<I',registers,4,0xffffffff)
        struct.pack_into('<I',registers,0x28,saved['registers']['40'] & 31)
        struct.pack_into('<I',registers,0,1)
        for offset in (0x5c,0x60,0x58,0x54,0x50):
            struct.pack_into('<I',registers,offset,saved['registers'][str(offset)])
finally:
    os.close(fd)
    # BusyBox init restarts both programs, including camera setup after PL reset.
    for pid in saved['pids'].values():
        os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
print('DISPLAY_SWAP_RESTARTED',flush=True)
