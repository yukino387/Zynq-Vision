#ifndef BASIC_CONV_H
#define BASIC_CONV_H

#include "basic_op.h"
#include <cstddef>

class BasicConv {
public:
    int h;
    int w;
    int s;
    int k;
    int p;
    int ch_in;
    int ch_out;
    data_t* weight;
    data_t* bias;

    BasicConv(int h, int w, int k, int s, int p, int ch_in, int ch_out);
    ~BasicConv();

    BasicConv(const BasicConv&) = delete;
    BasicConv& operator=(const BasicConv&) = delete;

    void forward(data_t* input, data_t* output);

    typedef bool (*WeightFileReader)(const char* path, float* values,
                                    std::size_t count, void* context);
    // directory contains float32 w.bin and b.bin. Reader must require exact size.
    // Without a reader, use the process filesystem (PC); bare metal needs an adapter.
    bool load_weight(const char* directory, WeightFileReader reader = nullptr,
                     void* context = nullptr);
    bool load_weight_files(const char* directory, const char* weight_file,
                           const char* bias_file, WeightFileReader reader = nullptr,
                           void* context = nullptr);
};

#endif
