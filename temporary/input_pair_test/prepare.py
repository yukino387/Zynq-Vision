from pathlib import Path
import subprocess
import json
import hashlib

test=Path(__file__).resolve().parent
root=test.parents[1]
build=test/'build'
source=build/'candidate_src'
source.mkdir(parents=True,exist_ok=True)
for p in (root/'hardware/hls/src').iterdir():
    if p.suffix in ['.cpp','.h']:
        data=p.read_bytes()
        (source/p.name).write_bytes(data)
path=source/'std_conv.cpp'
text=path.read_text()
original=subprocess.check_output(['git','show','de2d083:hardware/hls/src/std_conv.cpp'],cwd=root).decode()
begin=text.index('template<unsigned Lane>\nstatic void load_input_pair')
end=text.index('template<unsigned Lane>\nstatic void load_weight_lane',begin)
(build/'input_loader.inc').write_bytes(text[begin:end].encode())
(build/'baseline.json').write_text(json.dumps(dict(commit='de2d083',source_sha256=hashlib.sha256(original.encode()).hexdigest()),indent=2))
print('Prepared tests from the current formal HLS source')
