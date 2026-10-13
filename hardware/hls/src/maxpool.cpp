#include "maxpool.h"
#include "layout.h"
void maxpool(const uint64_t* input,uint64_t* output,int channels,int height,int width) {
    uint64_t first[8],second[8],result[4];
#pragma HLS ARRAY_PARTITION variable=first complete
#pragma HLS ARRAY_PARTITION variable=second complete
#pragma HLS ARRAY_PARTITION variable=result complete
    const unsigned pitch=row_pitch(width),out_pitch=row_pitch(width/2);
    for(unsigned n=0;n<unsigned(channels);++n) for(unsigned row=0;row<unsigned(height/2);++row) {
        const unsigned start=(channel_base(n,width)+((2*row)<<(size_level(width)+3)))>>3;
        for(unsigned i=0;i<pitch/8;++i) {
#pragma HLS PIPELINE II=1
            first[i]=input[start+i];
        }
        for(unsigned i=0;i<pitch/8;++i) {
#pragma HLS PIPELINE II=1
            second[i]=input[start+pitch/8+i];
        }
        for(unsigned i=0;i<out_pitch/8;++i) {
#pragma HLS PIPELINE II=1
            uint64_t packed=0;
            for(unsigned byte=0;byte<8;++byte) {
#pragma HLS UNROLL
                const unsigned x=(i*8+byte)*2;
                const unsigned word=x>>3,offset=x&7;
                data_t value=data_t(first[word]>>(offset*8));
                const data_t a=data_t(first[word]>>((offset+1)*8));
                const data_t b=data_t(second[word]>>(offset*8));
                const data_t c=data_t(second[word]>>((offset+1)*8));
                if(a>value)value=a;if(b>value)value=b;if(c>value)value=c;
                packed|=uint64_t(uint8_t(x<unsigned(width)?value:data_t(0)))<<(byte*8);
            }
            result[i]=packed;
        }
        const unsigned destination=(channel_base(n,width/2)+(row<<(size_level(width/2)+3)))>>3;
        for(unsigned i=0;i<out_pitch/8;++i) {
#pragma HLS PIPELINE II=1
            output[destination+i]=result[i];
        }
    }
}
