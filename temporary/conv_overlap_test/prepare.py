import subprocess
from pathlib import Path

test = Path(__file__).resolve().parent
root = test.parents[1]
source = test / 'build/candidate_src'
source.mkdir(parents=True, exist_ok=True)
for path in (root / 'hardware/hls/src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        (source / path.name).write_bytes(subprocess.check_output(
            ['git', 'show', f'ad1cbf7:hardware/hls/src/{path.name}'], cwd=root))
path = source / 'std_conv.cpp'
code = path.read_text()
needle = 'unsigned short fm_row,unsigned short fm_col,ap_uint<2> stride, ap_uint<2> kernel){'
assert code.count(needle) == 1
code = code.replace(needle, needle[:-2] + ',bool enabled){\n#pragma HLS INLINE off\n    if(!enabled)return;')
position = code.index('\n\nvoid std_conv(')
helpers = '''
static void store_previous(int32_t buffer[4][Tm/4][Tr][Tc],
                           uint64_t* out1,uint64_t* out2,uint64_t* out3,uint64_t* out4,
                           unsigned row,unsigned col,unsigned m,ap_uint<9> size,ap_uint<2> stride,
                           unsigned act,ap_uint<10> co,bool enabled) {
#pragma HLS INLINE off
    if(enabled)store_output(buffer,out1,out2,out3,out4,row,col,m,size,stride,act,co);
}

static void copy_output(int32_t source[4][Tm/4][Tr][Tc],int32_t target[4][Tm/4][Tr][Tc],unsigned rows) {
#pragma HLS INLINE off
    for(unsigned r=0;r<rows;++r)for(unsigned c=0;c<Tc;++c) {
#pragma HLS PIPELINE II=1
        for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
            for(unsigned group=0;group<Tm/4;++group) {
#pragma HLS UNROLL
                target[lane][group][r][c]=source[lane][group][r][c];
            }
        }
    }
}

static void compute_store(int32_t next[4][Tm/4][Tr][Tc],int32_t previous[4][Tm/4][Tr][Tc],
                          int32_t bias_buff[(MAX_LEN+Tm-1)/Tm][Tm],
                          const uint64_t* in1,const uint64_t* in2,const uint64_t* in3,const uint64_t* in4,
                          const uint64_t* w1,const uint64_t* w2,const uint64_t* w3,const uint64_t* w4,
                          uint64_t* out1,uint64_t* out2,uint64_t* out3,uint64_t* out4,
                          ap_uint<10> m,unsigned short row,unsigned short col,unsigned previous_m,unsigned previous_row,unsigned previous_col,
                          ap_uint<9> size,ap_uint<10> ci,ap_uint<10> co,ap_uint<2> stride,ap_uint<2> kernel,
                          unsigned act,bool compute_enabled,bool store_enabled) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    compute_output(next,bias_buff,in1,in2,in3,in4,w1,w2,w3,w4,m,size,ci,co,row,col,stride,kernel,compute_enabled);
    store_previous(previous,out1,out2,out3,out4,previous_row,previous_col,previous_m,size,stride,act,co,store_enabled);
}
'''
code = code[:position] + '\n' + helpers + code[position:]
code = code.replace('int32_t fm_out[4][Tm/4][Tr][Tc];', 'int32_t fm_out[2][4][Tm/4][Tr][Tc];')
code = code.replace('#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=2',
                    '#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=2\n#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=3')
code = code.replace('    unsigned weight_base=0;', '    unsigned weight_base=0,previous_m=0,previous_row=0,previous_col=0;\n    bool valid=false;')
old = '''            compute_output(fm_out,bias_buff,in1,in2,in3,in4,w1+weight_base,w2+weight_base,w3+weight_base,w4+weight_base,
                           m,fm_size,ch_in,ch_out,r,c,stride,kernel);
            store_output(fm_out,out1,out2,out3,out4,r,c,m,fm_size,stride,act,ch_out);'''
new = '''            compute_store(fm_out[0],fm_out[1],bias_buff,in1,in2,in3,in4,w1+weight_base,w2+weight_base,w3+weight_base,w4+weight_base,
                          out1,out2,out3,out4,m,r,c,previous_m,previous_row,previous_col,fm_size,ch_in,ch_out,stride,kernel,act,true,valid);
            copy_output(fm_out[0],fm_out[1],tile);
            previous_m=m;previous_row=r;previous_col=c;
            valid=true;'''
assert code.count(old) == 1
code = code.replace(old,new)
tail = '''    compute_store(fm_out[0],fm_out[1],bias_buff,in1,in2,in3,in4,w1,w2,w3,w4,
                  out1,out2,out3,out4,0,0,0,previous_m,previous_row,previous_col,fm_size,ch_in,ch_out,stride,kernel,act,false,valid);
'''
code = code.rstrip()
assert code.endswith('}')
code = code[:-1] + tail + '}\n'
path.write_text(code,encoding='utf-8')
print(source)
