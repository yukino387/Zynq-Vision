"""Prepare an isolated W8A8 candidate from the verified convolution schedule."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
dst = Path(__file__).resolve().parent / 'src'
dst.mkdir(exist_ok=True)
(dst / 'type.h').write_text('#pragma once\n#include <ap_int.h>\n#include <stdint.h>\ntypedef int8_t data_t;\n', encoding='utf-8')
text = (root / 'hardware/hls/src/std_conv.cpp').read_text()
text = text.replace('if (size == 8) return 8;\n    if (size == 16 || size == 32 || size == 64 || size == 128) return 16;\n    return size < 26 ? 13 : 26;', 'return size == 7 ? 7 : 14;')
text = text.replace('#define Tr 26', '#define Tr 14').replace('#define Tc 26', '#define Tc 14')
start = text.index('data_t leaky_relu(')
end = text.index('static data_t weight_cache', start)
text = text[:start] + '''static int32_t quant_m[512], quant_s[512], quant_nm[512], quant_ns[512];
static unsigned quant_channels;

data_t requant(int32_t value, int32_t multiplier, int32_t shift) {
#pragma HLS INLINE
    const int64_t product = int64_t(value) * multiplier;
    const uint64_t magnitude = product < 0 ? uint64_t(-product) : uint64_t(product);
    const int64_t rounded = (magnitude + (uint64_t(1) << (shift-1))) >> shift;
    const int64_t result = product < 0 ? -rounded : rounded;
    return result < -127 ? -127 : result > 127 ? 127 : data_t(result);
}

static data_t activate(int32_t value, unsigned channel, bool act) {
#pragma HLS INLINE
    if (channel >= quant_channels) return 0;
    const bool negative=act && value<0;
    const int32_t multiplier=negative ? quant_nm[channel] : quant_m[channel];
    const int32_t shift=negative ? quant_ns[channel] : quant_s[channel];
    return requant(value,multiplier,shift);
}

''' + text[end:]
text = text.replace('ap_uint<1> padding, ap_uint<6> extent)', 'ap_uint<1> padding, ap_uint<6> extent, bool valid)')
text = text.replace('if(row<padding || row>=ap_uint<10>(fm_size)+padding)', 'if(!valid || row<padding || row>=ap_uint<10>(fm_size)+padding)')
text = text.replace('ap_uint<9> fm_size, ap_uint<2> stride, ap_uint<2> kernel) {', 'ap_uint<9> fm_size, ap_uint<2> stride, ap_uint<2> kernel, ap_uint<10> ch_in) {')
for lane in range(4):
    text = text.replace(f'input_col,padding,extent);', f'input_col,padding,extent,n+{lane}<ch_in);', 1)
text = text.replace('else if (valid) {', 'else if (valid) {\n            const unsigned count=(ch_in-n < Tn ? unsigned(ch_in-n) : Tn)*elements;')
text = text.replace('values[k]=weights[base+block_offset+k];', 'values[k]=0;\n            }\n            for(unsigned short k=0; k<count; ++k) {\n#pragma HLS PIPELINE II=1\n                values[k]=weights[base+block_offset+k];')
text = text.replace('data_t fm_out_buff', 'int32_t fm_out_buff').replace('data_t bias_buff', 'int32_t bias_buff')
text = text.replace('data_t fm_out1', 'int32_t fm_out1').replace('data_t fm_out2', 'int32_t fm_out2')
start = text.index('                    data_t product[Tn];')
end = text.index('    \t\t\t\t}', start)
text = text[:start] + '''                    int16_t product[Tn];
#pragma HLS ARRAY_PARTITION variable=product complete
                    for(nn=0;nn<Tn;nn++) {
                        const unsigned short input_r = (stride == 2 ? rr << 1 : rr) + kx;
                        const unsigned short input_c = (stride == 2 ? cc << 1 : cc) + ky;
                        product[nn] = fm_in_buff[nn][input_r][input_c]*wt_buff[mm%4][mm/4][nn][kx][ky];
                    }
                    const int32_t sum = (int32_t(product[0])+product[1])+(int32_t(product[2])+product[3]);
                    fm_out_buff[mm][rr][cc] += sum;
''' + text[end:]
text = text.replace('leaky_relu(fm_out_buff[mm][rr][cc])', 'activate(fm_out_buff[mm][rr][cc],m+mm,true)')
for i in range(1,4):
    text = text.replace(f'leaky_relu(fm_out_buff[mm+{i}][rr][cc])', f'activate(fm_out_buff[mm+{i}][rr][cc],m+mm+{i},true)')
for i in range(4):
    index = 'mm' if i==0 else f'mm+{i}'
    text = text.replace(f'tmp{i+1}=fm_out_buff[{index}][rr][cc];', f'tmp{i+1}=activate(fm_out_buff[{index}][rr][cc],m+{index},false);')
text = text.replace('fm_size,stride,kernel);', 'fm_size,stride,kernel,ch_in);')
text = text.replace('data_t* bias,', 'int32_t* bias,')
text = re.sub(r'^.*cout<<.*$', '', text, flags=re.M)
text = text.replace('bias_buff[index/Tm][index%Tm] = bias[index];', '''bias_buff[index/Tm][index%Tm] = bias[index];
        quant_m[index]=bias[ch_out+index]; quant_s[index]=bias[2*ch_out+index];
        quant_nm[index]=bias[3*ch_out+index]; quant_ns[index]=bias[4*ch_out+index];''')
text = text.replace('    cache_enabled=kernel==1', '    quant_channels=ch_out;\n    cache_enabled=kernel==1')
# Four fixed output lanes avoid selecting among all 44 accumulator banks.
text = text.replace('fm_out_buff[Tm][Tr][Tc]', 'fm_out_buff[4][Tm/4][Tr][Tc]')
text = text.replace('fm_out1[Tm][Tr][Tc]', 'fm_out1[4][Tm/4][Tr][Tc]')
text = text.replace('fm_out2[Tm][Tr][Tc]', 'fm_out2[4][Tm/4][Tr][Tc]')
text = text.replace('fm_out_buff[mm][rr][cc]', 'fm_out_buff[mm%4][mm/4][rr][cc]')
for i in range(1,4):
    text = text.replace(f'fm_out_buff[mm+{i}][rr][cc]', f'fm_out_buff[{i}][mm/4][rr][cc]')
for array in ('fm_out_buff','fm_out1','fm_out2'):
    text = text.replace(f'#pragma HLS ARRAY_PARTITION variable={array} cyclic factor=44 dim=1',
                        f'#pragma HLS ARRAY_PARTITION variable={array} complete dim=1\n#pragma HLS ARRAY_PARTITION variable={array} complete dim=2')
text = text.replace('tmp1=activate(fm_out_buff[mm%4][mm/4][rr][cc]', 'tmp1=activate(fm_out_buff[0][mm/4][rr][cc]')
# Select the coefficient before multiplication; the final head also uses this path.
start = text.index('    \t\t\t    if(act==1){')
end = text.index('    \t\t\t    // o_fm_size', start)
text = text[:start] + ''.join(f'                    tmp{i+1}=activate(fm_out_buff[{i}][mm/4][rr][cc],m+mm+{i},act);\n' for i in range(4)) + text[end:]
text = text.replace('#define Tm 44', '#define Tm 32').replace('mm<44','mm<Tm')
text=text.replace('ap_uint<2> kernel, ap_uint<10> ch_in) {',
                  'ap_uint<2> kernel, ap_uint<10> ch_in) {\n    if(n>=ch_in) return;')
text=text.replace('ap_uint<10> ch_in,ap_uint<10> ch_out,ap_uint<2> kernel) {',
                  'ap_uint<10> ch_in,ap_uint<10> ch_out,ap_uint<2> kernel) {\n    if(n>=ch_in) return;')
text=text.replace('ap_uint<10> ch_out, ap_uint<2> kernel){',
                  'ap_uint<10> ch_out, ap_uint<2> kernel,bool enabled){\n    if(!enabled) return;')
helper = '''static void load_compute(data_t next_input[Tn][TRin][TCin], data_t next_weight[4][Tm/4][Tn][K][K],
                         data_t previous_input[Tn][TRin][TCin], data_t previous_weight[4][Tm/4][Tn][K][K],
                         int32_t output[4][Tm/4][Tr][Tc],
                         data_t* in1,data_t* in2,data_t* in3,data_t* in4,
                         data_t* w1,data_t* w2,data_t* w3,data_t* w4,
                         ap_uint<10> n,ap_uint<10> m,ap_uint<10> ci,ap_uint<10> co,
                         unsigned short row,unsigned short col,ap_uint<9> size,
                         ap_uint<2> stride,ap_uint<2> kernel,unsigned short tile,bool enabled) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    load_input(next_input,in1,in2,in3,in4,n,row,col,size,stride,kernel,ci);
    load_weight(next_weight,w1,w2,w3,w4,n,m,ci,co,kernel);
    compute(previous_input,output,previous_weight,stride,tile,co-m,kernel,enabled);
}

'''
index=text.index('// compute Out[')
text=text[:index]+helper+text[index:]
for current, previous in ((2,1),(1,2)):
    old=f'''load_input(fm_in_buff{current},in1,in2,in3,in4,ti,fm_row,fm_col,fm_size,stride,kernel,ch_in);
\t\t\tload_weight(wt_buff{current},w1,w2,w3,w4,ti,m,ch_in,ch_out,kernel);
\t\t\tcompute(fm_in_buff{previous},fm_out_buff,wt_buff{previous},stride,tile,ch_out-m,kernel);'''
    new=f'''load_compute(fm_in_buff{current},wt_buff{current},fm_in_buff{previous},wt_buff{previous},fm_out_buff,
                         in1,in2,in3,in4,w1,w2,w3,w4,ti,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,true);'''
    assert old in text
    text=text.replace(old,new)
old='''load_input(fm_in_buff1,in1,in2,in3,in4,ti,fm_row,fm_col,fm_size,stride,kernel,ch_in);   //ti=0
\tload_weight(wt_buff1,w1,w2,w3,w4,ti,m,ch_in,ch_out,kernel);'''
assert old in text
text=text.replace(old,'''load_compute(fm_in_buff1,wt_buff1,fm_in_buff2,wt_buff2,fm_out_buff,
                 in1,in2,in3,in4,w1,w2,w3,w4,0,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,false);''')
for previous,current in ((1,2),(2,1)):
    text=text.replace(f'compute(fm_in_buff{previous},fm_out_buff,wt_buff{previous},stride,tile,ch_out-m,kernel);',
                      f'''load_compute(fm_in_buff{current},wt_buff{current},fm_in_buff{previous},wt_buff{previous},fm_out_buff,
                 in1,in2,in3,in4,w1,w2,w3,w4,ch_in,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,true);''')
# compute/store calls are sequential; a second accumulator buffer adds no overlap.
start = text.index('void std_conv(')
body = text.index('{', start)
text = text[:body+1] + '''
    int32_t bias_buff[(MAX_LEN+Tm-1)/Tm][Tm];
#pragma HLS ARRAY_PARTITION variable=bias_buff complete dim=2
    int32_t fm_out[4][Tm/4][Tr][Tc];
#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=1
#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=2
    for (unsigned index=0;index<ch_out;++index) {
#pragma HLS PIPELINE II=1
        bias_buff[index/Tm][index%Tm]=bias[index];
        quant_m[index]=bias[ch_out+index]; quant_s[index]=bias[2*ch_out+index];
        quant_nm[index]=bias[3*ch_out+index]; quant_ns[index]=bias[4*ch_out+index];
    }
    quant_channels=ch_out;
    cache_enabled=kernel==1 || ch_in<=128;
    const unsigned out_size=stride==2 ? unsigned(fm_size)>>1 : unsigned(fm_size);
    const unsigned tile=spatial_tile(out_size);
    for(unsigned m=0;m<ch_out;m+=Tm) {
        cache_reuse=false;
        for(unsigned r=0;r<out_size;r+=tile) for(unsigned c=0;c<out_size;c+=tile) {
            compute_output(fm_out,bias_buff,in1,in2,in3,in4,w1,w2,w3,w4,
                           m,fm_size,ch_in,ch_out,r,c,stride,kernel);
            store_output(fm_out,out1,out2,out3,out4,r,c,m,fm_size,stride,act,ch_out);
            cache_reuse=true;
        }
    }
}
'''
for array in ('wt_buff1','wt_buff2'):
    text=text.replace(f'#pragma HLS ARRAY_PARTITION variable={array} complete dim=3',
                      f'#pragma HLS ARRAY_PARTITION variable={array} complete dim=3\n#pragma HLS BIND_STORAGE variable={array} type=ram_1p impl=lutram')
text=text.replace('#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=2',
                  '#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=2\n#pragma HLS BIND_STORAGE variable=fm_out type=ram_s2p impl=bram')
text=text.replace('const int64_t rounded = (magnitude + (uint64_t(1) << (shift-1))) >> shift;',
                  'const ap_uint<6> amount=shift;\n    const int64_t rounded = (magnitude + (uint64_t(1) << (amount-1))) >> amount;')
(dst / 'std_conv.cpp').write_text(text, encoding='utf-8')
header = (root / 'hardware/hls/src/std_conv.h').read_text().replace('data_t* bias,', 'int32_t* bias,')
(dst / 'std_conv.h').write_text(header + '\ndata_t requant(int32_t,int32_t,int32_t);\n', encoding='utf-8')
for name in ('maxpool.cpp','maxpool.h','upsample.cpp','upsample.h'):
    (dst / name).write_bytes((root / 'hardware/hls/src' / name).read_bytes())

top = (root / 'hardware/hls/src/top.cpp').read_text()
top = top.replace('data_t* bias,', 'int32_t* bias,').replace('data_t* b,', 'int32_t* b,')
top = top.replace('else upsample(in1,out1,size);', '''else if (kernel == 0) upsample(in1,out1,size);
    else if (kernel == 5) {
        const int count=ci*size*size;
        const int32_t multiplier=bias[0], shift=bias[1];
        for (int i=0; i<count; ++i) {
#pragma HLS PIPELINE II=1
            out1[i]=requant(in1[i],multiplier,shift);
        }
    }''')
top = top.replace('program[280]', 'program[640]').replace('ch_in > 28', 'ch_in > 64')
top = top.replace('''        const data_t low=b[2*i], high=b[2*i+1];
        program[i]=(ap_uint<32>(high.range(15,0))<<16) | ap_uint<32>(low.range(15,0));''', '        program[i]=b[i];')
top = top.replace('network ? w1+bias_offset : b', 'network ? b+bias_offset : b')
(dst / 'top.cpp').write_text(top, encoding='utf-8')
top_h = '#pragma once\n#include "std_conv.h"\n#include "maxpool.h"\n#include "upsample.h"\n' + '''void conv(data_t*,data_t*,data_t*,data_t*,data_t*,data_t*,data_t*,data_t*,
          int32_t*,data_t*,data_t*,data_t*,data_t*,int,int,int,int,int,int);
'''
(dst / 'top.h').write_text(top_h, encoding='utf-8')
