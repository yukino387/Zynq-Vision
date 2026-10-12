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

void Yolo4_Tiny::forward(data_t* input, data_t* out0, data_t* out1) {
    backbone->forward(input, P4 + 128 * 16 * 16, feat2);
    conv_forP5_conv->forward(feat2, P5);

    yolo_headP5_basic_conv1->forward(P5, out0_tmp);
    Xil_DCacheFlushRange((INTPTR)out0, OUT0_COUNT * sizeof(data_t));
    conv_leakyrelu(512, OUT_CH, 0, 1, 1, 8, 8,
                   out0_tmp, yolo_headP5_w2, yolo_headP5_b2, out0, 0);
    Xil_DCacheInvalidateRange((INTPTR)out0, OUT0_COUNT * sizeof(data_t));

    upsample_conv->forward(P5, P5_Upsample);
    sampling(P5_Upsample, P4, 128, 8, 0);

    yolo_headP4_basic_conv1->forward(P4, out1_tmp);
    Xil_DCacheFlushRange((INTPTR)out1, OUT1_COUNT * sizeof(data_t));
    conv_leakyrelu(256, OUT_CH, 0, 1, 1, 16, 16,
                   out1_tmp, yolo_headP4_w2, yolo_headP4_b2, out1, 0);
    Xil_DCacheInvalidateRange((INTPTR)out1, OUT1_COUNT * sizeof(data_t));
}
