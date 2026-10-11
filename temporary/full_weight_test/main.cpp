#include "yolo4_tiny.h"
#include "expected.h"
#include "xil_cache.h"
#include <cstring>
#include <cstdint>

extern "C" {
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

int main() {
    test_stage = 1;
    Yolo4_Tiny network;
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(raw_files), sizeof(raw_files));
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(raw_files), sizeof(raw_files));
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(pc_directory), sizeof(pc_directory));
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(pc_directory), sizeof(pc_directory));
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
    test_finished();
    return test_errors ? 1 : 0;
}
