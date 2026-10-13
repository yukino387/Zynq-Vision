from pathlib import Path
import hashlib
import json
import re

directory=Path(__file__).resolve().parent / 'build'
log=(directory / 'board/result.log').read_text()
assert 'PASS:' in log and 'TEST ERROR:' not in log, log
for name,count in (('out0',1617),('out1',6468)):
    output=(directory / 'board' / (name+'.bin')).read_bytes()[:count]
    expected=(directory.parent.parent / 'int8_model_test/build/golden' / (name+'.bin')).read_bytes()
    assert output==expected, name
    print('PASS:',name,count,'bytes',hashlib.sha256(output).hexdigest())
print(log)
match=re.search(r'LAYER_US = (.*)',log)
if match:
    times=[int(value,0) for value in match.group(1).split()]
    names=json.loads((directory / 'command_names.json').read_text())
    assert len(times)==len(names)
    assert all(value>0 for value in times), 'Layer timing samples missing'
    rows=[{'layer':name,'us':value} for name,value in zip(names,times)]
    (directory / 'board/layer_times.json').write_text(json.dumps(rows,indent=2))
    print('Individual commands total:',sum(times),'us')
    for row in sorted(rows,key=lambda row:row['us'],reverse=True)[:8]:
        print(row)
