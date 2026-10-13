#include "upsample.h"
#include "write_bytes.h"
void upsample(const uint64_t* input,uint64_t* output,unsigned short size) {
    uint64_t words[8];
#pragma HLS ARRAY_PARTITION variable=words complete
    data_t plane[49],result[196];
#pragma HLS ARRAY_PARTITION variable=result cyclic factor=8
    for(unsigned n=0;n<128;++n) {
        const unsigned start=n*size*size,offset=start&7;
        for(unsigned i=0;i<(offset+size*size+7)/8;++i) {
#pragma HLS PIPELINE II=1
            words[i]=input[(start>>3)+i];
        }
        for(unsigned i=0;i<size*size;++i) {
#pragma HLS PIPELINE II=1
            const unsigned byte=offset+i;
            plane[i]=data_t(words[byte>>3]>>((byte&7)*8));
        }
        for(unsigned y=0;y<2*size;++y) for(unsigned x=0;x<2*size;++x) {
#pragma HLS PIPELINE II=1
            result[y*size*2+x]=plane[(y>>1)*size+(x>>1)];
        }
        write_bytes<0,196>(output,n*size*size*4,result,size*size*4);
    }
}
