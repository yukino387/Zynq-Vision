#include "yolo4_tiny.h"
#include "camera/camera_input.h"
#include "camera/udp_output.h"
#include "expected.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xiltimer.h"
#include <cstring>

extern "C" {
float raw_files[TOTAL_FLOATS] __attribute__((aligned(64)));
char pc_directory[1024] __attribute__((aligned(64)));
uint16_t pixels[CAMERA_PIXELS + 32] __attribute__((aligned(64)));
data_t input_data[3 * CAMERA_PIXELS] __attribute__((aligned(64)));
data_t out0_storage[Yolo4_Tiny::OUT0_COUNT + 32] __attribute__((aligned(64)));
data_t out1_storage[Yolo4_Tiny::OUT1_COUNT + 32] __attribute__((aligned(64)));
volatile unsigned test_stage, test_errors, test_loaded, test_frames, forward_us;
volatile unsigned capture_us, conversion_us, transfer_us, cycle_us;
__attribute__((noinline)) void test_load_ready() { asm volatile("nop"); }
__attribute__((noinline)) void test_finished() { asm volatile("nop"); }
}
static bool pc_reader(const char* path, float* values, std::size_t count, void*) {
    const std::size_t prefix = std::strlen(pc_directory);
    if (std::strncmp(path, pc_directory, prefix) || path[prefix] != '/') return false;
    for (const auto& file : expected_files) {
        if (!std::strcmp(path + prefix + 1, file.name) && count == file.count) {
            std::memcpy(values, raw_files + file.offset, count * sizeof(float));
            ++test_loaded;
            return true;
        }
    }
    return false;
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
    if (!network.load_weight(pc_directory, pc_reader) || test_loaded != 42) test_errors = 1;
    if (!test_errors && !camera_init()) test_errors = 2;
    if (!test_errors && !camera_udp_init()) test_errors = 3;
    if (test_errors) { test_finished(); return 1; }
    conv_init();
    test_stage = 3;
    XTime start, end;
    XTime_GetTime(&start);
    while (!udp_client_ready()) {
        udp_poll();
        XTime_GetTime(&end);
        if (end - start > 60ULL * COUNTS_PER_SECOND) { test_errors = 4; break; }
    }
    for (unsigned frame = 0; frame < 3 && !test_errors; ++frame) {
        XTime cycle_start, captured, converted, predicted, sent;
        XTime_GetTime(&cycle_start);
        if (!camera_capture(pixels)) { test_errors = 5; break; }
        XTime_GetTime(&captured);
        camera_to_input(pixels, input_data);
        XTime_GetTime(&converted);
        XTime_GetTime(&start);
        network.forward(input_data, out0_storage, out1_storage);
        XTime_GetTime(&end);
        forward_us = static_cast<unsigned>((end - start) * 1000000ULL / (COUNTS_PER_SECOND));
        Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(out0_storage), sizeof(out0_storage));
        Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(out1_storage), sizeof(out1_storage));
        XTime_GetTime(&predicted);
        if (!udp_send_frame(frame, 0, out0_storage, Yolo4_Tiny::OUT0_COUNT * 2) ||
            !udp_send_frame(frame, 1, out1_storage, Yolo4_Tiny::OUT1_COUNT * 2) ||
            (udp_preview_enabled() && !udp_send_frame(frame, 2, pixels, CAMERA_BYTES))) {
            test_errors = 6;
            break;
        }
        ++test_frames;
        XTime_GetTime(&sent);
        capture_us = (captured - cycle_start) * 1000000ULL / (COUNTS_PER_SECOND);
        conversion_us = (converted - captured) * 1000000ULL / (COUNTS_PER_SECOND);
        transfer_us = (sent - predicted) * 1000000ULL / (COUNTS_PER_SECOND);
        cycle_us = (sent - cycle_start) * 1000000ULL / (COUNTS_PER_SECOND);
        xil_printf("Camera YOLO frame %u forward=%u us\r\n", frame, forward_us);
    }
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(out0_storage), sizeof(out0_storage));
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(out1_storage), sizeof(out1_storage));
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(pixels), sizeof(pixels));
    test_stage = 4;
    test_finished();
    return test_errors ? 1 : 0;
}
