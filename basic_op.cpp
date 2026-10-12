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


#include "xil_cache.h"

#pragma GCC push_options
#pragma GCC target("fpu=neon")
#include <arm_neon.h>

void sampling(data_t* in, data_t* out, int ch, int size, int mode) {
    const int output_size = mode ? size / 2 : size * 2;
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(in), ch * size * size * sizeof(data_t));
    for (int channel = 0; channel < ch; ++channel) {
        const data_t* source = in + channel * size * size;
        data_t* destination = out + channel * output_size * output_size;
        if (mode) {
            for (int y = 0; y < size; y += 2) {
                const data_t* first = source + y * size;
                const data_t* second = first + size;
                data_t* row = destination + y / 2 * output_size;
                int x = 0;
                for (; x + 8 <= size; x += 8) {
                    const int16x8_t vertical = vmaxq_s16(vld1q_s16(first + x), vld1q_s16(second + x));
                    const int16x8x2_t pairs = vuzpq_s16(vertical, vertical);
                    vst1_s16(row + x / 2, vmax_s16(vget_low_s16(pairs.val[0]), vget_low_s16(pairs.val[1])));
                }
                for (; x < size; x += 2) {
                    data_t value = first[x];
                    if (first[x + 1] > value) value = first[x + 1];
                    if (second[x] > value) value = second[x];
                    if (second[x + 1] > value) value = second[x + 1];
                    row[x / 2] = value;
                }
            }
        } else {
            for (int y = 0; y < size; ++y) {
                const data_t* row = source + y * size;
                data_t* first = destination + y * 2 * output_size;
                data_t* second = first + output_size;
                int x = 0;
                for (; x + 8 <= size; x += 8) {
                    const int16x8_t values = vld1q_s16(row + x);
                    const int16x8x2_t doubled = vzipq_s16(values, values);
                    vst1q_s16(first + 2 * x, doubled.val[0]);
                    vst1q_s16(first + 2 * x + 8, doubled.val[1]);
                    vst1q_s16(second + 2 * x, doubled.val[0]);
                    vst1q_s16(second + 2 * x + 8, doubled.val[1]);
                }
                for (; x < size; ++x)
                    first[2 * x] = first[2 * x + 1] = second[2 * x] = second[2 * x + 1] = row[x];
            }
        }
    }
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(out), ch * output_size * output_size * sizeof(data_t));
}
#pragma GCC pop_options
