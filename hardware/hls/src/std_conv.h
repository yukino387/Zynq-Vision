#include"type.h"

void std_conv(const uint64_t* in1,const uint64_t* in2,const uint64_t* in3,const uint64_t* in4,
              const uint64_t* w1, const uint64_t* w2, const uint64_t* w3, const uint64_t* w4,
              int32_t* bias,
              uint64_t* out1, uint64_t* out2, uint64_t* out3, uint64_t* out4,
              ap_uint<10> ch_in, ap_uint<10> ch_out,
              ap_uint<9> fm_size, ap_uint<2> stride, ap_uint<1> act, ap_uint<2> kernel);


data_t requant(int32_t,int32_t,int32_t);
