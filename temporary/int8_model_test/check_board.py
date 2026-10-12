from pathlib import Path
import hashlib

directory=Path(__file__).resolve().parent / 'build'
log=(directory / 'board/result.log').read_text()
assert 'PASS:' in log and 'TEST ERROR:' not in log, log
for name,count in (('out0',1617),('out1',6468)):
    output=(directory / 'board' / (name+'.bin')).read_bytes()[:count]
    expected=(directory / 'golden' / (name+'.bin')).read_bytes()
    assert output==expected, name
    print('PASS:',name,count,'bytes',hashlib.sha256(output).hexdigest())
print(log)
