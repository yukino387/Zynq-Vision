"""Experiment: use one convolution datapath for both kernel sizes."""
from pathlib import Path
import re
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'shared_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'pooladdr_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)

path = out / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
for old in ('unsigned short fm_size, unsigned short stride){',
            'unsigned short ch_in,unsigned short ch_out){',
            'unsigned short stride, unsigned short tile, unsigned short ch_out){',
            'unsigned short fm_row,unsigned short fm_col,unsigned short stride){',
            'unsigned short fm_size,unsigned short stride,unsigned short act){'):
    assert code.count(old) == 1, old
    code = code.replace(old, old[:-2]+', unsigned short kernel){')

start, end = code.index('void load_input('), code.index('//load weight tile')
loader = code[start:end]
loader = loader.replace('    unsigned short nn,rr,cc;',
                        '    const unsigned short padding = kernel == 1 ? 0 : 1;\n    unsigned short nn,rr,cc;')
loader = re.sub(r'\bP\b', 'padding', loader)
loader = loader.replace('tile+K-1', 'tile+kernel-1')
code = code[:start]+loader+code[end:]

start, end = code.index('void load_weight('), code.index('void load_bias(')
loader = code[start:end].replace('int ch_in_kk=ch_in*K*K;',
                                'const int kernel_elements = kernel == 1 ? 1 : 9;\n\tint ch_in_kk=ch_in*kernel_elements;')
loader = loader.replace('n*K*K', 'n*kernel_elements').replace('k<Tn*K*K', 'k<Tn*kernel_elements')
loader = loader.replace('nn=k/(K*K)', 'nn=kernel == 1 ? k : k/9')
loader = loader.replace('i=(k%(K*K))/K', 'i=kernel == 1 ? 0 : (k%9)/3')
loader = loader.replace('j=k%K', 'j=kernel == 1 ? 0 : k%3')
code = code[:start]+loader+code[end:]

start, end = code.index('void compute('), code.index('// store fm_out_buff')
compute = code[start:end].replace('kx<K', 'kx<kernel').replace('ky<K', 'ky<kernel')
first = compute.index('    \t\t\t\t\tfor(nn=0;nn<Tn;nn++){')
last = compute.index('    \t\t\t\t}', first)
compute = compute[:first]+'''                    data_t product[Tn];
#pragma HLS ARRAY_PARTITION variable=product complete
                    for(nn=0;nn<Tn;nn++) {
                        const unsigned short input_r = (stride == 2 ? rr << 1 : rr) + kx;
                        const unsigned short input_c = (stride == 2 ? cc << 1 : cc) + ky;
                        product[nn] = fm_in_buff[nn][input_r][input_c]*wt_buff[mm+phase*32][nn][kx][ky];
                    }
                    if (kernel == 1) {
                        data_t a = product[0]+product[1], b = product[2]+product[3];
                        data_t sum = a+b;
                        fm_out_buff[mm+phase*32][rr][cc] = data_t(fm_out_buff[mm+phase*32][rr][cc]+sum);
                    } else {
                        for(nn=0;nn<Tn;nn++)
                            fm_out_buff[mm+phase*32][rr][cc] = data_t(fm_out_buff[mm+phase*32][rr][cc]+product[nn]);
                    }
'''+compute[last:]
code = code[:start]+compute+code[end:]

for name in ('load_input', 'load_weight', 'compute', 'compute_output'):
    code = re.sub(r'('+name+r'\([^;{}]*)(\);)', r'\1,kernel\2', code)
for lane, expression in enumerate(('base_addr+cc', 'base_addr+o_size+cc',
                                   'base_addr+2*o_size+cc', 'base_addr+3*o_size+cc')):
    old = f'*(out{lane+1}+{expression})=tmp{lane+1};'
    assert code.count(old) == 1, old
    code = code.replace(old, f'if (m+mm+{lane}<ch_out) '+old)
path.write_bytes(code.encode('utf-8'))

path = out / 'std_conv.h'
code = path.read_text(encoding='utf-8').replace('unsigned short act);', 'unsigned short act, unsigned short kernel);')
path.write_bytes(code.encode('utf-8'))
path = out / 'top.cpp'
code = path.read_text(encoding='utf-8').replace('if(kernel==3)', 'if(kernel==3 || kernel==1)')
code = code.replace('fsize,stride,act);', 'fsize,stride,act,kernel);', 1)
code = re.sub(r'\s*else if\(kernel==1\)\{[^{}]*\}', '', code)
path.write_bytes(code.encode('utf-8'))
print(out)
