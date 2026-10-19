from pathlib import Path
import hashlib
import json
import shutil
import tarfile
import urllib.request

task = Path(__file__).resolve().parent
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open('http://169.254.140.110:9088/manifest', timeout=10) as response:
    manifest = json.load(response)
destination = task / ('sd-backup-' + manifest['cid'])
destination.mkdir(exist_ok=False)
(destination / 'backup-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8', newline='\n')
archive = destination / 'original-files.tar.gz'
with opener.open('http://169.254.140.110:9088/backup', timeout=60) as response, archive.open('xb') as stream:
    shutil.copyfileobj(response, stream, 1024 * 1024)
assert archive.stat().st_size == manifest['archiveBytes']
with archive.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest['archiveSha256']
with tarfile.open(archive) as source:
    source.extractall(destination / 'files', filter='data')
for entry in manifest['files']:
    path = destination / 'files/boot' / entry['path']
    assert path.stat().st_size == entry['size'], entry['path']
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == entry['sha256'], entry['path']
(task / 'backup-verified.json').write_text(json.dumps({
    'path': str(destination), 'cid': manifest['cid'], 'sectors': manifest['sectors'],
    'files': len(manifest['files']), 'bytes': sum(x['size'] for x in manifest['files']),
    'archiveSha256': manifest['archiveSha256'], 'allFileHashesVerified': True}, indent=2), encoding='utf-8', newline='\n')
print('PASS: SD file backup downloaded and every file SHA-256 verified: ' + str(destination))
