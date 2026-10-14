import subprocess
from pathlib import Path

test = Path(__file__).resolve().parent
root = test.parents[1]
source = test / 'build/candidate_src'
source.mkdir(parents=True, exist_ok=True)
for path in (root / 'hardware/hls/src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        raw = subprocess.check_output(['git', 'show', f'45d6ce0:hardware/hls/src/{path.name}'], cwd=root)
        (source / path.name).write_bytes(raw)
path = source / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
code = code.replace('#include "layout.h"', '#include "layout.h"\n#include <hls_stream.h>')
start = code.index('template<unsigned Lane>\nstatic void write_row(')
end = code.index('static void load_compute(', start)
pipeline = '''static void quantize_output(int32_t buffer[4][Tm/4][Tr][Tc],
                            hls::stream<uint64_t> words[4],
                            unsigned m,unsigned rows,unsigned cols,unsigned bytes,
                            unsigned act,unsigned co) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=words complete
    uint64_t partial[4]={0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=partial complete
    const unsigned level=bytes==8?3:bytes==16?4:5;
    const unsigned count=rows<<level;
    for(unsigned mm=0;mm<Tm && m+mm<co;mm+=4) {
        int32_t multiplier[4],shift[4],negative_multiplier[4],negative_shift[4];
#pragma HLS ARRAY_PARTITION variable=multiplier complete
#pragma HLS ARRAY_PARTITION variable=shift complete
#pragma HLS ARRAY_PARTITION variable=negative_multiplier complete
#pragma HLS ARRAY_PARTITION variable=negative_shift complete
        for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
            const unsigned channel=m+mm+lane;
            multiplier[lane]=channel<co?quant_m[channel]:0;
            shift[lane]=channel<co?quant_s[channel]:1;
            negative_multiplier[lane]=channel<co?quant_nm[channel]:0;
            negative_shift[lane]=channel<co?quant_ns[channel]:1;
        }
        for(unsigned p=0;p<count;++p) {
#pragma HLS PIPELINE II=1
            const unsigned rr=p>>level,cc=p&(bytes-1);
            for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
                const int32_t sum=cc<cols && m+mm+lane<co?buffer[lane][mm/4][rr][cc]:0;
                const bool negative=act && sum<0;
                const data_t value=cc<cols && m+mm+lane<co?requant(sum,
                    negative?negative_multiplier[lane]:multiplier[lane],
                    negative?negative_shift[lane]:shift[lane]):data_t(0);
                if((cc&7)==0)partial[lane]=0;
                partial[lane]|=uint64_t(uint8_t(value))<<((cc&7)*8);
                if((cc&7)==7 && m+mm+lane<co)words[lane].write(partial[lane]);
            }
        }
    }
}

template<unsigned Lane>
static void write_output_stream(uint64_t* output,hls::stream<uint64_t>& words,
                                unsigned row,unsigned col,unsigned m,unsigned size,
                                unsigned rows,unsigned bytes,unsigned co) {
#pragma HLS INLINE off
    uint64_t packed[56];
#pragma HLS BIND_STORAGE variable=packed type=ram_1p impl=lutram
    const unsigned level=bytes==8?0:bytes==16?1:2;
    const unsigned row_words=1u<<level,count=rows<<level;
    for(unsigned mm=Lane;mm<Tm && m+mm<co;mm+=4) {
        const unsigned base=channel_base(m+mm,size)+(row<<(size_level(size)+3))+col;
        if(size<=14) {
            for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
                packed[i]=words.read();
            }
            for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
                output[(base>>3)+i]=packed[i];
            }
        } else {
            for(unsigned rr=0;rr<rows;++rr) {
                for(unsigned i=0;i<row_words;++i) {
#pragma HLS PIPELINE II=1
                    packed[i]=words.read();
                }
                const unsigned destination=(base>>3)+(rr<<size_level(size));
                for(unsigned i=0;i<row_words;++i) {
#pragma HLS PIPELINE II=1
                    output[destination+i]=packed[i];
                }
            }
        }
    }
}

static void store_output(int32_t buffer[4][Tm/4][Tr][Tc],
                         uint64_t* out1,uint64_t* out2,uint64_t* out3,uint64_t* out4,
                         unsigned row,unsigned col,unsigned m,unsigned size,unsigned stride,
                         unsigned act,unsigned co) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    size=stride==2?size>>1:size;
    const unsigned rows=size==7?7:14;
    const unsigned cols=size-col<16?size-col:16;
    const unsigned bytes=col+cols==size?row_pitch(size)-col:16;
    hls::stream<uint64_t> words[4];
#pragma HLS ARRAY_PARTITION variable=words complete
#pragma HLS STREAM variable=words depth=32
#pragma HLS BIND_STORAGE variable=words type=fifo impl=srl
    quantize_output(buffer,words,m,rows,cols,bytes,act,co);
    write_output_stream<0>(out1,words[0],row,col,m,size,rows,bytes,co);
    write_output_stream<1>(out2,words[1],row,col,m,size,rows,bytes,co);
    write_output_stream<2>(out3,words[2],row,col,m,size,rows,bytes,co);
    write_output_stream<3>(out4,words[3],row,col,m,size,rows,bytes,co);
}

'''
code = code[:start] + pipeline + code[end:]
path.write_bytes(code.encode('utf-8'))
print(source)
