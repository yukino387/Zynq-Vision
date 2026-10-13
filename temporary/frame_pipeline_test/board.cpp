#define main camera_application_main
#include "camera/int8/live_main.cpp"
#undef main
#include "temporary/int8_rebuild_test/build/gray_expected.h"
void udp_poll() {}
bool udp_send_frame(uint32_t,uint32_t,const void*,uint32_t) { return false; }
bool camera_ready() { return true; }
bool camera_finish(uint16_t*) { return true; }
extern "C" {
volatile unsigned test_stage,test_errors,forward_us[3];
__attribute__((noinline)) void test_load_ready() { asm volatile("nop"); }
__attribute__((noinline)) void test_finished() { asm volatile("nop"); }
}
int main() {
    XConv engine;
    if(XConv_Initialize(&engine,0x43c00000)) return 1;
    Xil_DCacheFlush();
    test_load_ready();
    Xil_DCacheInvalidate();
    for(unsigned run=0;run<3;++run) {
        bool pending=true;
        unsigned rows=0;
        uint32_t convert=0,send=0;
        XTime begin,end;
        XTime_GetTime(&begin);
        test_errors+=forward(engine,0,run,false,pending,rows,convert,send);
        XTime_GetTime(&end);
        forward_us[run]=microseconds(end-begin);
        uint32_t hash=2166136261u;
        for(unsigned i=0;i<224*224;++i) hash=(hash^uint8_t(gray_data[i]))*16777619u;
        if(hash!=gray_expected_hash || rows!=640 || pending) ++test_errors;
    }
    Xil_DCacheFlush();
    test_stage=3;
    test_finished();
    return test_errors ? 1 : 0;
}
