from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, os, struct, subprocess, threading, time

task = Path('/workspace/temporary/hdmi_crop_20261018')
previous = Path('/workspace/temporary/inspection_terminal_20261018')
source = (previous / 'panel_fb_fixture.c').read_text().replace('inspection_terminal_20261018', 'hdmi_crop_20261018')
(task / 'panel_fb_fixture.c').write_text(source)
subprocess.run(['arm-linux-gnueabihf-gcc', '-shared', '-fPIC', str(task/'panel_fb_fixture.c'), '-o', str(task/'panel_fb_fixture.so'), '-ldl'], check=True)
framebuffer = task / 'panel-fb.bin'
if framebuffer.exists():
    framebuffer.unlink()
active = True

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == '/jobs':
            body = [{'id': 'test', 'name': 'Display regression fixture'}] if active else []
        elif self.path == '/state':
            body = {'job': {'id': 'test', 'name': 'Display regression fixture', 'instructions': 'Test only'} if active else None,
                    'total': int(active), 'counts': {'PASS': int(active), 'FAIL': 0, 'REVIEW': 0, 'ERROR': 0},
                    'pendingSync': 0, 'error': '', 'syncError': '', 'paused': False,
                    'last': {'sequence': 1, 'result': 'PASS', 'findings': []} if active else None}
        elif self.path == '/frame' and active:
            meta = json.dumps({'frameId': 1, 'fresh': True, 'boxes': []}).encode()
            body = struct.pack('<I', len(meta)) + meta + b'\x00\xf8' * (416*416)
            self.send_response(200); self.end_headers(); self.wfile.write(body); return
        else:
            self.send_response(409); self.end_headers(); return
        self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(body).encode())

server = HTTPServer(('127.0.0.1',8877), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
log = (task / 'panel-reset.console.log').open('wb')
process = subprocess.Popen(['qemu-arm','-cpu','cortex-a9','-L','/usr/arm-linux-gnueabihf',
    '-E','LD_PRELOAD='+str(task/'panel_fb_fixture.so'), '/workspace/camera/terminal/build/arm/vision-panel',
    '/workspace/camera/terminal/build/delivery/rootfs/usr/share/vision/NotoSansCJKsc-Regular.otf'], stdout=log, stderr=log)

def wait_pixel(color):
    deadline = time.monotonic()+25
    while time.monotonic()<deadline:
        assert process.poll() is None, 'Panel exited'
        if framebuffer.exists():
            data = framebuffer.read_bytes()
            if len(data)==7372800:
                offsets = [(200*1280+100)*4 + page*3686400 for page in (0,1)]
                if all(struct.unpack_from('<I',data,offset)[0]&0xffffff == color for offset in offsets):
                    return data
        time.sleep(.15)
    raise RuntimeError('Both pages did not reach expected image color '+hex(color))

try:
    before = wait_pixel(0xff0000)
    (task/'panel-active.bin').write_bytes(before)
    active = False
    after = wait_pixel(0)
    (task/'panel-cleared.bin').write_bytes(after)
    assert before[3686400:] != after[3686400:], 'No rendered state transition'
    print('PASS: actual ARM panel renders live preview, then clears stale image on both pages when the engine loses its job/frame')
finally:
    process.terminate()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.kill(); process.wait()
    log.close(); server.shutdown(); server.server_close()
