#include "../../camera/camera_input.cpp"
extern "C" {
uint16_t bar_images[2][CAMERA_PIXELS+32] __attribute__((aligned(64)));
uint16_t work_pixels[CAMERA_PIXELS+32] __attribute__((aligned(64)));
volatile unsigned quality_error=0, differing_pixels[2][32], elapsed_us[2][32];
__attribute__((noinline)) void quality_finished(){asm volatile("nop");}
}
int main(){
    if(!camera_init()){quality_error=1;quality_finished();return 1;}
    uint8_t awb=0;
    if(!read_register(0x3406,awb) || !write_register(0x3406,awb|1) || !write_register(0x3503,3) || !write_register(0x503d,0x80)){quality_error=2;quality_finished();return 2;}
    for(unsigned mode=0;mode<2 && !quality_error;++mode){
        if(!write_register(0x5584,mode?0x40:0x20)){quality_error=3;break;}
        usleep(200000);
        for(unsigned i=0;i<4;++i)if(!camera_capture(work_pixels)){quality_error=4;break;}
        if(!camera_capture(bar_images[mode])){quality_error=5;break;}
        for(unsigned i=CAMERA_PIXELS;i<CAMERA_PIXELS+32;++i)work_pixels[i]=0xdead;
        Xil_DCacheFlushRange((INTPTR)work_pixels,sizeof(work_pixels));
        for(unsigned frame=0;frame<32 && !quality_error;++frame){
            XTime begin,end;XTime_GetTime(&begin);
            if(!camera_capture(work_pixels)){quality_error=6;break;}
            XTime_GetTime(&end);elapsed_us[mode][frame]=unsigned((end-begin)*1000000/(COUNTS_PER_SECOND));
            unsigned errors=0;
            for(unsigned i=0;i<CAMERA_PIXELS;++i)errors+=work_pixels[i]!=bar_images[mode][i];
            differing_pixels[mode][frame]=errors;
            for(unsigned i=CAMERA_PIXELS;i<CAMERA_PIXELS+32;++i)if(work_pixels[i]!=0xdead)quality_error=7;
        }
    }
    Xil_DCacheFlush();quality_finished();return quality_error;
}
