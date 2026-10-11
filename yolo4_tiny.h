#ifndef YOLO4_TINY_H
#define YOLO4_TINY_H

#include "cspdarknet.h"

class Yolo4_Tiny {
public:
    enum {
        OUT_CH = 75,
        FEAT2_COUNT = 512 * 13 * 13,
        P5_COUNT = 256 * 13 * 13,
        UPSAMPLE_COUNT = 128 * 13 * 13,
        P4_COUNT = 384 * 26 * 26,
        HEAD_P4_COUNT = 256 * 26 * 26,
        OUT0_COUNT = OUT_CH * 13 * 13,
        OUT1_COUNT = OUT_CH * 26 * 26
    };

    CSPDarkNet* backbone;
    BasicConv* conv_forP5_conv;
    BasicConv* yolo_headP5_basic_conv1;
    BasicConv* upsample_conv;
    BasicConv* yolo_headP4_basic_conv1;
    data_t* yolo_headP5_w2;
    data_t* yolo_headP5_b2;
    data_t* yolo_headP4_w2;
    data_t* yolo_headP4_b2;

    data_t* feat2;
    data_t* P5;
    data_t* out0_tmp;
    data_t* P5_Upsample;
    data_t* P4; // CHW: upsample in channels 0..127, feat1 in channels 128..383.
    data_t* out1_tmp;

    Yolo4_Tiny();
    ~Yolo4_Tiny();
    Yolo4_Tiny(const Yolo4_Tiny&) = delete;
    Yolo4_Tiny& operator=(const Yolo4_Tiny&) = delete;

    // Separate cache-line-aligned CHW buffers; output allocations must include
    // padding to the end of their last cache line. conv_init() is called by the caller.
    void forward(data_t* input, data_t* out0, data_t* out1);
    // On failure, earlier layers may already be loaded; retry before inference.
    bool load_weight(const char* directory, BasicConv::WeightFileReader reader = nullptr,
                     void* context = nullptr);

private:
    data_t* storage[6];
};

#endif
