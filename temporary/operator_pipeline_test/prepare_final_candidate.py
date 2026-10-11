from pathlib import Path
import re
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'phased_address_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'address_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
# Keep address pipelining, but use the verified shared-multiplier pointwise schedule.
phased = (base / 'pwphase_src/pwconv.cpp').read_text(encoding='utf-8')
start = phased.index('void compute(data_t')
end = phased.index('// store fm_out_buff', start)
path = out / 'pwconv.cpp'
code = path.read_text(encoding='utf-8')
a = code.index('void compute(data_t')
b = code.index('// store fm_out_buff', a)
code = code[:a] + phased[start:end] + code[b:]
for name in ('wt_buff', 'wt_buff1', 'wt_buff2', 'fm_out_buff', 'fm_out1', 'fm_out2'):
    code = code.replace('variable='+name+' complete dim=1', 'variable='+name+' cyclic factor=8 dim=1')
path.write_bytes(code.encode('utf-8'))
# Address generator may have repeated a binding after replacing RESOURCE.
path = out / 'maxpool.cpp'
code = path.read_text(encoding='utf-8')
for name in ('nn_size', 'ii_fsize'):
    pragma = '#pragma HLS BIND_OP variable='+name+' op=mul impl=fabric latency=3'
    code = re.sub(re.escape(pragma)+r'\s*'+re.escape(pragma), pragma, code)
path.write_bytes(code.encode('utf-8'))
print(out)
