from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'pw24_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'pw12_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'pwconv.cpp'
code = path.read_text(encoding='utf-8').replace('#define Tm 12', '#define Tm 24')
phased = (base / 'pwphase_src/pwconv.cpp').read_text(encoding='utf-8')
a, b = code.index('void compute(data_t'), code.index('// store fm_out_buff')
c, d = phased.index('void compute(data_t'), phased.index('// store fm_out_buff')
compute = phased[c:d].replace('factor=8', 'factor=12').replace('mm<8', 'mm<12').replace('phase*8', 'phase*12')
code = code[:a]+compute+code[b:]
for name in ('wt_buff','wt_buff1','wt_buff2','fm_out_buff','fm_out1','fm_out2'):
    code = code.replace('variable='+name+' complete dim=1', 'variable='+name+' cyclic factor=12 dim=1')
code = code.replace('MAX_LEN/Tm', '(MAX_LEN+Tm-1)/Tm')
advance = 'next_block(SIZE,M,basePixAddr,baseChannel,next_basePixAddr,next_baseChannel);'
assert code.count(advance) == 1
code = code.replace(advance, '')
code = code.replace('while(true){', advance+'\n    while(next_baseChannel<M){')
stop = 'if(basePixAddr+Tp>=SIZE*SIZE&&baseChannel+Tm>=M)\n    \t\tbreak;'
assert stop in code
code = code.replace(stop, advance)
path.write_bytes(code.encode('utf-8'))
path = out / 'top.cpp'
code = path.read_text(encoding='utf-8').replace('max_write_burst_length=256', 'max_write_burst_length=32 num_write_outstanding=4')
for lane in range(1,5):
    code = code.replace(f'port=out{lane} offset=slave bundle=FM{lane}',
                        f'port=out{lane} offset=slave bundle=FM{lane} max_write_burst_length=32 num_write_outstanding=4')
path.write_bytes(code.encode('utf-8'))
print(out)
