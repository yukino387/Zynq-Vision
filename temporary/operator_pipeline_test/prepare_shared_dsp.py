"""Spend freed DSP capacity on pipelined address multiplication."""
from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'shared_dsp_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'shared_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
for name in ('std_conv.cpp', 'maxpool.cpp'):
    path = out / name
    code = path.read_text(encoding='utf-8')
    code = code.replace('op=mul impl=fabric latency=3', 'op=mul impl=dsp latency=3')
    if name == 'maxpool.cpp':
        assert code.count('int size=h*w;') == 1
        code = code.replace('int size=h*w;', 'int size=static_cast<unsigned short>(h)*static_cast<unsigned short>(w);')
    path.write_bytes(code.encode('utf-8'))
print(out)
