"""Test 44 output lanes; 48 lanes exceeded the 220-DSP limit."""
from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'shared44_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'pool_rows_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
assert code.count('#define Tm 64') == 1
code = code.replace('#define Tm 64', '#define Tm 88')
code = code.replace('MAX_LEN/Tm', '(MAX_LEN+Tm-1)/Tm')
code = code.replace('factor=32', 'factor=44')
code = code.replace('ch_out<=32', 'ch_out<=44').replace('mm<32', 'mm<44')
code = code.replace('phase*32', 'phase*44')
assert code.count('stride,tile,ch_out,kernel);') == 4
code = code.replace('stride,tile,ch_out,kernel);', 'stride,tile,ch_out-m,kernel);')
path.write_bytes(code.encode('utf-8'))
print(out)
