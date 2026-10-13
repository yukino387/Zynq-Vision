from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[2]
log=(Path(__file__).resolve().parent/'build/board/result.log').read_text()
assert 'PASS:' in log and 'TEST ERROR:' not in log,log
for name,count in [('out0',1617),('out1',6468)]:
    actual=(Path(__file__).resolve().parent/'build/board'/f'{name}.bin').read_bytes()[:count]
    expected=(root/'temporary/int8_model_test/build/golden'/f'{name}.bin').read_bytes()
    assert actual==expected,name
    print('PASS',name,count,hashlib.sha256(actual).hexdigest())
print(log)
