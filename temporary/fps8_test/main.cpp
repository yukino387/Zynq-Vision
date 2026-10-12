#include "yolo4_tiny.h"
#include "../full_weight_test/expected.h"
#include "input_expected.h"
#include "xiltimer.h"
#include "xil_cache.h"
#include <cstring>
#include <cstdint>

extern "C" {
data_t input_data[CSPDarkNet::INPUT_COUNT] __attribute__((aligned(64)));
data_t out0_storage[Yolo4_Tiny::OUT0_COUNT + 64] __attribute__((aligned(64)));
data_t out1_storage[Yolo4_Tiny::OUT1_COUNT + 64] __attribute__((aligned(64)));
volatile int input_min = 0, input_max = 0, out0_min = 0, out0_max = 0, out1_min = 0, out1_max = 0;
volatile unsigned forward_us = 0, timer_counts_per_second = COUNTS_PER_SECOND;
volatile unsigned out0_changed = 0, out1_changed = 0;
float raw_files[TOTAL_FLOATS] __attribute__((aligned(64)));
char pc_directory[1024] __attribute__((aligned(64)));
volatile int test_stage = 0, test_errors = 0, test_loaded = 0, test_verified = 0;
volatile unsigned test_checked = 0;
struct FileResult { unsigned count; int low, high; uint32_t hash; unsigned reads; };
FileResult file_results[FILE_COUNT];
__attribute__((noinline)) void test_load_ready() { asm volatile("nop"); }
__attribute__((noinline)) void test_finished() { asm volatile("nop"); }
}

static bool pc_reader(const char* path, float* values, std::size_t count, void*) {
    const std::size_t prefix = std::strlen(pc_directory);
    if (std::strncmp(path, pc_directory, prefix) || path[prefix] != '/') return false;
    for (int i = 0; i < FILE_COUNT; ++i) {
        const ExpectedFile& file = expected_files[i];
        if (!std::strcmp(path + prefix + 1, file.name) && count == file.count) {
            std::memcpy(values, raw_files + file.offset, count * sizeof(float));
            ++file_results[i].reads;
            ++test_loaded;
            return true;
        }
    }
    return false;
}

static void verify(int index, const data_t* values, std::size_t count) {
    const ExpectedFile& expected = expected_files[index];
    FileResult& result = file_results[index];
    result.count = count;
    result.low = 32767;
    result.high = -32768;
    result.hash = 2166136261u;
    for (std::size_t i = 0; i < count; ++i) {
        const int value = values[i];
        if (value < result.low) result.low = value;
        if (value > result.high) result.high = value;
        const uint16_t bits = static_cast<uint16_t>(values[i]);
        result.hash = (result.hash ^ (bits & 255u)) * 16777619u;
        result.hash = (result.hash ^ (bits >> 8)) * 16777619u;
    }
    test_checked += count;
    if (count != expected.count || result.low != expected.low || result.high != expected.high ||
        result.hash != expected.hash || result.reads != 1) ++test_errors;
    else ++test_verified;
}

static data_t sampling_input[3 * 26 * 26 + 32] __attribute__((aligned(64)));
static data_t sampling_output[3 * 26 * 26 * 4 + 32] __attribute__((aligned(64)));
volatile unsigned sampling_checked;
static void check_sampling() {
    for (int mode = 0; mode < 2; ++mode) for (int run = 0; run < 2; ++run) {
        const int size = run == 0 ? 8 : (mode ? 26 : 13);
        const int output_size = mode ? size / 2 : size * 2;
        const int count = 3 * size * size, output_count = 3 * output_size * output_size;
        for (int i = 0; i < count; ++i) sampling_input[i] = ((i * 9973 + 12345) & 65535) - 32768;
        sampling_input[0] = -32768; sampling_input[1] = 32767;
        for (int i = 0; i < output_count + 32; ++i) sampling_output[i] = -12345;
        Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(sampling_input), (count + 32) * sizeof(data_t));
        sampling(sampling_input, sampling_output, 3, size, mode);
        for (int c = 0; c < 3; ++c) for (int y = 0; y < output_size; ++y) for (int x = 0; x < output_size; ++x) {
            int expected = sampling_input[c * size * size + (mode ? 2 * y : y / 2) * size + (mode ? 2 * x : x / 2)];
            if (mode) for (int ky = 0; ky < 2; ++ky) for (int kx = 0; kx < 2; ++kx) {
                const int value = sampling_input[c * size * size + (2 * y + ky) * size + 2 * x + kx];
                if (value > expected) expected = value;
            }
            if (sampling_output[c * output_size * output_size + y * output_size + x] != expected) ++test_errors;
            ++sampling_checked;
        }
        for (int i = 0; i < 32; ++i) if (sampling_output[output_count + i] != -12345) ++test_errors;
    }
}

int main() {
    check_sampling();
    test_stage = 1;
    Yolo4_Tiny network;
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(raw_files), sizeof(raw_files));
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(raw_files), sizeof(raw_files));
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(pc_directory), sizeof(pc_directory));
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(pc_directory), sizeof(pc_directory));
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(input_data), sizeof(input_data));
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(input_data), sizeof(input_data));
    test_load_ready();
    test_stage = 2;
    if (!network.load_weight(pc_directory, pc_reader)) {
        ++test_errors;
    } else {
        BasicConv* layers[] = {
            network.backbone->basic_conv1, network.backbone->basic_conv2, network.backbone->basic_conv3,
            network.backbone->resblock1->conv1, network.backbone->resblock1->conv2,
            network.backbone->resblock1->conv3, network.backbone->resblock1->conv4,
            network.backbone->resblock2->conv1, network.backbone->resblock2->conv2,
            network.backbone->resblock2->conv3, network.backbone->resblock2->conv4,
            network.backbone->resblock3->conv1, network.backbone->resblock3->conv2,
            network.backbone->resblock3->conv3, network.backbone->resblock3->conv4,
            network.conv_forP5_conv, network.yolo_headP4_basic_conv1, nullptr,
            network.yolo_headP5_basic_conv1, nullptr, network.upsample_conv
        };
        for (int i = 0; i < FILE_COUNT / 2; ++i) {
            if (layers[i]) {
                const BasicConv& conv = *layers[i];
                verify(2 * i, conv.weight, static_cast<std::size_t>(conv.ch_out) * conv.ch_in * conv.k * conv.k);
                verify(2 * i + 1, conv.bias, conv.ch_out);
            } else if (i == 17) {
                verify(2 * i, network.yolo_headP4_w2, Yolo4_Tiny::OUT_CH * 256);
                verify(2 * i + 1, network.yolo_headP4_b2, Yolo4_Tiny::OUT_CH);
            } else {
                verify(2 * i, network.yolo_headP5_w2, Yolo4_Tiny::OUT_CH * 512);
                verify(2 * i + 1, network.yolo_headP5_b2, Yolo4_Tiny::OUT_CH);
            }
        }
    }
    test_stage = 3;
    uint32_t input_hash = 2166136261u;
    input_min = 32767; input_max = -32768;
    for (int i = 0; i < CSPDarkNet::INPUT_COUNT; ++i) {
        const int value = input_data[i];
        if (value < input_min) input_min = value;
        if (value > input_max) input_max = value;
        const uint16_t bits = static_cast<uint16_t>(value);
        input_hash = (input_hash ^ (bits & 255u)) * 16777619u;
        input_hash = (input_hash ^ (bits >> 8)) * 16777619u;
    }
    if (input_hash != INPUT_HASH || input_min != INPUT_MIN || input_max != INPUT_MAX) ++test_errors;
    if (!test_errors) {
        for (unsigned i = 0; i < sizeof(out0_storage) / sizeof(data_t); ++i) out0_storage[i] = -12345;
        for (unsigned i = 0; i < sizeof(out1_storage) / sizeof(data_t); ++i) out1_storage[i] = -12345;
        Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(out0_storage), sizeof(out0_storage));
        Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(out1_storage), sizeof(out1_storage));
        conv_init();
        XTime start, end;
        XTime_GetTime(&start);
        network.forward(input_data, out0_storage + 32, out1_storage + 32);
        XTime_GetTime(&end);
        forward_us = static_cast<unsigned>((end - start) * 1000000ULL / (COUNTS_PER_SECOND));
        Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(out0_storage), sizeof(out0_storage));
        Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(out1_storage), sizeof(out1_storage));
        out0_min = out1_min = 32767; out0_max = out1_max = -32768;
        for (int i = 0; i < Yolo4_Tiny::OUT0_COUNT; ++i) {
            const int value = out0_storage[i + 32];
            if (value < out0_min) out0_min = value;
            if (value > out0_max) out0_max = value;
            if (value != -12345) ++out0_changed;
        }
        for (int i = 0; i < Yolo4_Tiny::OUT1_COUNT; ++i) {
            const int value = out1_storage[i + 32];
            if (value < out1_min) out1_min = value;
            if (value > out1_max) out1_max = value;
            if (value != -12345) ++out1_changed;
        }
        for (int i = 0; i < 32; ++i) {
            if (out0_storage[i] != -12345 || out1_storage[i] != -12345 ||
                out0_storage[32 + Yolo4_Tiny::OUT0_COUNT + i] != -12345 ||
                out1_storage[32 + Yolo4_Tiny::OUT1_COUNT + i] != -12345) ++test_errors;
        }
        if (!out0_changed || !out1_changed || !forward_us) ++test_errors;
    }
    if (test_errors == 0) {
        data_t reference0[Yolo4_Tiny::OUT0_COUNT];
        data_t reference1[Yolo4_Tiny::OUT1_COUNT];
        std::memcpy(reference0, out0_storage + 32, sizeof(reference0));
        std::memcpy(reference1, out1_storage + 32, sizeof(reference1));
        for (int i = 0; i < CSPDarkNet::INPUT_COUNT; ++i) input_data[i] = 512 - input_data[i];
        network.forward(input_data, out0_storage + 32, out1_storage + 32);
        if (!std::memcmp(reference0, out0_storage + 32, sizeof(reference0)) &&
            !std::memcmp(reference1, out1_storage + 32, sizeof(reference1))) ++test_errors;
        for (int i = 0; i < CSPDarkNet::INPUT_COUNT; ++i) input_data[i] = 512 - input_data[i];
        network.forward(input_data, out0_storage + 32, out1_storage + 32);
        if (std::memcmp(reference0, out0_storage + 32, sizeof(reference0)) ||
            std::memcmp(reference1, out1_storage + 32, sizeof(reference1))) ++test_errors;
        for (int i = 0; i < 32; ++i)
            if (out0_storage[i] != -12345 || out1_storage[i] != -12345 ||
                out0_storage[32 + Yolo4_Tiny::OUT0_COUNT + i] != -12345 ||
                out1_storage[32 + Yolo4_Tiny::OUT1_COUNT + i] != -12345) ++test_errors;
    }
    // Make CPU-read output data visible to debugger memory export.
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(out0_storage), sizeof(out0_storage));
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(out1_storage), sizeof(out1_storage));
    test_stage = 4;
    test_finished();
    return test_errors ? 1 : 0;
}
