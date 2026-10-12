#ifndef CSPDARKNET_H
#define CSPDARKNET_H

#include "resblock_body.h"

class CSPDarkNet {
public:
    BasicConv* basic_conv1;
    BasicConv* basic_conv2;
    BasicConv* basic_conv3;
    Resblock_body* resblock1;
    Resblock_body* resblock2;
    Resblock_body* resblock3;

    enum {
        INPUT_COUNT = 3 * 256 * 256,
        CONV1_COUNT = 32 * 128 * 128,
        CONV2_COUNT = 64 * 64 * 64,
        BLOCK1_COUNT = 128 * 32 * 32,
        BLOCK2_COUNT = 256 * 16 * 16,
        BLOCK3_COUNT = 512 * 8 * 8,
        FEAT1_COUNT = 256 * 16 * 16,
        FEAT2_COUNT = 512 * 8 * 8
    };

    data_t* basic_conv1_out; // CHW: 32 x 128 x 128.
    data_t* basic_conv2_out; // CHW: 64 x 64 x 64.
    data_t* resblock1_out;   // CHW: 128 x 32 x 32.
    data_t* resblock2_out;   // CHW: 256 x 16 x 16.
    data_t* resblock3_out;   // CHW: 512 x 8 x 8.
    data_t* tmp;             // Shared block1/block2 feature buffer: 64 x 64 x 64.

    CSPDarkNet();
    ~CSPDarkNet();
    CSPDarkNet(const CSPDarkNet&) = delete;
    CSPDarkNet& operator=(const CSPDarkNet&) = delete;

    // Caller supplies separate cache-line-aligned CHW buffers.
    // input: 3x256x256; feat1: 256x16x16; feat2: 512x8x8.
    void forward(data_t* input, data_t* feat1, data_t* feat2);
    bool load_weight(const char* directory, BasicConv::WeightFileReader reader = nullptr,
                     void* context = nullptr);

private:
    data_t* storage[6];
};

#endif
