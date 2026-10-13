#include "upsample.h"
#include "layout.h"
void upsample(const uint64_t* input,uint64_t* output,unsigned short size) {
    uint64_t words[7],result[28];
#pragma HLS ARRAY_PARTITION variable=words complete
    for(unsigned n=0;n<128;++n) {
        for(unsigned i=0;i<7;++i) {
#pragma HLS PIPELINE II=1
            words[i]=input[n*7+i];
        }
        for(unsigned row=0;row<14;++row) for(unsigned x=0;x<2;++x) {
#pragma HLS PIPELINE II=1
            uint64_t packed=0;
            for(unsigned byte=0;byte<8;++byte) {
#pragma HLS UNROLL
                const unsigned col=x*8+byte;
                const uint8_t value=col<14?uint8_t(words[row>>1]>>((col>>1)*8)):0;
                packed|=uint64_t(value)<<(byte*8);
            }
            result[row*2+x]=packed;
        }
        for(unsigned i=0;i<28;++i) {
#pragma HLS PIPELINE II=1
            output[n*28+i]=result[i];
        }
    }
}
