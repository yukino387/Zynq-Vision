#include "basic_conv.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include <cstring>

static const int ch_in = 32, ch_out = 64, h = 208, out_h = 104;
static const int input_count = ch_in * h * h;
static const int weight_count = ch_out * ch_in * 9;
static const int output_count = ch_out * out_h * out_h;
static data_t input[input_count] __attribute__((aligned(64)));
static data_t output[output_count] __attribute__((aligned(64)));

extern "C" {
volatile unsigned test_stage = 0;
volatile unsigned test_errors = 0;
volatile unsigned test_checked = 0;
volatile unsigned test_destroyed = 0;
void test_finished() { while (1) {} }
}

int main() {
    for (int i = 0; i < input_count; ++i) input[i] = 512;
    conv_init();
    test_stage = 1;

    for (int run = 0; run < 2; ++run) {
        {
            BasicConv conv(h, h, 3, 2, 1, ch_in, ch_out);
            std::memset(conv.weight, 0, weight_count * sizeof(data_t));
            std::memset(conv.bias, 0, ch_out * sizeof(data_t));
            for (int oc = 0; oc < ch_out; ++oc)
                conv.weight[oc * ch_in * 9 + 4] = 512;
            std::memset(output, 0xA5, sizeof(output));

            Xil_DCacheFlushRange((INTPTR)input, sizeof(input));
            Xil_DCacheFlushRange((INTPTR)conv.weight, weight_count * sizeof(data_t));
            Xil_DCacheFlushRange((INTPTR)conv.bias, ch_out * sizeof(data_t));
            Xil_DCacheFlushRange((INTPTR)output, sizeof(output));
            test_stage = 2;
            conv.forward(input, output);
            test_stage = 3;
            Xil_DCacheInvalidateRange((INTPTR)output, sizeof(output));

            for (int i = 0; i < output_count; ++i) {
                if (output[i] != 512) {
                    if (test_errors < 10)
                        xil_printf("Mismatch [%d]: got %d, expected 512\r\n", i, (int)output[i]);
                    ++test_errors;
                }
                ++test_checked;
            }
        }
        ++test_destroyed;
    }

    test_stage = test_errors ? 5 : 4;
    xil_printf("BasicConv test: checked=%u errors=%u destroyed=%u\r\n",
               test_checked, test_errors, test_destroyed);
    test_finished();
    return 0;
}
