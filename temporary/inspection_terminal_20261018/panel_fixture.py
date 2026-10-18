import json
import struct
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/jobs':
            payload = [{'id': 'test', 'name': '包装配装检查 · 测试批次'}]
        elif self.path == '/state':
            payload = {'job': {'id': 'test', 'name': '包装配装检查', 'instructions': '将一盒牛奶放入检查区域，确认摆放后点击检查'}, 'total': 12, 'counts': {'PASS': 10, 'FAIL': 1, 'REVIEW': 1, 'ERROR': 0}, 'pendingSync': 3, 'error': '', 'syncError': 'fixture offline', 'paused': False, 'last': {'sequence': 12, 'result': 'PASS', 'findings': [{'label': '牛奶', 'count': 1, 'uncertain': 0, 'min': 1, 'max': 1}]}}
        elif self.path == '/frame':
            meta = json.dumps({'frameId': 123, 'fresh': True, 'boxes': [{'x1': 120, 'y1': 80, 'x2': 285, 'y2': 340}]}).encode()
            pixels = b''.join(struct.pack('<H', ((x//14 & 31)<<11) | ((y//7 & 63)<<5) | 10) for y in range(416) for x in range(416))
            body = struct.pack('<I', len(meta)) + meta + pixels
            self.send_response(200); self.end_headers(); self.wfile.write(body); return
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(payload).encode())

HTTPServer.allow_reuse_address = True
HTTPServer(('127.0.0.1', 8877), Handler).serve_forever()
