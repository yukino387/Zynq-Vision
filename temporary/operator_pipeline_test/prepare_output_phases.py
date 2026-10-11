from pathlib import Path
import re
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'output_phases_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'phased_address_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
a = code.index('void compute(data_t')
b = code.index('// store fm_out_buff', a)
compute = code[a:b]
compute = compute.replace('unsigned short stride, unsigned short tile)',
                          'unsigned short stride, unsigned short tile, unsigned short ch_out)')
compute = compute.replace('phase<2', 'phase<(ch_out<=32 ? 1 : 2)')
compute = compute.replace('mm<Tm', 'mm<32').replace('nn<2', 'nn<Tn')
compute = compute.replace('nn+phase*2', 'nn')
compute = compute.replace('wt_buff[mm][nn]', 'wt_buff[mm+phase*32][nn]')
compute = compute.replace('fm_out_buff[mm][rr][cc]', 'fm_out_buff[mm+phase*32][rr][cc]')
code = code[:a]+compute+code[b:]
code, calls = re.subn(r'(compute\(fm_in_buff[12],fm_out_buff,wt_buff[12],stride,tile)\);', r'\1,ch_out);', code)
assert calls == 4, calls
for name in ('wt_buff','wt_buff1','wt_buff2','fm_out_buff','fm_out_buff1','fm_out_buff2','fm_out1','fm_out2'):
    code = code.replace('variable='+name+' complete dim=1', 'variable='+name+' cyclic factor=32 dim=1')
for name in ('wt_buff','wt_buff1','wt_buff2'):
    code = code.replace('variable='+name+' cyclic factor=2 dim=2', 'variable='+name+' complete dim=2')
path.write_bytes(code.encode('utf-8'))
print(out)
