#include "yolo4_tiny.h"
#include "camera/camera_input.h"
#include "camera/udp_output.h"
#include "expected.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xiltimer.h"
#include "sleep.h"
#include <cstring>

extern "C" {
float raw_files[TOTAL_FLOATS] __attribute__((aligned(64)));
char pc_directory[1024] __attribute__((aligned(64)));
uint16_t pixels[2][CAMERA_PIXELS + 32] __attribute__((aligned(64)));
data_t input_data[3 * CAMERA_PIXELS] __attribute__((aligned(64)));
data_t out0_storage[Yolo4_Tiny::OUT0_COUNT + 32] __attribute__((aligned(64)));
data_t out1_storage[Yolo4_Tiny::OUT1_COUNT + 32] __attribute__((aligned(64)));
__attribute__((noinline)) void test_load_ready() { asm volatile("nop"); }
}
static bool pc_reader(const char* path, float* values, std::size_t count, void*) {
    const std::size_t prefix = std::strlen(pc_directory);
    if (std::strncmp(path, pc_directory, prefix) || path[prefix] != '/') return false;
    for (const auto& file : expected_files) {
        if (!std::strcmp(path + prefix + 1, file.name) && count == file.count) {
            std::memcpy(values, raw_files + file.offset, count * sizeof(float));
            return true;
        }
    }
    return false;
}
int main() {
    Yolo4_Tiny network;
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(raw_files), sizeof(raw_files));
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(raw_files), sizeof(raw_files));
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(pc_directory), sizeof(pc_directory));
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(pc_directory), sizeof(pc_directory));
    test_load_ready();
    if (!network.load_weight(pc_directory, pc_reader) || !camera_init() || !camera_udp_init()) return 1;
    conv_init();
    while (!udp_client_ready()) udp_poll();
    CameraStatus status = {0x31545343, 0, 0x7020, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    unsigned current = 0;
    bool pending = false;
    XTime cycle_begin, captured, converted, predicted, sent;
    auto microseconds = [](XTime ticks) { return static_cast<uint32_t>(ticks * 1000000ULL / (COUNTS_PER_SECOND)); };
    for (uint32_t frame = 0;; ++frame) {
        udp_poll();
        while (!udp_running()) { udp_poll(); usleep(1000); }
        if (status.brightness != udp_brightness()) {
            if (!camera_set_brightness(udp_brightness())) { status.errors = 1; udp_send_status(status); return 4; }
            status.brightness = udp_brightness();
        }
        XTime_GetTime(&cycle_begin);
        if ((!pending && !camera_begin(pixels[current])) || !camera_finish(pixels[current])) {
            status.errors = 2; udp_send_status(status); return 2;
        }
        pending = false;
        XTime_GetTime(&captured);
        const bool inference = !udp_camera_only();
        if (inference) camera_to_input(pixels[current], input_data);
        XTime_GetTime(&converted);
        // Capture the next image while the existing accelerator processes this input.
        if (!camera_begin(pixels[1 - current])) { status.errors = 2; udp_send_status(status); return 2; }
        pending = true;
        if (inference) {
            network.forward(input_data, out0_storage, out1_storage);
            Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(out0_storage), sizeof(out0_storage));
            Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(out1_storage), sizeof(out1_storage));
        }
        XTime_GetTime(&predicted);
        if ((inference && (!udp_send_frame(frame, 0, out0_storage, Yolo4_Tiny::OUT0_COUNT * 2) ||
            !udp_send_frame(frame, 1, out1_storage, Yolo4_Tiny::OUT1_COUNT * 2))) ||
            (udp_preview_enabled() && !udp_send_frame(frame, 2, pixels[current], CAMERA_BYTES))) {
            status.errors = 3; udp_send_status(status); return 3;
        }
        XTime_GetTime(&sent);
        status.frame = frame;
        status.capture_us = microseconds(captured - cycle_begin);
        status.conversion_us = microseconds(converted - captured);
        status.inference_us = microseconds(predicted - converted);
        status.transfer_us = microseconds(sent - predicted);
        status.cycle_us = microseconds(sent - cycle_begin);
        udp_send_status(status);
        current = 1 - current;
    }
}
