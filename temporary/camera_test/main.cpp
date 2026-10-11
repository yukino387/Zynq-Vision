#include "camera/camera_input.h"
#include "xil_printf.h"
#include "xil_cache.h"
extern "C" {
uint16_t camera_pixels[CAMERA_PIXELS + 32] __attribute__((aligned(64)));
data_t camera_input[3 * CAMERA_PIXELS] __attribute__((aligned(64)));
volatile int camera_stage = 0, camera_errors = 0, camera_frames = 0;
volatile unsigned camera_hash = 0;
volatile int camera_min = 0, camera_max = 0;
__attribute__((noinline)) void camera_test_finished() { asm volatile("nop"); }
}
int main() {
    camera_stage = 1;
    if (!camera_init()) { camera_errors = 1; camera_test_finished(); return 1; }
    camera_stage = 2;
    for (unsigned frame = 0; frame < 3; ++frame) {
        for (unsigned i = 0; i < CAMERA_PIXELS + 32; ++i) camera_pixels[i] = 0xdead;
        Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(camera_pixels), sizeof(camera_pixels));
        if (!camera_capture(camera_pixels)) { camera_errors = 2; break; }
        Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(camera_pixels), sizeof(camera_pixels));
        for (unsigned i = CAMERA_PIXELS; i < CAMERA_PIXELS + 32; ++i)
            if (camera_pixels[i] != 0xdead) camera_errors = 3;
        camera_to_input(camera_pixels, camera_input);
        camera_min = 512; camera_max = 0; camera_hash = 2166136261u;
        for (unsigned i = 0; i < 3 * CAMERA_PIXELS; ++i) {
            const int value = camera_input[i];
            if (value < camera_min) camera_min = value;
            if (value > camera_max) camera_max = value;
            if (value < 0 || value > 512) camera_errors = 4;
            camera_hash = (camera_hash ^ static_cast<unsigned>(value)) * 16777619u;
        }
        ++camera_frames;
        xil_printf("Camera frame %u input=%d..%d hash=%08x\r\n", frame, camera_min, camera_max, camera_hash);
    }
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(camera_input), sizeof(camera_input));
    camera_stage = 3;
    camera_test_finished();
    return camera_errors;
}
