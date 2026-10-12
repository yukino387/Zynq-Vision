#include "../../camera/camera_input.cpp"

extern "C" {
uint16_t probe_pixels[CAMERA_PIXELS + 32] __attribute__((aligned(64)));
volatile uint32_t probe_result[40];
__attribute__((noinline)) void probe_done() { asm volatile("nop"); }
}

int main() {
    probe_result[0] = camera_init() ? 1 : 0;
    const uint16_t registers[] = {0x3035,0x3036,0x3037,0x3108,0x380c,0x380d,
        0x380e,0x380f,0x3500,0x3501,0x3502,0x3503,0x350a,0x350b,
        0x350c,0x350d,0x3a00,0x3a02,0x3a03,0x3a14,0x3a15};
    for (unsigned i=0; i<sizeof(registers)/sizeof(registers[0]); ++i) {
        uint8_t value=0;
        probe_result[1+i] = read_register(registers[i], value) ? value : 0xffffffff;
    }
    for (unsigned i=0; i<16; ++i) {
        XTime before, after;
        XTime_GetTime(&before);
        const bool ok=camera_capture(probe_pixels);
        XTime_GetTime(&after);
        probe_result[22+i] = ok ? (after-before)*1000000ULL/(COUNTS_PER_SECOND) : 0xffffffff;
    }
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(probe_result),sizeof(probe_result));
    probe_done();
    for (;;) {}
}
