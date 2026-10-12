#include"upsample.h"


// 128*13*13-->128*26*26
void upsample(data_t* in,data_t* out, unsigned short size){
//#pragma HLS INTERFACE m_axi depth=100 port=out offset=slave bundle=OUT num_write_outstanding=4 
	data_t tmp;
	for(unsigned short n=0;n<128;n++)
		for(unsigned short i=0;i<size;i++)
			for(unsigned short j=0;j<size;j++){
#pragma HLS PIPELINE
				int wr_base_addr=n*size*size*4+i*size*4+2*j;
//#pragma HLS RESOURCE variable=wr_base_addr core=Mul_LUT
				int rd_base_addr=n*size*size+i*size+j;
//#pragma HLS RESOURCE variable=rd_base_addr core=Mul_LUT
				tmp=*(in+rd_base_addr);
				*(out+wr_base_addr)=tmp;
				*(out+wr_base_addr+1)=tmp;
				*(out+wr_base_addr+2*size)=tmp;
				*(out+wr_base_addr+2*size+1)=tmp;
			}
}
