#ifndef BASIC_OP_H
#define BASIC_OP_H

#include "xconv.h"

typedef short data_t;

void conv_init();
void conv_leakyrelu(int ch_in, int ch_out, int pad, int stride, int k,
                   int h, int w, data_t* in, data_t* weight,
                   data_t* bias, data_t* out, int act);
void sampling(data_t* in, data_t* out, int ch, int fsize, int mode);

#endif
