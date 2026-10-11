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
        INPUT_COUNT = 3 * 416 * 416,
        CONV1_COUNT = 32 * 208 * 208,
        CONV2_COUNT = 64 * 104 * 104,
        BLOCK1_COUNT = 128 * 52 * 52,
        BLOCK2_COUNT = 256 * 26 * 26,
        BLOCK3_COUNT = 512 * 13 * 13,
        FEAT1_COUNT = 256 * 26 * 26,
        FEAT2_COUNT = 512 * 13 * 13
    };

    data_t* basic_conv1_out; // CHW: 32 x 208 x 208.
    data_t* basic_conv2_out; // CHW: 64 x 104 x 104.
    data_t* resblock1_out;   // CHW: 128 x 52 x 52.
    data_t* resblock2_out;   // CHW: 256 x 26 x 26.
    data_t* resblock3_out;   // CHW: 512 x 13 x 13.
    data_t* tmp;             // Shared block1/block2 feature buffer: 64 x 104 x 104.

    CSPDarkNet();
    ~CSPDarkNet();
    CSPDarkNet(const CSPDarkNet&) = delete;
    CSPDarkNet& operator=(const CSPDarkNet&) = delete;

    // Caller supplies separate cache-line-aligned CHW buffers.
    // input: 3x416x416; feat1: 256x26x26; feat2: 512x13x13.
    void forward(data_t* input, data_t* feat1, data_t* feat2);
    bool load_weight(const char* directory, BasicConv::WeightFileReader reader = nullptr,
                     void* context = nullptr);

private:
    data_t* storage[6];
};

#endif
