#include "basic_conv.h"
#include "xil_cache.h"
#include <cmath>
#include <cstring>

static const int weight_count = 32 * 3 * 3 * 3, bias_count = 32;
static const int input_count = 3 * 416 * 416, output_count = 32 * 208 * 208;
static data_t input[input_count] __attribute__((aligned(64)));
extern "C" {
float raw_weight[weight_count] __attribute__((aligned(64)));
float raw_bias[bias_count] __attribute__((aligned(64)));
char pc_directory[1024] __attribute__((aligned(64)));
data_t output[output_count + 32] __attribute__((aligned(64)));
volatile unsigned test_stage = 0, test_errors = 0, test_checked = 0, test_loaded = 0;
volatile int weight_min = 32767, weight_max = -32768, bias_min = 32767, bias_max = -32768;
volatile int output_min = 32767, output_max = -32768;
volatile unsigned output_changed = 0;
volatile unsigned loader_checks = 0;
void test_load_ready() {}
void test_finished() { while (1) {} }
}

static bool fixture_reader(const char* path, float* values, std::size_t count, void* context) {
    if (count != 4) return false;
    const int mode = *static_cast<int*>(context);
    if (mode == 1) return false;
    const float fixture[] = {1.0f / 1024, -1.0f / 1024, 3.0f / 1024, -3.0f / 1024};
    for (unsigned i = 0; i < 4; ++i)
        values[i] = std::strstr(path, "w.bin") ? fixture[i] : 0.0f;
    if (mode == 2) values[0] = NAN;
    if (mode == 3) values[0] = 64.0f;
    return true;
}

static void verify_loader() {
    BasicConv fixture(1, 1, 1, 1, 0, 1, 4);
    int mode = 0;
    if (!fixture.load_weight("fixture", fixture_reader, &mode)) { ++test_errors; return; }
    const data_t expected[] = {1, -1, 2, -2};
    for (unsigned i = 0; i < 4; ++i) if (fixture.weight[i] != expected[i]) ++test_errors;
    ++loader_checks;
    for (mode = 1; mode <= 3; ++mode) {
        if (fixture.load_weight("fixture", fixture_reader, &mode)) ++test_errors;
        for (unsigned i = 0; i < 4; ++i) if (fixture.weight[i] != expected[i]) ++test_errors;
        ++loader_checks;
    }
}

static bool jtag_reader(const char* path, float* values, std::size_t count, void*) {
    const std::size_t length = std::strlen(pc_directory);
    if (std::strncmp(path, pc_directory, length) != 0) return false;
    if (std::strcmp(path + length, "/w.bin") == 0 && count == weight_count) {
        std::memcpy(values, raw_weight, sizeof(raw_weight));
        test_loaded |= 1;
        return true;
    }
    if (std::strcmp(path + length, "/b.bin") == 0 && count == bias_count) {
        std::memcpy(values, raw_bias, sizeof(raw_bias));
        test_loaded |= 2;
        return true;
    }
    return false;
}

int main() {
    conv_init();
    verify_loader();
    BasicConv layer(416, 416, 3, 2, 1, 3, 32);
    Xil_DCacheFlushRange((INTPTR)raw_weight, sizeof(raw_weight));
    Xil_DCacheFlushRange((INTPTR)raw_bias, sizeof(raw_bias));
    Xil_DCacheFlushRange((INTPTR)pc_directory, sizeof(pc_directory));
    Xil_DCacheInvalidateRange((INTPTR)raw_weight, sizeof(raw_weight));
    Xil_DCacheInvalidateRange((INTPTR)raw_bias, sizeof(raw_bias));
    Xil_DCacheInvalidateRange((INTPTR)pc_directory, sizeof(pc_directory));
    test_stage = 1;
    test_load_ready();
    if (!layer.load_weight(pc_directory, jtag_reader)) { test_stage = 5; test_finished(); }
    for (int i = 0; i < weight_count; ++i) {
        if (layer.weight[i] != static_cast<data_t>(std::round(raw_weight[i] * 512.0f))) ++test_errors;
        if (layer.weight[i] < weight_min) weight_min = layer.weight[i];
        if (layer.weight[i] > weight_max) weight_max = layer.weight[i];
    }
    for (int i = 0; i < bias_count; ++i) {
        if (layer.bias[i] != static_cast<data_t>(std::round(raw_bias[i] * 512.0f))) ++test_errors;
        if (layer.bias[i] < bias_min) bias_min = layer.bias[i];
        if (layer.bias[i] > bias_max) bias_max = layer.bias[i];
    }
    for (int i = 0; i < input_count; ++i) input[i] = 512;
    for (int i = 0; i < output_count + 32; ++i) output[i] = -12345;
    Xil_DCacheFlushRange((INTPTR)input, sizeof(input));
    Xil_DCacheFlushRange((INTPTR)layer.weight, weight_count * sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)layer.bias, bias_count * sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)output, sizeof(output));
    test_stage = 2;
    layer.forward(input, output);
    test_stage = 3;
    Xil_DCacheInvalidateRange((INTPTR)output, sizeof(output));
    for (int i = 0; i < output_count; ++i) {
        if (output[i] < output_min) output_min = output[i];
        if (output[i] > output_max) output_max = output[i];
        if (output[i] != -12345) ++output_changed;
        ++test_checked;
    }
    if (output_changed == 0) ++test_errors;
    for (int i = 0; i < 32; ++i) if (output[output_count + i] != -12345) ++test_errors;
    test_stage = test_errors ? 5 : 4;
    test_finished();
    return 0;
}
