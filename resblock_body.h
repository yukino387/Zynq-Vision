#ifndef RESBLOCK_BODY_H
#define RESBLOCK_BODY_H

#include "basic_conv.h"

class Resblock_body {
public:
    int h, w, ch_in, ch_out;
    BasicConv* conv1;
    BasicConv* conv2;
    BasicConv* conv3;
    BasicConv* conv4;
    data_t* route;
    data_t* conv3_out;

    Resblock_body(int h, int w, int ch_in, int ch_out);
    ~Resblock_body();
    Resblock_body(const Resblock_body&) = delete;
    Resblock_body& operator=(const Resblock_body&) = delete;

    // feat: ch_out*h*w; out: (2*ch_out)*(h/2)*(w/2), both CHW.
    // Caller supplies separate, cache-line-aligned input/feat/out buffers.
    void forward(data_t* input, data_t* feat, data_t* out);
    bool load_weight(const char* directory, BasicConv::WeightFileReader reader = nullptr,
                     void* context = nullptr);

private:
    data_t* route_storage;
    data_t* concat_storage;
};

#endif
