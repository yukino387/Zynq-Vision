"""Use one 44-channel output bank after the dual-bank core failed placement."""
from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'shared44_single_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'shared44_narrow_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
assert code.count('#define Tm 88') == 1
assert code.count('phase<(ch_out<=44 ? 1 : 2)') == 1
code = code.replace('#define Tm 88', '#define Tm 44')
code = code.replace('phase<(ch_out<=44 ? 1 : 2)', 'phase<1')
path.write_bytes(code.encode('utf-8'))
path = out / 'top.cpp'
code = path.read_text(encoding='utf-8')
assert code.count('depth=128 port=b') == 1
code = code.replace('depth=128 port=b', 'depth=512 port=b')
path.write_bytes(code.encode('utf-8'))
print(out)
