import subprocess
from pathlib import Path

test = Path(__file__).resolve().parent
root = test.parents[1]
original = {p.name: subprocess.check_output(['git', 'show', f'ad1cbf7:hardware/hls/src/{p.name}'], cwd=root)
            for p in (root / 'hardware/hls/src').iterdir() if p.suffix in ('.cpp', '.h')}
code = original['std_conv.cpp'].decode()
start = code.index('    for (unsigned index=0;index<ch_out;++index) {')
end = code.index('    quant_channels=ch_out;', start)
assignments = ['bias_buff[index/Tm][index%Tm]=bias[index];',
               'quant_m[index]=bias[ch_out+index];', 'quant_s[index]=bias[2*ch_out+index];',
               'quant_nm[index]=bias[3*ch_out+index];', 'quant_ns[index]=bias[4*ch_out+index];']
code = code[:start] + ''.join('    for(unsigned index=0;index<ch_out;++index) {\n#pragma HLS PIPELINE II=1\n        '
                              + line + '\n    }\n' for line in assignments) + code[end:]
variants = {'a': code}
assert code.count('variable=words type=fifo impl=srl') == 1
code = code.replace('variable=words type=fifo impl=srl', 'variable=words type=fifo impl=bram')
variants['b'] = code
start = code.index('    uint64_t packed[56];')
end = code.index('\nstatic void store_output(', start)
code = code[:start] + '''    const unsigned level=bytes==8?0:bytes==16?1:2;
    const unsigned row_words=1u<<level,count=rows<<level;
    for(unsigned mm=Lane;mm<Tm && m+mm<co;mm+=4) {
        const unsigned base=channel_base(m+mm,size)+(row<<(size_level(size)+3))+col;
        if(size<=14) {
            for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
                output[(base>>3)+i]=words.read();
            }
        } else {
            for(unsigned rr=0;rr<rows;++rr) {
                const unsigned destination=(base>>3)+(rr<<size_level(size));
                for(unsigned i=0;i<row_words;++i) {
#pragma HLS PIPELINE II=1
                    output[destination+i]=words.read();
                }
            }
        }
    }
}
''' + code[end:]
variants['c'] = code
variants['d'] = code.replace('variable=words type=fifo impl=bram', 'variable=words type=fifo impl=srl')
for name, content in variants.items():
    directory = test / 'build' / f'{name}_src'
    directory.mkdir(parents=True, exist_ok=True)
    for filename, data in original.items():
        (directory / filename).write_bytes(content.encode() if filename == 'std_conv.cpp' else data)
print('Prepared A: sequential parameters; B: A + BRAM FIFO; C: B + direct writes; D: A + direct writes')
