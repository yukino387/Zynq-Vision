#include "../../camera/camera_input.cpp"
extern "C" {
uint16_t probe_pixels[CAMERA_PIXELS+32] __attribute__((aligned(64)));
volatile unsigned capture_us[3][8], probe_error=0;
volatile uint8_t sensor_values[3][16];
__attribute__((noinline)) void probe_finished() {asm volatile("nop");}
}
int main() {
    if(!camera_init()) {probe_error=1;probe_finished();return 1;}
    const uint16_t addresses[]={0x3034,0x3035,0x3036,0x3037,0x3108,0x3824,0x380c,0x380d,0x380e,0x380f,0x3500,0x3501,0x3502,0x350a,0x350b,0x3a00};
    for(unsigned mode=0;mode<3 && !probe_error;++mode) {
        if(!write_register(0x3824,mode==1?2:4) || !write_register(0x3037,mode==2?0x03:0x13)) {probe_error=2;break;}
        usleep(200000);
        for(unsigned i=0;i<16;++i) {
            uint8_t value=0;
            if(!read_register(addresses[i],value)) probe_error=3;
            sensor_values[mode][i]=value;
        }
        for(unsigned i=CAMERA_PIXELS;i<CAMERA_PIXELS+32;++i)probe_pixels[i]=0xdead;
        Xil_DCacheFlushRange((INTPTR)probe_pixels,sizeof(probe_pixels));
        if(!camera_capture(probe_pixels)) {probe_error=4;break;}
        for(unsigned i=0;i<8;++i) {
            XTime begin,end;
            XTime_GetTime(&begin);
            if(!camera_capture(probe_pixels)) {probe_error=5;break;}
            XTime_GetTime(&end);
            capture_us[mode][i]=unsigned((end-begin)*1000000/(COUNTS_PER_SECOND));
            for(unsigned j=CAMERA_PIXELS;j<CAMERA_PIXELS+32;++j) if(probe_pixels[j]!=0xdead)probe_error=6;
        }
    }
    Xil_DCacheFlush();
    probe_finished();
    return probe_error;
}
