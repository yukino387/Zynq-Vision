#include "cspdarknet.h"
#include "xil_cache.h"

static data_t* allocate_feature(data_t*& storage, int count) {
    storage = new data_t[count + 64];
    return reinterpret_cast<data_t*>((reinterpret_cast<UINTPTR>(storage) + 63U)
                                      & ~static_cast<UINTPTR>(63U));
}

static void run_basic_conv(BasicConv* conv, data_t* input, data_t* output, int count) {
    Xil_DCacheFlushRange((INTPTR)output, count * sizeof(data_t));
    conv->forward(input, output);
    Xil_DCacheInvalidateRange((INTPTR)output, count * sizeof(data_t));
}

CSPDarkNet::CSPDarkNet() {
    basic_conv1 = new BasicConv(256, 256, 3, 2, 1, 3, 32);
    basic_conv2 = new BasicConv(128, 128, 3, 2, 1, 32, 64);
    basic_conv3 = new BasicConv(8, 8, 3, 1, 1, 512, 512);
    resblock1 = new Resblock_body(64, 64, 64, 64);
    resblock2 = new Resblock_body(32, 32, 128, 128);
    resblock3 = new Resblock_body(16, 16, 256, 256);
    basic_conv1_out = allocate_feature(storage[0], CONV1_COUNT);
    basic_conv2_out = allocate_feature(storage[1], CONV2_COUNT);
    resblock1_out = allocate_feature(storage[2], BLOCK1_COUNT);
    resblock2_out = allocate_feature(storage[3], BLOCK2_COUNT);
    resblock3_out = allocate_feature(storage[4], BLOCK3_COUNT);
    tmp = allocate_feature(storage[5], CONV2_COUNT);
}

CSPDarkNet::~CSPDarkNet() {
    delete basic_conv1;
    delete basic_conv2;
    delete basic_conv3;
    delete resblock1;
    delete resblock2;
    delete resblock3;
    for (data_t* buffer : storage) delete[] buffer;
}

void CSPDarkNet::forward(data_t* input, data_t* feat1, data_t* feat2) {
    Xil_DCacheFlushRange((INTPTR)input, INPUT_COUNT * sizeof(data_t));
    run_basic_conv(basic_conv1, input, basic_conv1_out, CONV1_COUNT);
    run_basic_conv(basic_conv2, basic_conv1_out, basic_conv2_out, CONV2_COUNT);
    resblock1->forward(basic_conv2_out, tmp, resblock1_out);
    resblock2->forward(resblock1_out, tmp, resblock2_out);
    resblock3->forward(resblock2_out, feat1, resblock3_out);
    run_basic_conv(basic_conv3, resblock3_out, feat2, FEAT2_COUNT);
}
