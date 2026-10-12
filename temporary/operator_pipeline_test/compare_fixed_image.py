"""Compare identical real-image tests; do not infer camera FPS from one forward."""
from pathlib import Path
import hashlib
import json
import re
import sys

base = Path(__file__).resolve().parent / 'build/fixed_image'
candidate = sys.argv[1]
results = {}
for name in ('baseline100', candidate):
    directory = base / name
    log = (directory / 'result.log').read_text()
    assert 'PASS: real weights + real RGB image forward completed' in log
    assert 'TEST ERROR' not in log
    for symbol, expected in (('test_errors', 0), ('test_loaded', 42),
                             ('test_verified', 42), ('test_stage', 4)):
        assert int(re.search(rf'^{symbol} = {symbol}\s*:\s*(\d+)', log, re.M)[1]) == expected
    outputs = {}
    for filename, count in (('out0.bin', 25350), ('out1.bin', 101400)):
        data = (directory / filename).read_bytes()
        assert len(data) == (count + 3) // 4 * 4
        outputs[filename] = data[:count]
    results[name] = {
        'reported_forward_us': int(re.search(r'^forward_us = forward_us\s*:\s*(\d+)', log, re.M)[1]),
        'sha256': {key: hashlib.sha256(value).hexdigest() for key, value in outputs.items()},
    }
    if name == 'baseline100':
        baseline_outputs = outputs
    else:
        for filename in outputs:
            assert outputs[filename] == baseline_outputs[filename], f'{filename}: prediction changed'
assert results[candidate]['reported_forward_us'] < results['baseline100']['reported_forward_us']
results['exact_outputs_match'] = True
results['forward_speedup'] = results['baseline100']['reported_forward_us'] / results[candidate]['reported_forward_us']
results['scope'] = 'Same ELF, weights and fixed image. Single forward only; camera FPS requires UDP measurement.'
(base / f'{candidate}_comparison.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
