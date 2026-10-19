from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import hashlib
import json
import tarfile

root = Path('/boot')
assert '/dev/mmcblk0p1 /boot vfat ro,' in Path('/proc/mounts').read_text()
assert 'rootfs / rootfs ' in Path('/proc/mounts').read_text()
manifest = {'device': '/dev/mmcblk0',
            'cid': Path('/sys/block/mmcblk0/device/cid').read_text().strip(),
            'sectors': int(Path('/sys/block/mmcblk0/size').read_text()), 'files': []}
for path in sorted(root.rglob('*')):
    if path.is_file():
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        manifest['files'].append({'path': path.relative_to(root).as_posix(),
                                  'size': path.stat().st_size, 'sha256': digest})
with open('/dev/mmcblk0', 'rb', buffering=0) as stream:
    Path('/tmp/sd-original-head.bin').write_bytes(stream.read(1024 * 1024))
Path('/tmp/sd-original-manifest.json').write_text(json.dumps(manifest, indent=2))
with tarfile.open('/tmp/sd-original-files.tar.gz', 'w:gz', compresslevel=1) as archive:
    archive.add('/tmp/sd-original-manifest.json', arcname='manifest.json')
    archive.add('/tmp/sd-original-head.bin', arcname='original-first-1MiB.bin')
    archive.add(root, arcname='boot')
archive_path = Path('/tmp/sd-original-files.tar.gz')
with archive_path.open('rb') as stream:
    manifest['archiveSha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
manifest['archiveBytes'] = archive_path.stat().st_size

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.client_address[0] != '169.254.140.109':
            self.send_error(403)
            return
        if self.path == '/manifest':
            data = json.dumps(manifest).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/backup':
            self.send_response(200)
            self.send_header('Content-Length', str(archive_path.stat().st_size))
            self.end_headers()
            with archive_path.open('rb') as stream:
                while block := stream.read(1024 * 1024):
                    self.wfile.write(block)
        else:
            self.send_error(404)

print('SD_BACKUP_READY ' + json.dumps(manifest), flush=True)
HTTPServer(('169.254.140.110', 9088), Handler).serve_forever()
