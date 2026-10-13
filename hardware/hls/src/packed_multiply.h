#pragma once
#include <stdint.h>

static inline void multiply_pair(int8_t input,int8_t weight0,int8_t weight1,int16_t& output0,int16_t& output1) {
#pragma HLS INLINE
    const int32_t joined=int32_t(weight1)*65536+weight0;
    const int32_t packed=int32_t(uint32_t(joined)<<7)>>7;
    int32_t product=packed*input;
#pragma HLS BIND_OP variable=product op=mul impl=dsp latency=3
    output0=int16_t(product);
    output1=int16_t((product>>16)+(output0<0 ? 1 : 0));
}
