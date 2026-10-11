"""Bound internal channel counters to the existing 512-channel network limit."""
from pathlib import Path
import re
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'shared44_narrow_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'shared44_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
for name in ('std_conv.cpp', 'std_conv.h'):
    path = out / name
    code = path.read_text(encoding='utf-8')
    code = re.sub(r'unsigned short (?=(?:ch_in|ch_out|m|n|ti|index)\b)', 'ap_uint<10> ', code)
    for name_width, width in (('fm_size',9), ('stride',2), ('kernel',2), ('act',1)):
        code = re.sub(r'unsigned short (?='+name_width+r'\b)', f'ap_uint<{width}> ', code)
    code = code.replace('unsigned short &next_m', 'ap_uint<10> &next_m')
    code = code.replace('unsigned short r,c,m;', 'unsigned short r,c;\n    ap_uint<10> m;')
    code = code.replace('unsigned short next_r,next_c,next_m;', 'unsigned short next_r,next_c;\n    ap_uint<10> next_m;')
    if name == 'std_conv.cpp':
        assert code.count('fm_size / stride') == 2
        code = code.replace('fm_size / stride', '(stride == 2 ? fm_size >> 1 : fm_size)')
        code = code.replace('fm_size/2', '(fm_size >> 1)')
    path.write_bytes(code.encode('utf-8'))
print(out)
