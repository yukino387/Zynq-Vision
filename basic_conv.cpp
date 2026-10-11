#include "basic_conv.h"

BasicConv::BasicConv(int h, int w, int k, int s, int p, int ch_in, int ch_out)
    : h(h), w(w), s(s), k(k), p(p), ch_in(ch_in), ch_out(ch_out),
      weight(new data_t[ch_out * ch_in * k * k]), bias(new data_t[ch_out]) {}

BasicConv::~BasicConv() {
    delete[] weight;
    delete[] bias;
}

void BasicConv::forward(data_t* input, data_t* output) {
    conv_leakyrelu(ch_in, ch_out, p, s, k, h, w,
                   input, weight, bias, output, 1);
}
