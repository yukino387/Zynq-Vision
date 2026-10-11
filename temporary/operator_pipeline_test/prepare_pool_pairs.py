from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'pool_pairs_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'output_phases_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'maxpool.cpp'
code = path.read_text(encoding='utf-8')
a = code.index('void load_input(')
b = code.index('void compute(', a)
loader = code[a:b]
loader = loader.replace('jj<Tc*2;jj++', 'jj<Tc*2;jj+=2')
old = 'fm_in_buff[nn][ii][jj]=*(in+ base_addr +nn_size+ii_fsize+jj);'
assert loader.count(old) == 1
loader = loader.replace(old, '''for (unsigned short lane=0; lane<2; ++lane) {
#pragma HLS UNROLL
                    fm_in_buff[nn][ii][jj+lane]=*(in+base_addr+nn_size+ii_fsize+jj+lane);
                }''')
code = code[:a]+loader+code[b:]
path.write_bytes(code.encode('utf-8'))
print(out)
