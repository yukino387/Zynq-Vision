#include "resblock_body.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include <cstring>

static const int h = 26, channels = 64, half_channels = 32;
static const int pixels = h * h, count = channels * pixels, pooled_pixels = 13 * 13;
static data_t input[count] __attribute__((aligned(64)));
static data_t feat[count + 32] __attribute__((aligned(64)));
static data_t output[count / 2 + 32] __attribute__((aligned(64)));
extern "C" {
volatile unsigned test_stage = 0, test_errors = 0, test_checked = 0, test_destroyed = 0;
void test_finished() { while (1) {} }
}

static void check(data_t actual, int expected) {
    if (actual != expected) {
        if (test_errors < 10)
            xil_printf("Mismatch %u: got %d expected %d\r\n", test_checked, (int)actual, expected);
        ++test_errors;
    }
    ++test_checked;
}

static void identity(BasicConv* conv, int bias_value) {
    std::memset(conv->weight, 0, conv->ch_out * conv->ch_in * conv->k * conv->k * sizeof(data_t));
    for (int c = 0; c < conv->ch_out; ++c) {
        conv->weight[(c * conv->ch_in + c) * conv->k * conv->k + conv->k * conv->k / 2] = 512;
        conv->bias[c] = bias_value;
    }
}

static int value(int c, int r, int col, int run) {
    return 512 + c * 8 + r * 2 + col * 2 + run * 64;
}

int main() {
    conv_init();
    for (int run = 0; run < 2; ++run) {
        {
            Resblock_body block(h, h, channels, channels);
            identity(block.conv1, 0);
            identity(block.conv2, 128);
            identity(block.conv3, 256);
            std::memset(block.conv4->weight, 0, channels * channels * sizeof(data_t));
            for (int c = 0; c < channels; ++c) {
                block.conv4->bias[c] = c < half_channels ? 0 : 64;
                if (c < half_channels) {
                    block.conv4->weight[c * channels + c] = 256;
                    block.conv4->weight[c * channels + c + half_channels] = 256;
                } else {
                    block.conv4->weight[c * channels + c] = 512;
                }
            }
            for (int c = 0; c < channels; ++c)
                for (int r = 0; r < h; ++r)
                    for (int col = 0; col < h; ++col)
                        input[c * pixels + r * h + col] = value(c, r, col, run);
            for (int i = 0; i < count + 32; ++i) feat[i] = -12345;
            for (int i = 0; i < count / 2 + 32; ++i) output[i] = -12345;
            Xil_DCacheFlushRange((INTPTR)feat, sizeof(feat));
            Xil_DCacheFlushRange((INTPTR)output, sizeof(output));
            test_stage = 2;
            block.forward(input, feat, output);
            test_stage = 3;
            Xil_DCacheInvalidateRange((INTPTR)feat, sizeof(feat));
            Xil_DCacheInvalidateRange((INTPTR)output, sizeof(output));
            for (int c = 0; c < channels; ++c)
                for (int r = 0; r < h; ++r)
                    for (int col = 0; col < h; ++col) {
                        const int i = c * pixels + r * h + col;
                        const int selected = value(half_channels + c % half_channels, r, col, run);
                        check(block.route[i], value(c, r, col, run));
                        check(block.conv3_out[i], selected + (c < half_channels ? 384 : 128));
                        check(feat[i], selected + (c < half_channels ? 256 : 192));
                    }
            for (int c = 0; c < channels * 2; ++c)
                for (int r = 0; r < h / 2; ++r)
                    for (int col = 0; col < h / 2; ++col) {
                        const int channel = c % channels;
                        const int expected = c < channels
                            ? value(channel, r * 2 + 1, col * 2 + 1, run)
                            : value(half_channels + channel % half_channels, r * 2 + 1, col * 2 + 1, run)
                                + (channel < half_channels ? 256 : 192);
                        check(output[c * pooled_pixels + r * 13 + col], expected);
                    }
            for (int i = 0; i < 32; ++i) {
                if (feat[count + i] != -12345 || output[count / 2 + i] != -12345)
                    ++test_errors;
            }
        }
        ++test_destroyed;
    }
    test_stage = test_errors ? 5 : 4;
    xil_printf("Resblock test: checked=%u errors=%u destroyed=%u\r\n",
               test_checked, test_errors, test_destroyed);
    test_finished();
    return 0;
}
