from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, struct, subprocess, threading, time

task = Path('/workspace/temporary/xp_terminal_20261019')
source = Path('/workspace/temporary/inspection_terminal_20261018/panel_fb_fixture.c').read_text()
(task/'panel_fb_fixture.c').write_text(source.replace('inspection_terminal_20261018', task.name))
subprocess.run(['arm-linux-gnueabihf-gcc', '-shared', '-fPIC', str(task/'panel_fb_fixture.c'),
                '-o', str(task/'panel_fb_fixture.so'), '-ldl'], check=True)
framebuffer = task/'panel-fb.bin'
framebuffer.unlink(missing_ok=True)
scenario = 'idle'
observed = 0

# Deliberately synthetic camera fixture; no production job or inspection is created.
pixels = bytearray()
for y in range(416):
    for x in range(416):
        r, g, b = (176, 178, 174)
        if 45 < x < 370 and 44 < y < 370:
            r, g, b = (29, 100 + (x+y)%13, 71)
            if x%42 in (0, 1) or y%42 in (0, 1): r, g, b = (121, 153, 81)
            if 133 < x < 287 and 143 < y < 276: r, g, b = (38, 43, 49)
            for cx, cy in ((85,85), (330,85), (85,330), (330,330)):
                if (x-cx)**2+(y-cy)**2 < 100: r, g, b = (215, 211, 174)
        pixels += struct.pack('<H', ((r>>3)<<11)|((g>>2)<<5)|(b>>3))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        global observed
        active = scenario == 'review'
        if self.path == '/jobs':
            body = [{'id': 'fixture', 'name': '渲染验证 · 装配完整性检查'}] if active else []
        elif self.path == '/state':
            observed += 1
            body = {'job': {'id': 'fixture', 'name': '渲染验证 · 装配完整性检查',
                           'instructions': '核对主芯片与四个定位孔，结果不计入生产记录'} if active else None,
                    'total': 128, 'counts': {'PASS': 120, 'FAIL': 5, 'REVIEW': 3},
                    'pendingSync': 7, 'error': '摄像头连接中断，请检查设备连接。' if scenario == 'error' else '',
                    'syncError': 'offline' if scenario == 'error' else '', 'paused': False,
                    'last': {'sequence': 128, 'result': 'REVIEW',
                             'findings': [{'label': name, 'count': 1, 'uncertain': 0, 'min': 1, 'max': 1}
                                          for name in ['主芯片', '左上定位孔', '右上定位孔', '左下定位孔', '右下定位孔', '接口组件', '电源模块', '标识区域']]} if active else None}
        elif self.path == '/frame' and active:
            meta = json.dumps({'frameId': 128, 'fresh': True,
                               'boxes': [{'x1': 132, 'y1': 142, 'x2': 288, 'y2': 277}]}).encode()
            self.send_response(200);self.end_headers()
            self.wfile.write(struct.pack('<I', len(meta))+meta+pixels);return
        else:
            self.send_response(409);self.end_headers();return
        self.send_response(200);self.end_headers();self.wfile.write(json.dumps(body).encode())

server = HTTPServer(('127.0.0.1', 8877), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
log = (task/'render.console.log').open('wb')
process = subprocess.Popen(['qemu-arm', '-cpu', 'cortex-a9', '-L', '/usr/arm-linux-gnueabihf',
    '-E', 'LD_PRELOAD='+str(task/'panel_fb_fixture.so'), '/workspace/camera/terminal/build/arm/vision-panel',
    '/workspace/camera/terminal/build/delivery/rootfs/usr/share/vision/NotoSansCJKsc-Regular.otf'], stdout=log, stderr=log)

try:
    for name in ('idle', 'review', 'error'):
        scenario = name
        baseline = observed
        deadline = time.monotonic()+30
        while observed < baseline+3 or not framebuffer.exists():
            assert process.poll() is None, 'ARM panel exited'
            assert time.monotonic() < deadline, 'ARM panel did not refresh'
            time.sleep(.1)
        time.sleep(2.5)  # Include the 2-second job list timer and complete page flips.
        data = framebuffer.read_bytes()
        assert len(data) == 7372800
        assert data[:3686400] == data[3686400:], 'Back page is stale'
        # The fixed 416-square image must be entirely present, and cleared on loss.
        def pixel(x, y): return struct.unpack_from('<I', data, (y*1280+x)*4)[0]&0xffffff
        assert pixel(230, 220) != 0 if name == 'review' else pixel(230, 220) == 0
        (task/(name+'.bin')).write_bytes(data[:3686400])
        print('PASS ARM render:', name, flush=True)
finally:
    process.terminate()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.kill();process.wait()
    log.close();server.shutdown();server.server_close()
