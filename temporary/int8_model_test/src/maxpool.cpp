#include "maxpool.h"
#include "write_bytes.h"
static void read_row(const uint64_t* input,data_t values[56],unsigned start,unsigned width) {
#pragma HLS INLINE off
    uint64_t words[8];
#pragma HLS ARRAY_PARTITION variable=words complete
    const unsigned offset=start&7;
    for(unsigned i=0;i<(offset+width+7)/8;++i) {
#pragma HLS PIPELINE II=1
        words[i]=input[(start>>3)+i];
    }
    for(unsigned i=0;i<width;++i) {
#pragma HLS PIPELINE II=1
        const unsigned byte=offset+i;
        values[i]=data_t(words[byte>>3]>>((byte&7)*8));
    }
}
void maxpool(const uint64_t* input,uint64_t* output,int channels,int height,int width) {
    data_t first[56],second[56],result[28];
#pragma HLS ARRAY_PARTITION variable=result cyclic factor=8
    for(int n=0;n<channels;++n) for(int row=0;row<height/2;++row) {
        const unsigned start=n*width*height+2*row*width;
        read_row(input,first,start,width);
        read_row(input,second,start+width,width);
        for(int x=0;x<width/2;++x) {
#pragma HLS PIPELINE II=1
            data_t maximum=first[2*x];
            if(first[2*x+1]>maximum) maximum=first[2*x+1];
            if(second[2*x]>maximum) maximum=second[2*x];
            if(second[2*x+1]>maximum) maximum=second[2*x+1];
            result[x]=maximum;
        }
        const unsigned destination=n*(width*height/4)+row*(width/2);
        write_bytes<0,28>(output,destination,result,width/2);
    }
}
