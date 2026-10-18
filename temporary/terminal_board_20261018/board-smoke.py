"""RAM-only commissioning fixture; no server sync and no physical SD writes."""
from pathlib import Path
import base64, hashlib, json, shutil, struct, time, urllib.request, uuid, zlib

root = Path('/var/lib/vision')
assert not (root / 'connection.json').exists(), 'Commissioning must remain offline'
assert not (root / 'active.json').exists(), 'Preserve an existing active job'
assert not list((root / 'records').glob('*.json')), 'Preserve existing production evidence'
job_id = 'commissioning-20261018'
folder = root / 'jobs' / job_id
folder.mkdir(exist_ok=True)
binary = bytearray(Path('/boot/M04.BIN').read_bytes())
version = binary[24:88].split(b'\0')[0].decode()
payload_sha = hashlib.sha256(binary[128:]).hexdigest()
assert version == 'MILK-RGB-v3-20261018'
assert payload_sha == 'da359e72f2d097667f3a69c407fac6695b88a145e59fd2614b770c24bd435023'
# Resident SD slots carry generation/commit fields. Recreate the portable
# package header in RAM; leave the existing SD slot and model payload intact.
struct.pack_into('<II', binary, 16, 0, 0)
struct.pack_into('<I', binary, 120, zlib.crc32(binary[:120]) & 0xffffffff)
labels = ['commissioning-' + str(index) for index in range(6)]
job = {'formatVersion': 1, 'id': job_id, 'name': 'RAM commissioning only', 'target': 1,
       'deviceId': 'commissioning-only', 'modelSha256': hashlib.sha256(binary).hexdigest(),
       'manifest': {'networkTemplate': 'ZYNQ7020_NEU_INT8_V1', 'classCount': 6, 'classes': labels,
                    'quantization': {'outputScales': [.11581249687615341, .15977688286248154]}},
       'snapshot': {'modelVersion': version, 'modelPayloadSha256': payload_sha,
                    'acceptance': {'confidence': .7, 'qualityGate': False},
                    'rules': {'region': {'x': 0, 'y': 0, 'width': 1, 'height': 1},
                              'classes': labels, 'instructions': 'Commissioning fixture only',
                              'checks': [{'classId': i, 'min': 0, 'max': 100} for i in range(6)]}}}
(folder / 'model.bin').write_bytes(binary)
(folder / 'job.json').write_text(json.dumps(job))

def request(path, payload=None):
    req = urllib.request.Request('http://127.0.0.1:8877' + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

print('SMOKE_MODEL_VALIDATED', flush=True)
request('/select', {'id': job_id})
started = time.monotonic()
samples = []
while len(samples) < 20 and time.monotonic() - started < 30:
    state = request('/state')
    assert not state['error'], state
    if state['fresh'] and (not samples or state['frameId'] != samples[-1]):
        samples.append(state['frameId'])
    time.sleep(.1)
assert len(samples) == 20, samples
with urllib.request.urlopen('http://127.0.0.1:8877/frame', timeout=15) as response:
    frame = response.read()
size = struct.unpack_from('<I', frame)[0]
meta = json.loads(frame[4:4 + size])
pixels = frame[4 + size:]
assert len(pixels) == 416 * 416 * 2
assert len(set(struct.unpack('<173056H', pixels))) > 100, 'Camera image is constant'
operation = str(uuid.uuid4())
first = request('/check', {'requestId': operation})
assert first['saved'] and request('/check', {'requestId': operation}) == first
evidence = list((root / 'records').glob('*.json'))
assert len(evidence) == 1
record = json.loads(evidence[0].read_text())['payload']
assert len(base64.b64decode(record['raw'])) == 416 * 416 * 2
assert len(base64.b64decode(record['out0'])) == 1617
assert len(base64.b64decode(record['out1'])) == 6468
request('/pause', {'paused': True})
print('BOARD_SMOKE_PASSED ' + json.dumps({'model': version, 'framesObserved': samples,
    'elapsedSeconds': round(time.monotonic() - started, 3), 'previewFrame': meta['frameId'],
    'cameraSha256': hashlib.sha256(pixels).hexdigest(), 'recordSequence': first['sequence'],
    'idempotent': True, 'physicalSdWritten': False, 'serverSynced': False}), flush=True)
# The service is restarted after this script to return it to the empty-job state.
evidence[0].unlink()
(root / 'active.json').unlink()
shutil.rmtree(folder)
print('SMOKE_RAM_FIXTURE_REMOVED', flush=True)
