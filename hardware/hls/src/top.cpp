#include"top.h"
#include "layout.h"


static void execute_layer(const uint64_t* in1, const uint64_t* in2, const uint64_t* in3, const uint64_t* in4,
                          const uint64_t* w1, const uint64_t* w2, const uint64_t* w3, const uint64_t* w4,
                          int32_t* bias, uint64_t* out1, uint64_t* out2, uint64_t* out3, uint64_t* out4,
                          int ci, int co, int size, int stride, int kernel, int act) {
#pragma HLS INLINE off
    if (kernel == 3 || kernel == 1)
        std_conv(in1,in2,in3,in4,w1,w2,w3,w4,bias,out1,out2,out3,out4,ci,co,size,stride,act,kernel);
    else if (kernel == 2) maxpool(in1,out1,ci,size,size);
    else if (kernel == 0) upsample(in1,out1,size);
    else if (kernel == 5) {
        const int count=ci*plane_size(size);
        const int32_t multiplier=bias[0], shift=bias[1];
        data_t table[8][256];
#pragma HLS ARRAY_PARTITION variable=table complete dim=1
#pragma HLS BIND_STORAGE variable=table type=ram_1p impl=bram
        for(unsigned i=0;i<256;++i) {
#pragma HLS PIPELINE II=1
            const data_t value=requant(data_t(i),multiplier,shift);
            for(unsigned byte=0;byte<8;++byte) {
#pragma HLS UNROLL
                table[byte][i]=value;
            }
        }
        uint64_t words[64];
        for(unsigned base=0;base<unsigned(count);base+=512) {
            const unsigned bytes=count-base<512 ? count-base : 512;
            for(unsigned i=0;i<(bytes+7)/8;++i) {
#pragma HLS PIPELINE II=1
                words[i]=in1[(base>>3)+i];
            }
            for(unsigned i=0;i<bytes/8;++i) {
#pragma HLS PIPELINE II=1
                const uint64_t input=words[i];
                uint64_t word=0;
                for(unsigned byte=0;byte<8;++byte) {
#pragma HLS UNROLL
                    word|=uint64_t(uint8_t(table[byte][uint8_t(input>>(byte*8))]))<<(byte*8);
                }
                out1[(base>>3)+i]=word;
            }
        }
    }
}

void conv(const uint64_t* in1,const uint64_t* in2,const uint64_t* in3,const uint64_t* in4,
          const uint64_t* w1,const uint64_t* w2,const uint64_t* w3,const uint64_t* w4,
          int32_t* b,
          uint64_t* out1,uint64_t* out2,uint64_t* out3,uint64_t* out4,
          int ch_in,int ch_out,
          int fsize,int stride,int kernel,int act){
// AXI4-Lite
#pragma HLS INTERFACE s_axilite port=in1 bundle=CTRL offset=0x10
#pragma HLS INTERFACE s_axilite port=in2 bundle=CTRL offset=0x18
#pragma HLS INTERFACE s_axilite port=in3 bundle=CTRL offset=0x20
#pragma HLS INTERFACE s_axilite port=in4 bundle=CTRL offset=0x28
#pragma HLS INTERFACE s_axilite port=w1 bundle=CTRL offset=0x30
#pragma HLS INTERFACE s_axilite port=w2 bundle=CTRL offset=0x38
#pragma HLS INTERFACE s_axilite port=w3 bundle=CTRL offset=0x40
#pragma HLS INTERFACE s_axilite port=w4 bundle=CTRL offset=0x48
#pragma HLS INTERFACE s_axilite port=b bundle=CTRL offset=0x50
#pragma HLS INTERFACE s_axilite port=out1 bundle=CTRL offset=0x58
#pragma HLS INTERFACE s_axilite port=out2 bundle=CTRL offset=0x60
#pragma HLS INTERFACE s_axilite port=out3 bundle=CTRL offset=0x68
#pragma HLS INTERFACE s_axilite port=out4 bundle=CTRL offset=0x70
#pragma HLS INTERFACE s_axilite port=ch_in bundle=CTRL
#pragma HLS INTERFACE s_axilite port=ch_out bundle=CTRL
#pragma HLS INTERFACE s_axilite port=fsize bundle=CTRL
#pragma HLS INTERFACE s_axilite port=return bundle=CTRL
#pragma HLS INTERFACE s_axilite port=kernel bundle=CTRL
#pragma HLS INTERFACE s_axilite port=act bundle=CTRL
#pragma HLS INTERFACE s_axilite port=stride bundle=CTRL
// AXI4-Master
#pragma HLS INTERFACE m_axi depth=200000 port=in1 offset=slave bundle=FM1 max_read_burst_length=256 num_read_outstanding=4 max_write_burst_length=32 num_write_outstanding=4
#pragma HLS INTERFACE m_axi depth=200000 port=in2 offset=slave bundle=FM2 max_read_burst_length=256 num_read_outstanding=4 max_write_burst_length=32 num_write_outstanding=4
#pragma HLS INTERFACE m_axi depth=200000 port=in3 offset=slave bundle=FM3 max_read_burst_length=256 num_read_outstanding=4 max_write_burst_length=32 num_write_outstanding=4
#pragma HLS INTERFACE m_axi depth=200000 port=in4 offset=slave bundle=FM4 max_read_burst_length=256 num_read_outstanding=4 max_write_burst_length=32 num_write_outstanding=4
#pragma HLS INTERFACE m_axi depth=65536 port=w1 offset=slave bundle=W1 max_read_burst_length=256 num_read_outstanding=4
#pragma HLS INTERFACE m_axi depth=65536 port=w2 offset=slave bundle=W2 max_read_burst_length=256 num_read_outstanding=4
#pragma HLS INTERFACE m_axi depth=65536 port=w3 offset=slave bundle=W3 max_read_burst_length=256 num_read_outstanding=4
#pragma HLS INTERFACE m_axi depth=65536 port=w4 offset=slave bundle=W4 max_read_burst_length=256 num_read_outstanding=4
#pragma HLS INTERFACE m_axi depth=512 port=b offset=slave bundle=W1 max_read_burst_length=256 num_read_outstanding=4
#pragma HLS INTERFACE m_axi depth=100000 port=out1 offset=slave bundle=FM1 max_write_burst_length=32 num_write_outstanding=4
#pragma HLS INTERFACE m_axi depth=100000 port=out2 offset=slave bundle=FM2 max_write_burst_length=32 num_write_outstanding=4
#pragma HLS INTERFACE m_axi depth=100000 port=out3 offset=slave bundle=FM3 max_write_burst_length=32 num_write_outstanding=4
#pragma HLS INTERFACE m_axi depth=100000 port=out4 offset=slave bundle=FM4 max_write_burst_length=32 num_write_outstanding=4
//
    execute_layer(in1,in2,in3,in4,w1,w2,w3,w4,b,out1,out2,out3,out4,
                  ch_in,ch_out,fsize,stride,kernel,act);
}
