from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import hashlib
import json

task = Path(__file__).resolve().parent
delivery = task.parents[1] / 'camera/terminal/build/delivery'
entries = {x['path']: x for x in json.loads((delivery / 'checksums.json').read_text(encoding='utf-8-sig'))['files']}
backup = json.loads((task / 'backup-verified.json').read_text())
assert backup['allFileHashesVerified']
image = delivery / 'vision-terminal-sd.img.gz'
with image.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == entries[image.name]['sha256']
plan = {'cid': backup['cid'], 'sectors': backup['sectors'],
        'backupSha256': backup['archiveSha256'],
        'compressed': entries[image.name], 'image': entries['vision-terminal-sd.img'],
        'boot': {name: entries['boot/' + name] for name in ['BOOT.bin', 'zImage', 'system.dtb']}}
(task / 'flash-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8', newline='\n')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.client_address[0] != '169.254.140.110':
            self.send_error(403)
            return
        if self.path == '/plan':
            data = json.dumps(plan).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/image.gz':
            self.send_response(200)
            self.send_header('Content-Length', str(image.stat().st_size))
            self.end_headers()
            with image.open('rb') as stream:
                while block := stream.read(1024 * 1024):
                    self.wfile.write(block)
        else:
            self.send_error(404)

print('SD_IMAGE_SERVER_READY', flush=True)
HTTPServer(('169.254.140.109', 9089), Handler).serve_forever()
