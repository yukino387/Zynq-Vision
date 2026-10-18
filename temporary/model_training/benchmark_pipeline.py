"""Time a few-dozen-image workload by replaying existing project assets.

Read-only production database access. Outputs stay in temporary/model_training.
The repeated samples are timing fixtures, not independent accuracy evidence.
"""
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
config = {}
for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
    if line.startswith(('DATABASE_URL=', 'STORAGE_ROOT=')):
        key, value = line.split('=', 1)
        config[key] = value.strip().strip('"\'')
database = Path(config.get('DATABASE_URL', 'file:../../../data/app.db')[5:])
if not database.is_absolute():
    database = (ROOT / 'apps/server/prisma' / database).resolve()
storage = (ROOT / 'apps/server' / config.get('STORAGE_ROOT', '../../data/storage')).resolve()
db = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
rows = db.execute('''SELECT i.sampleId,i.snapshot FROM DatasetItem i JOIN Dataset d
                    ON d.id=i.datasetId WHERE d.status='FROZEN' ORDER BY i.sampleId''').fetchall()
originals = []
for sample_id, snapshot in rows:
    snapshot = json.loads(snapshot)
    asset = db.execute('SELECT storageKey,sha256 FROM Asset WHERE id=?', (snapshot['previewId'],)).fetchone()
    originals.append({'id': sample_id, 'path': str(storage / asset[0]), 'sha256': asset[1],
                      'width': snapshot['width'], 'height': snapshot['height'], 'boxes': snapshot['boxes']})
db.close()
assert originals, 'A frozen source snapshot is needed for timing replay'
items = [{**originals[i % len(originals)], 'id': f'timing-{i}', 'split': 'train' if i < 38 else 'val'} for i in range(48)]
results = []
for mode in ('GRAY', 'RGB'):
    directory = BASE / f'pipeline_{mode.lower()}'
    directory.mkdir(exist_ok=True)
    spec = {'options': {'colorMode': mode, 'epochs': 5, 'batchSize': 32, 'learningRate': .001,
                        'seed': 7020, 'device': 'cuda', 'amp': True, 'workers': 4},
            'items': items, 'version': f'TIMING-{mode}', 'datasetChecksum': 'TIMING_REPLAY_ONLY'}
    (directory / 'spec.json').write_text(json.dumps(spec), encoding='utf-8')
    started = time.perf_counter()
    child = subprocess.Popen([str(ROOT / 'data/training-venv/Scripts/python.exe'), '-u',
                              str(ROOT / 'camera/training/train.py'), '--spec', str(directory / 'spec.json'),
                              '--output', str(directory)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding='utf-8', env={**os.environ, 'PYTHONUTF8': '1'})
    quantization_at = integer_validation_at = None
    with (directory / 'run.log').open('w', encoding='utf-8') as log:
        for line in child.stdout:
            log.write(line); log.flush()
            try:
                event = json.loads(line)
            except ValueError:
                print(line.rstrip(), flush=True)
                continue
            if event.get('stage') == 'Quantization':
                quantization_at = time.perf_counter()
            if event.get('stage') == 'Validation' and event.get('progress') == 85:
                integer_validation_at = time.perf_counter()
            if 'epoch' in event and 'trainSeconds' in event:
                print(json.dumps({'mode': mode, **event}), flush=True)
    code = child.wait()
    if code:
        raise RuntimeError(f'{mode} pipeline failed: {code}')
    wall = time.perf_counter() - started
    report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
    result = {'mode': mode, 'wallSeconds': wall, 'history': report['history'], 'runtime': report['runtime'],
              'calibrationAndExportSeconds': integer_validation_at - quantization_at,
              'integerValidationAndFinishSeconds': time.perf_counter() - integer_validation_at}
    results.append(result)
    print(json.dumps({'completed': result}), flush=True)
    (BASE / 'pipeline_timing_report.json').write_text(json.dumps({
        'workload': '48 timing records replayed from existing frozen image assets; 38 train, 10 validation; 5 epochs',
        'independentSourceImages': len(originals), 'accuracyEvidence': False, 'results': results}, indent=2), encoding='utf-8')
