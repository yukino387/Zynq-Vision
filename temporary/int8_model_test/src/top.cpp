#include"top.h"


static void execute_layer(data_t* in1, data_t* in2, data_t* in3, data_t* in4,
                          data_t* w1, data_t* w2, data_t* w3, data_t* w4,
                          int32_t* bias, data_t* out1, data_t* out2, data_t* out3, data_t* out4,
                          int ci, int co, int size, int stride, int kernel, int act) {
#pragma HLS INLINE off
    if (kernel == 3 || kernel == 1)
        std_conv(in1,in2,in3,in4,w1,w2,w3,w4,bias,out1,out2,out3,out4,ci,co,size,stride,act,kernel);
    else if (kernel == 2) maxpool(in1,out1,ci,size,size);
    else if (kernel == 0) upsample(in1,out1,size);
    else if (kernel == 5) {
        const int count=ci*size*size;
        const int32_t multiplier=bias[0], shift=bias[1];
        for (int i=0; i<count; ++i) {
#pragma HLS PIPELINE II=1
            out1[i]=requant(in1[i],multiplier,shift);
        }
    }
}

void conv(data_t* in1,data_t* in2,data_t* in3,data_t* in4,
          data_t* w1,data_t* w2,data_t* w3,data_t* w4,
          int32_t* b,
          data_t* out1,data_t* out2,data_t* out3,data_t* out4,
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
    ap_uint<32> program[640];
#pragma HLS BIND_STORAGE variable=program type=ram_1p impl=bram
    const bool network = kernel == 4;
    if (network && (ch_in < 1 || ch_in > 64)) return;
    const int count = network ? ch_in : 1;
    if (network) for (int i=0; i<count*10; ++i) {
#pragma HLS PIPELINE II=2
        program[i]=b[i];
    }
    for (int layer=0; layer<count; ++layer) {
        int ci=ch_in, co=ch_out, size=fsize, step=stride, op=kernel, activation=act;
        int input_offset=0, output_offset=0, weight_offset=0, bias_offset=0;
        if (network) {
            input_offset=program[layer*10+0]; output_offset=program[layer*10+1];
            weight_offset=program[layer*10+2]; bias_offset=program[layer*10+3];
            ci=program[layer*10+4]; co=program[layer*10+5]; size=program[layer*10+6];
            step=program[layer*10+7]; op=program[layer*10+8]; activation=program[layer*10+9];
        }
        execute_layer(in1+input_offset,in2+input_offset,in3+input_offset,in4+input_offset,
                      w1+weight_offset,w2+weight_offset,w3+weight_offset,w4+weight_offset,
                      network ? b+bias_offset : b,
                      out1+output_offset,out2+output_offset,out3+output_offset,out4+output_offset,
                      ci,co,size,step,op,activation);
    }
}
