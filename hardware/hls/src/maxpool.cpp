#include "maxpool.h"
#include "layout.h"
void maxpool(const uint64_t* input,uint64_t* output,int channels,int height,int width) {
    uint64_t plane[448],result[112];
#pragma HLS ARRAY_PARTITION variable=plane cyclic factor=2
#pragma HLS BIND_STORAGE variable=plane type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=result type=ram_1p impl=bram
    const unsigned level=size_level(width),out_level=size_level(width/2);
    const unsigned row_words=1u<<level,out_row_words=1u<<out_level;
    const unsigned input_words=unsigned(height)<<level;
    const unsigned output_words=unsigned(height/2)<<out_level;
    unsigned start=0,destination=0;
    for(unsigned n=0;n<unsigned(channels);++n) {
        for(unsigned i=0;i<input_words;++i) {
#pragma HLS PIPELINE II=1
            plane[i]=input[start+i];
        }
        for(unsigned i=0;i<output_words;++i) {
#pragma HLS PIPELINE II=1
            const unsigned col=i&(out_row_words-1);
            const unsigned source=((i>>out_level)<<(level+1))+2*col;
            const uint64_t first0=plane[source],first1=plane[source+1];
            const uint64_t second0=plane[source+row_words],second1=plane[source+row_words+1];
            uint64_t packed=0;
            for(unsigned byte=0;byte<8;++byte) {
#pragma HLS UNROLL
                const unsigned x=(col*8+byte)*2;
                const unsigned offset=(byte&3)*16;
                const uint64_t first=byte<4?first0:first1;
                const uint64_t second=byte<4?second0:second1;
                data_t value=data_t(first>>offset);
                const data_t a=data_t(first>>(offset+8));
                const data_t b=data_t(second>>offset);
                const data_t c=data_t(second>>(offset+8));
                if(a>value)value=a;if(b>value)value=b;if(c>value)value=c;
                packed|=uint64_t(uint8_t(x<unsigned(width)?value:data_t(0)))<<(byte*8);
            }
            result[i]=packed;
        }
        for(unsigned i=0;i<output_words;++i) {
#pragma HLS PIPELINE II=1
            output[destination+i]=result[i];
        }
        start+=plane_size(width)>>3;
        destination+=plane_size(width/2)>>3;
    }
}
