#include "basic_op.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xparameters.h"
#include <cstring>

static const int ch_in = 32, ch_out = 64, h = 208, out_h = 104;
static const int input_count = ch_in * h * h;
static const int weight_count = ch_out * ch_in * 9;
static const int output_count = ch_out * out_h * out_h;
static data_t input[input_count] __attribute__((aligned(64)));
static data_t weights[weight_count] __attribute__((aligned(64)));
static data_t bias[ch_out] __attribute__((aligned(64)));
static data_t output[output_count] __attribute__((aligned(64)));

extern "C" {
volatile unsigned test_stage = 0;
volatile unsigned test_errors = 0;
volatile unsigned test_checked = 0;
void test_finished() { while (1) {} }
}

int main() {
    for (int i = 0; i < input_count; ++i) input[i] = 512;
    std::memset(weights, 0, sizeof(weights));
    std::memset(bias, 0, sizeof(bias));
    for (int oc = 0; oc < ch_out; ++oc)
        weights[oc * ch_in * 9 + 4] = 512;

    conv_init();
    test_stage = 1;
    xil_printf("conv_init completed, base=0x%x\r\n", XPAR_CONV_0_BASEADDR);
    for (int run = 0; run < 2; ++run) {
        std::memset(output, 0xA5, sizeof(output));
        Xil_DCacheFlushRange((INTPTR)input, sizeof(input));
        Xil_DCacheFlushRange((INTPTR)weights, sizeof(weights));
        Xil_DCacheFlushRange((INTPTR)bias, sizeof(bias));
        Xil_DCacheFlushRange((INTPTR)output, sizeof(output));
        test_stage = 2;
        conv_leakyrelu(ch_in, ch_out, 0, 2, 3, h, h,
                       input, weights, bias, output, 0);
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
    test_stage = test_errors ? 5 : 4;
    xil_printf("basic_op test: checked=%u errors=%u stage=%u\r\n",
               test_checked, test_errors, test_stage);
    test_finished();
    return 0;
}
