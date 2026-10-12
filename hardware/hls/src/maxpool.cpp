#include "maxpool.h"

void maxpool(data_t* in, data_t* out, int ch, int h, int w) {
    data_t first_row[416];
    data_t result[208];
    const unsigned short width = w;
    const unsigned short height = h;
    const int input_size = width * height;
#pragma HLS BIND_OP variable=input_size op=mul impl=dsp latency=3
    const int output_size = input_size >> 2;
    int input_base = 0, output_base = 0;
    for (int n = 0; n < ch; ++n) {
        int source = input_base, destination = output_base;
        for (unsigned short r = 0; r < height / 2; ++r) {
            for (unsigned short c = 0; c < width; ++c) {
#pragma HLS PIPELINE II=1
                first_row[c] = in[source + c];
            }
            source += width;
            data_t left = 0;
            for (unsigned short c = 0; c < width; ++c) {
#pragma HLS PIPELINE II=1
                const data_t value = in[source + c];
                const data_t vertical = first_row[c] > value ? first_row[c] : value;
                if (c & 1) result[c >> 1] = left > vertical ? left : vertical;
                else left = vertical;
            }
            source += width;
            for (unsigned short c = 0; c < width / 2; ++c) {
#pragma HLS PIPELINE II=1
                out[destination + c] = result[c];
            }
            destination += width / 2;
        }
        input_base += input_size;
        output_base += output_size;
    }
}
