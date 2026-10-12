#include "basic_op.h"
#include "yolo4_tiny.h"
#include "xil_cache.h"

static data_t* allocate_feature(data_t*& storage, int count) {
    storage = new data_t[count + 64];
    data_t* result = reinterpret_cast<data_t*>((reinterpret_cast<UINTPTR>(storage) + 63U)
                                               & ~static_cast<UINTPTR>(63U));
    Xil_DCacheFlushRange((INTPTR)result, count * sizeof(data_t));
    return result;
}


Yolo4_Tiny::Yolo4_Tiny() {
    backbone = new CSPDarkNet();
    conv_forP5_conv = new BasicConv(8, 8, 1, 1, 0, 512, 256);
    yolo_headP5_basic_conv1 = new BasicConv(8, 8, 3, 1, 1, 256, 512);
    upsample_conv = new BasicConv(8, 8, 1, 1, 0, 256, 128);
    yolo_headP4_basic_conv1 = new BasicConv(16, 16, 3, 1, 1, 384, 256);
    yolo_headP5_w2 = new data_t[OUT_CH * 512];
    yolo_headP5_b2 = new data_t[OUT_CH];
    yolo_headP4_w2 = new data_t[OUT_CH * 256];
    yolo_headP4_b2 = new data_t[OUT_CH];
    feat2 = allocate_feature(storage[0], FEAT2_COUNT);
    P5 = allocate_feature(storage[1], P5_COUNT);
    out0_tmp = allocate_feature(storage[2], FEAT2_COUNT);
    P5_Upsample = allocate_feature(storage[3], UPSAMPLE_COUNT);
    P4 = allocate_feature(storage[4], P4_COUNT);
    out1_tmp = allocate_feature(storage[5], HEAD_P4_COUNT);
}

Yolo4_Tiny::~Yolo4_Tiny() {
    delete backbone;
    delete conv_forP5_conv;
    delete yolo_headP5_basic_conv1;
    delete upsample_conv;
    delete yolo_headP4_basic_conv1;
    delete[] yolo_headP5_w2;
    delete[] yolo_headP5_b2;
    delete[] yolo_headP4_w2;
    delete[] yolo_headP4_b2;
    for (data_t* buffer : storage) delete[] buffer;
}

static uint32_t offset(data_t* p) { return (reinterpret_cast<UINTPTR>(p)-0x00100000U)/2; }
static void append(ConvCommand* program, int& count, BasicConv* layer, data_t* in, data_t* out) {
    program[count++]={offset(in),offset(out),offset(layer->weight),offset(layer->bias),
                      unsigned(layer->ch_in),unsigned(layer->ch_out),unsigned(layer->h),
                      unsigned(layer->s),unsigned(layer->k),1};
}
static void resize(ConvCommand* program, int& count, data_t* in, data_t* out, int ch, int size, int mode) {
    program[count++]={offset(in),offset(out),0,0,unsigned(ch),unsigned(ch),unsigned(size),0,unsigned(mode ? 2 : 0),0};
}
static void block(ConvCommand* program, int& count, Resblock_body* r, data_t* in, data_t* feat, data_t* out) {
    const int n=r->ch_out*r->h*r->w;
    append(program,count,r->conv1,in,r->route);
    append(program,count,r->conv2,r->route+n/2,r->conv3_out+n/2);
    append(program,count,r->conv3,r->conv3_out+n/2,r->conv3_out);
    append(program,count,r->conv4,r->conv3_out,feat);
    resize(program,count,r->route,out,r->ch_out,r->h,1);
    resize(program,count,feat,out+n/4,r->ch_out,r->h,1);
}
void Yolo4_Tiny::forward(data_t* input, data_t* out0, data_t* out1) {
    ConvCommand program[28] __attribute__((aligned(64)));
    int count=0;
    append(program,count,backbone->basic_conv1,input,backbone->basic_conv1_out);
    append(program,count,backbone->basic_conv2,backbone->basic_conv1_out,backbone->basic_conv2_out);
    block(program,count,backbone->resblock1,backbone->basic_conv2_out,backbone->tmp,backbone->resblock1_out);
    block(program,count,backbone->resblock2,backbone->resblock1_out,backbone->tmp,backbone->resblock2_out);
    block(program,count,backbone->resblock3,backbone->resblock2_out,P4+128*16*16,backbone->resblock3_out);
    append(program,count,backbone->basic_conv3,backbone->resblock3_out,feat2);
    append(program,count,conv_forP5_conv,feat2,P5);
    append(program,count,yolo_headP5_basic_conv1,P5,out0_tmp);
    program[count++]={offset(out0_tmp),offset(out0),offset(yolo_headP5_w2),offset(yolo_headP5_b2),512,OUT_CH,8,1,1,0};
    append(program,count,upsample_conv,P5,P5_Upsample);
    resize(program,count,P5_Upsample,P4,128,8,0);
    append(program,count,yolo_headP4_basic_conv1,P4,out1_tmp);
    program[count++]={offset(out1_tmp),offset(out1),offset(yolo_headP4_w2),offset(yolo_headP4_b2),256,OUT_CH,16,1,1,0};
    Xil_AssertVoid(count==28);
    Xil_DCacheFlushRange((INTPTR)input,CSPDarkNet::INPUT_COUNT*sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)out0,OUT0_COUNT*sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)out1,OUT1_COUNT*sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)program,sizeof(program));
    conv_run_program(program,count);
    Xil_DCacheInvalidateRange((INTPTR)out0,OUT0_COUNT*sizeof(data_t));
    Xil_DCacheInvalidateRange((INTPTR)out1,OUT1_COUNT*sizeof(data_t));
}
