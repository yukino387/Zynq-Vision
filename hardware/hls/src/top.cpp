#include"top.h"


void conv(data_t* in1,data_t* in2,data_t* in3,data_t* in4,
		  data_t* w1,data_t* w2,data_t* w3,data_t* w4,
		  data_t* b,
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
	if(kernel==3 || kernel==1){
		cout<<"conv B1"<<endl;
		std_conv(in1,in2,in3,in4,
				 w1,w2,w3,w4,
				 b,
				 out1,out2,out3,out4,
				 ch_in,ch_out,
				 fsize,stride,act,kernel);
	}
	else if(kernel==2){     //kernel==2 maxpool; kernel==0 upsample
		maxpool(in1,out1,ch_in,fsize,fsize);
	}
	else{
		upsample(in1,out1);
	}
}
