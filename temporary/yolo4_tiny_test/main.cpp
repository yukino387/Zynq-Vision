#include "yolo4_tiny.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include <cstring>

static data_t input[CSPDarkNet::INPUT_COUNT] __attribute__((aligned(64)));
static data_t out0_storage[Yolo4_Tiny::OUT0_COUNT + 64] __attribute__((aligned(64)));
static data_t* const out0 = out0_storage + 32;
static data_t out1_storage[Yolo4_Tiny::OUT1_COUNT + 64] __attribute__((aligned(64)));
static data_t* const out1 = out1_storage + 32;
extern "C" {
volatile unsigned test_stage = 0, test_errors = 0, test_checked = 0, test_destroyed = 0;
volatile unsigned stage_errors[8] = {};
volatile unsigned stage_checked[8] = {};
volatile unsigned negative_out0 = 0, negative_out1 = 0;
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

static void initialize_prediction(data_t* weight, data_t* bias, int inputs) {
    std::memset(weight, 0, Yolo4_Tiny::OUT_CH * inputs * sizeof(data_t));
    for (int c = 0; c < Yolo4_Tiny::OUT_CH; ++c) {
        weight[c * inputs + (c * 3) % inputs] = c % 2 ? -512 : 512;
        bias[c] = -32;
    }
    Xil_DCacheFlushRange((INTPTR)weight, Yolo4_Tiny::OUT_CH * inputs * sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)bias, Yolo4_Tiny::OUT_CH * sizeof(data_t));
}

int main() {
    conv_init();
    test_stage = 1;
    {
        Yolo4_Tiny net;
        initialize_conv(net.backbone->basic_conv1, 16);
        initialize_conv(net.backbone->basic_conv2, 32);
        initialize_conv(net.backbone->basic_conv3, 48);
        initialize_block(net.backbone->resblock1);
        initialize_block(net.backbone->resblock2);
        initialize_block(net.backbone->resblock3);
        initialize_conv(net.conv_forP5_conv, 64);
        initialize_conv(net.yolo_headP5_basic_conv1, 128);
        initialize_conv(net.upsample_conv, 256);
        initialize_conv(net.yolo_headP4_basic_conv1, 512);
        // Select channels from both sides of the P4 concat.
        std::memset(net.yolo_headP4_basic_conv1->weight, 0, 256 * 384 * 9 * sizeof(data_t));
        for (int c = 0; c < 256; ++c)
            net.yolo_headP4_basic_conv1->weight[(c * 384 + (c * 5) % 384) * 9 + 4] = 512;
        Xil_DCacheFlushRange((INTPTR)net.yolo_headP4_basic_conv1->weight, 256 * 384 * 9 * sizeof(data_t));
        initialize_prediction(net.yolo_headP5_w2, net.yolo_headP5_b2, 512);
        initialize_prediction(net.yolo_headP4_w2, net.yolo_headP4_b2, 256);

        for (int c = 0; c < 3; ++c)
            for (int p = 0; p < 416 * 416; ++p)
                input[c * 416 * 416 + p] = 512 + c * 256;
        prepare(net.feat2, Yolo4_Tiny::FEAT2_COUNT);
        prepare(net.P5, Yolo4_Tiny::P5_COUNT);
        prepare(net.out0_tmp, Yolo4_Tiny::FEAT2_COUNT);
        prepare(net.P5_Upsample, Yolo4_Tiny::UPSAMPLE_COUNT);
        prepare(net.P4, Yolo4_Tiny::P4_COUNT);
        prepare(net.out1_tmp, Yolo4_Tiny::HEAD_P4_COUNT);
        for (unsigned i = 0; i < sizeof(out0_storage) / sizeof(data_t); ++i) out0_storage[i] = -12345;
        for (unsigned i = 0; i < sizeof(out1_storage) / sizeof(data_t); ++i) out1_storage[i] = -12345;
        Xil_DCacheFlushRange((INTPTR)out0_storage, sizeof(out0_storage));
        Xil_DCacheFlushRange((INTPTR)out1_storage, sizeof(out1_storage));
        test_stage = 2;
        net.forward(input, out0, out1);
        test_stage = 3;

        int conv1[32], conv2[64], block1[128], block2[256], block3[512];
        int feature1[64], feature2[128], feature3[256], backbone_feature[512];
        int p5[256], head5[512], upsample[128], p4[384], head4[256];
        int prediction0[75], prediction1[75];
        for (int c = 0; c < 32; ++c) conv1[c] = 512 + c % 3 * 256 + 16;
        for (int c = 0; c < 64; ++c) conv2[c] = conv1[c % 32] + 32;
        reference_block(conv2, 64, feature1, block1);
        reference_block(block1, 128, feature2, block2);
        reference_block(block2, 256, feature3, block3);
        for (int c = 0; c < 512; ++c) backbone_feature[c] = block3[c] + 48;
        for (int c = 0; c < 256; ++c) p5[c] = backbone_feature[c] + 64;
        for (int c = 0; c < 512; ++c) head5[c] = p5[c % 256] + 128;
        for (int c = 0; c < 128; ++c) upsample[c] = p5[c] + 256;
        for (int c = 0; c < 384; ++c)
            p4[c] = c < 128 ? upsample[c] : feature3[c - 128];
        for (int c = 0; c < 256; ++c) head4[c] = p4[(c * 5) % 384] + 512;
        for (int c = 0; c < 75; ++c) {
            const int sign = c % 2 ? -1 : 1;
            prediction0[c] = sign * head5[(c * 3) % 512] - 32;
            prediction1[c] = sign * head4[(c * 3) % 256] - 32;
        }
        verify(net.feat2, 512, 13, backbone_feature, 0);
        verify(net.P5, 256, 13, p5, 1);
        verify(net.out0_tmp, 512, 13, head5, 2);
        verify(net.P5_Upsample, 128, 13, upsample, 3);
        verify(net.P4, 384, 26, p4, 4);
        verify(net.out1_tmp, 256, 26, head4, 5);
        verify(out0, 75, 13, prediction0, 6);
        verify(out1, 75, 26, prediction1, 7);
        Xil_DCacheInvalidateRange((INTPTR)out0_storage, sizeof(out0_storage));
        Xil_DCacheInvalidateRange((INTPTR)out1_storage, sizeof(out1_storage));
        for (int i = 0; i < 32; ++i)
            if (out0_storage[i] != -12345 || out1_storage[i] != -12345) ++test_errors;
        for (int i = 0; i < Yolo4_Tiny::OUT0_COUNT; ++i) if (out0[i] < 0) ++negative_out0;
        for (int i = 0; i < Yolo4_Tiny::OUT1_COUNT; ++i) if (out1[i] < 0) ++negative_out1;
        if (negative_out0 != 37 * 13 * 13 || negative_out1 != 37 * 26 * 26) ++test_errors;
    }
    ++test_destroyed;
    test_stage = test_errors ? 5 : 4;
    xil_printf("Yolo4_Tiny test: checked=%u errors=%u negative=%u/%u\r\n",
               test_checked, test_errors, negative_out0, negative_out1);
    test_finished();
    return 0;
}

