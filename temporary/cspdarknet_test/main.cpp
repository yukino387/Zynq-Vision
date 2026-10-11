#include "cspdarknet.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include <cstring>

static data_t input[CSPDarkNet::INPUT_COUNT] __attribute__((aligned(64)));
static data_t feat1[CSPDarkNet::FEAT1_COUNT + 32] __attribute__((aligned(64)));
static data_t feat2[CSPDarkNet::FEAT2_COUNT + 32] __attribute__((aligned(64)));
extern "C" {
volatile unsigned test_stage = 0, test_errors = 0, test_checked = 0, test_destroyed = 0;
volatile unsigned stage_errors[7] = {};
volatile unsigned stage_checked[7] = {};
void test_finished() { while (1) {} }
}

static void initialize_conv(BasicConv* layer, int bias) {
    const int kernel_area = layer->k * layer->k;
    std::memset(layer->weight, 0, layer->ch_out * layer->ch_in * kernel_area * sizeof(data_t));
    for (int c = 0; c < layer->ch_out; ++c) {
        layer->weight[(c * layer->ch_in + c % layer->ch_in) * kernel_area + kernel_area / 2] = 512;
        layer->bias[c] = bias;
    }
    Xil_DCacheFlushRange((INTPTR)layer->weight, layer->ch_out * layer->ch_in * kernel_area * sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)layer->bias, layer->ch_out * sizeof(data_t));
}

static void initialize_block(Resblock_body* block) {
    initialize_conv(block->conv1, 64);
    initialize_conv(block->conv2, 128);
    initialize_conv(block->conv3, 256);
    initialize_conv(block->conv4, 512);
}

static void reference_block(const int* input_values, int channels, int* features, int* output_values) {
    for (int c = 0; c < channels; ++c) {
        const int selected = input_values[channels / 2 + c % (channels / 2)];
        features[c] = selected + (c < channels / 2 ? 960 : 704);
        output_values[c] = input_values[c] + 64;
        output_values[channels + c] = features[c];
    }
}

static void prepare(data_t* buffer, int count) {
    for (int i = 0; i < count + 32; ++i) buffer[i] = -12345;
    Xil_DCacheFlushRange((INTPTR)buffer, (count + 32) * sizeof(data_t));
}

static void verify(data_t* buffer, int channels, int height, const int* values, int stage) {
    const int pixels = height * height;
    Xil_DCacheInvalidateRange((INTPTR)buffer, (channels * pixels + 32) * sizeof(data_t));
    for (int c = 0; c < channels; ++c)
        for (int p = 0; p < pixels; ++p) {
            if (buffer[c * pixels + p] != values[c]) {
                if (test_errors < 10)
                    xil_printf("Stage %d channel %d pixel %d: got %d expected %d\r\n",
                               stage, c, p, (int)buffer[c * pixels + p], values[c]);
                ++test_errors;
                ++stage_errors[stage];
            }
            ++test_checked;
            ++stage_checked[stage];
        }
    for (int i = 0; i < 32; ++i)
        if (buffer[channels * pixels + i] != -12345) {
            ++test_errors;
            ++stage_errors[stage];
        }
}

int main() {
    conv_init();
    test_stage = 1;
    {
        CSPDarkNet net;
        initialize_conv(net.basic_conv1, 16);
        initialize_conv(net.basic_conv2, 32);
        initialize_conv(net.basic_conv3, 48);
        initialize_block(net.resblock1);
        initialize_block(net.resblock2);
        initialize_block(net.resblock3);
        for (int c = 0; c < 3; ++c)
            for (int p = 0; p < 416 * 416; ++p)
                input[c * 416 * 416 + p] = 512 + c * 256;
        prepare(net.basic_conv1_out, CSPDarkNet::CONV1_COUNT);
        prepare(net.basic_conv2_out, CSPDarkNet::CONV2_COUNT);
        prepare(net.resblock1_out, CSPDarkNet::BLOCK1_COUNT);
        prepare(net.resblock2_out, CSPDarkNet::BLOCK2_COUNT);
        prepare(net.resblock3_out, CSPDarkNet::BLOCK3_COUNT);
        prepare(feat1, CSPDarkNet::FEAT1_COUNT);
        prepare(feat2, CSPDarkNet::FEAT2_COUNT);
        test_stage = 2;
        net.forward(input, feat1, feat2);
        test_stage = 3;

        int conv1[32], conv2[64], block1[128], block2[256], block3[512];
        int feature1[64], feature2[128], feature3[256], final_feature[512];
        for (int c = 0; c < 32; ++c) conv1[c] = 512 + c % 3 * 256 + 16;
        for (int c = 0; c < 64; ++c) conv2[c] = conv1[c % 32] + 32;
        reference_block(conv2, 64, feature1, block1);
        reference_block(block1, 128, feature2, block2);
        reference_block(block2, 256, feature3, block3);
        for (int c = 0; c < 512; ++c) final_feature[c] = block3[c] + 48;
        verify(net.basic_conv1_out, 32, 208, conv1, 0);
        verify(net.basic_conv2_out, 64, 104, conv2, 1);
        verify(net.resblock1_out, 128, 52, block1, 2);
        verify(net.resblock2_out, 256, 26, block2, 3);
        verify(net.resblock3_out, 512, 13, block3, 4);
        verify(feat1, 256, 26, feature3, 5);
        verify(feat2, 512, 13, final_feature, 6);
    }
    ++test_destroyed;
    test_stage = test_errors ? 5 : 4;
    xil_printf("CSPDarkNet test: checked=%u errors=%u\r\n", test_checked, test_errors);
    test_finished();
    return 0;
}
