#include"type.h"

void std_conv(data_t* in1,data_t* in2,data_t* in3,data_t* in4, 
			  data_t* w1, data_t* w2, data_t* w3, data_t* w4,
			  data_t* bias,
			  data_t* out1, data_t* out2, data_t* out3, data_t* out4,
			  ap_uint<10> ch_in, ap_uint<10> ch_out,
			  ap_uint<9> fm_size, ap_uint<2> stride, ap_uint<1> act, ap_uint<2> kernel);
