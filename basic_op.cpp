#include"basic_op.h"
#include "xparameters.h"

static XConv conv_inst;

void conv_leakyrelu(int ch_in,int ch_out,int pad,int stride,int k,int h,int w,
					data_t* in,data_t *weight,data_t *bias,data_t *out,int act){
	(void)pad;
	(void)w;
	//Xil_DCacheFlushRange((u32)in,sizeof(data_t)*ch_in*h*w);//������ˢ����DDR
	XConv_Set_in1(&conv_inst, (u32)in);
	XConv_Set_in2(&conv_inst, (u32)in);
	XConv_Set_in3(&conv_inst, (u32)in);
	XConv_Set_in4(&conv_inst, (u32)in);

	XConv_Set_w1_r(&conv_inst, (u32)weight);
	XConv_Set_w2_r(&conv_inst, (u32)weight);
	XConv_Set_w3_r(&conv_inst, (u32)weight);
	XConv_Set_w4_r(&conv_inst, (u32)weight);

	XConv_Set_b(&conv_inst, (u32)bias);
	XConv_Set_out1(&conv_inst, (u32)out);
	XConv_Set_out2(&conv_inst, (u32)out);
	XConv_Set_out3(&conv_inst, (u32)out);
	XConv_Set_out4(&conv_inst, (u32)out);

	XConv_Set_ch_in(&conv_inst,ch_in);
	XConv_Set_ch_out(&conv_inst,ch_out);
	XConv_Set_fsize(&conv_inst,h);
	XConv_Set_stride(&conv_inst,stride);
	XConv_Set_kernel(&conv_inst,k);
	XConv_Set_act(&conv_inst,act);
	//
	XConv_Start(&conv_inst);
	while(XConv_IsDone(&conv_inst)==0);
//	if(k==3&&stride==2)
//		Xil_DCacheInvalidateRange((u32)((unsigned int)out&0xffffffe0), 32*((ch_out*h*w/4*sizeof(data_t))/32+2));
//	else
//	    Xil_DCacheInvalidateRange((u32)((unsigned int)out&0xffffffe0), 32*((ch_out*h*w*sizeof(data_t))/32+2));

}


void conv_init(){
	XConv_Config config = {0, XPAR_CONV_0_BASEADDR};
	int status = XConv_CfgInitialize(&conv_inst, &config);
	Xil_AssertVoid(status == XST_SUCCESS);
	(void)status;
}


void sampling(data_t* in,data_t* out,int ch,int fsize,int mode){
	if(mode==1)   //maxpool
	    conv_leakyrelu(ch,ch,0,0,2,fsize,fsize,in,in,in,out,0);
	else //upsample
		conv_leakyrelu(ch,ch,0,0,0,fsize,fsize,in,in,in,out,0);
}
