"""Separate the four weight-port handshakes; retain INT16 arithmetic order."""
from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'shared44_weight_lanes_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'shared44_read_rows_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
start = code.index('void load_weight(')
end = code.index('void load_bias(', start)
replacement = '''template<unsigned Lane>
void load_weight_lane(data_t bank[Tm/4][Tn][K][K], data_t* weights,
                      int base, int ch_in_kk, ap_uint<10> n,
                      ap_uint<10> m, ap_uint<10> ch_in,
                      ap_uint<10> ch_out, ap_uint<2> kernel) {
#pragma HLS INLINE off
    const unsigned short elements = kernel == 1 ? 1 : 9;
    for(unsigned short group=0; group<Tm/4; ++group) {
        const unsigned short channel=4*group+Lane;
        int block_offset=channel*ch_in_kk;
#pragma HLS BIND_OP variable=block_offset op=mul impl=dsp latency=3
        const bool valid=m+channel<ch_out;
        for(unsigned short k=0; k<Tn*elements; ++k) {
#pragma HLS PIPELINE II=1
            const unsigned short nn=kernel == 1 ? k : k/9;
            const unsigned short i=kernel == 1 ? 0 : (k%9)/3;
            const unsigned short j=kernel == 1 ? 0 : k%3;
            const data_t value=valid ? weights[base+block_offset+k] : data_t(0);
            bank[group][nn][i][j]=n+nn<ch_in ? value : data_t(0);
        }
    }
}

void load_weight(data_t wt_buff[4][Tm/4][Tn][K][K],
                 data_t* w1,data_t* w2,data_t* w3,data_t* w4,
                 ap_uint<10> n,ap_uint<10> m,
                 ap_uint<10> ch_in,ap_uint<10> ch_out,ap_uint<2> kernel) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=1
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=3
    const int elements=kernel == 1 ? 1 : 9;
    int ch_in_kk=ch_in*elements;
#pragma HLS RESOURCE variable=ch_in_kk core=Mul_LUT
    int kernel_offset=m*ch_in_kk;
#pragma HLS BIND_OP variable=kernel_offset op=mul impl=dsp latency=3
    const int base=kernel_offset+n*elements;
    load_weight_lane<0>(wt_buff[0],w1,base,ch_in_kk,n,m,ch_in,ch_out,kernel);
    load_weight_lane<1>(wt_buff[1],w2,base,ch_in_kk,n,m,ch_in,ch_out,kernel);
    load_weight_lane<2>(wt_buff[2],w3,base,ch_in_kk,n,m,ch_in,ch_out,kernel);
    load_weight_lane<3>(wt_buff[3],w4,base,ch_in_kk,n,m,ch_in,ch_out,kernel);
}

'''
code = code[:start]+replacement+code[end:]
for name in ('wt_buff', 'wt_buff1', 'wt_buff2'):
    code = code.replace(f'{name}[Tm][Tn][K][K]', f'{name}[4][Tm/4][Tn][K][K]')
    old = (f'#pragma HLS ARRAY_PARTITION variable={name} complete dim=2\n'
           f'#pragma HLS ARRAY_PARTITION variable={name} cyclic factor=44 dim=1')
    new = (f'#pragma HLS ARRAY_PARTITION variable={name} complete dim=1\n'
           f'#pragma HLS ARRAY_PARTITION variable={name} complete dim=2\n'
           f'#pragma HLS ARRAY_PARTITION variable={name} complete dim=3')
    code = code.replace(old, new)
code = code.replace('#pragma HLS ARRAY_PARTITION variable=wt_buff cyclic factor=44 dim=1\n'
                    '#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2',
                    '#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=1\n'
                    '#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2\n'
                    '#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=3')
old = 'wt_buff[mm+phase*44][nn][kx][ky]'
assert code.count(old) == 1
code = code.replace(old, 'wt_buff[mm%4][mm/4][nn][kx][ky]')
assert all('cyclic factor' not in line for line in code.splitlines()
           if 'variable=wt_buff' in line)
path.write_bytes(code.encode('utf-8'))
print(out)
