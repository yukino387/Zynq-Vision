#ifndef BASIC_OP_H
#define BASIC_OP_H

#include "xconv.h"

typedef short data_t;

// Offsets count 16-bit elements from the DDR link origin, 0x00100000.
struct ConvCommand {
    uint32_t input, output, weight, bias;
    uint32_t ci, co, size, stride, kernel, act;
};
static_assert(sizeof(ConvCommand) == 40, "Conv command must match the PL table");
void conv_run_program(const ConvCommand* program, int count);

void conv_init();
void conv_leakyrelu(int ch_in, int ch_out, int pad, int stride, int k,
                   int h, int w, data_t* in, data_t* weight,
                   data_t* bias, data_t* out, int act);
void sampling(data_t* in, data_t* out, int ch, int fsize, int mode);

#endif
