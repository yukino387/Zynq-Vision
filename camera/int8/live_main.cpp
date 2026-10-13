#include "model.h"
#include "gray.h"
#include "camera/camera_input.h"
#include "camera/udp_output.h"
#include "xconv.h"
#include "xil_cache.h"
#include "xiltimer.h"
#include "sleep.h"
#include <cstring>

extern "C" {
int8_t features[feature_bytes] __attribute__((aligned(64)));
extern const int8_t weights[];
extern const int32_t metadata[];
uint16_t pixels[2][CAMERA_PIXELS] __attribute__((aligned(64)));
int8_t gray_data[224*224];
int8_t out0[1617],out1[6468];
}

static bool forward(XConv& engine) {
    Xil_DCacheFlushRange((INTPTR)features,224*256);
    XTime begin,now;
    XTime_GetTime(&begin);
    for(unsigned layer=0;layer<command_count;++layer) {
        const int32_t* c=metadata+layer*10;
        XConv_Set_in1(&engine,(uintptr_t)(features+c[0]));
        XConv_Set_in2(&engine,(uintptr_t)(features+c[0]));
        XConv_Set_in3(&engine,(uintptr_t)(features+c[0]));
        XConv_Set_in4(&engine,(uintptr_t)(features+c[0]));
        XConv_Set_w1_r(&engine,(uintptr_t)(weights+c[2]));
        XConv_Set_w2_r(&engine,(uintptr_t)(weights+c[2]));
        XConv_Set_w3_r(&engine,(uintptr_t)(weights+c[2]));
        XConv_Set_w4_r(&engine,(uintptr_t)(weights+c[2]));
        XConv_Set_out1(&engine,(uintptr_t)(features+c[1]));
        XConv_Set_out2(&engine,(uintptr_t)(features+c[1]));
        XConv_Set_out3(&engine,(uintptr_t)(features+c[1]));
        XConv_Set_out4(&engine,(uintptr_t)(features+c[1]));
        XConv_Set_b(&engine,(uintptr_t)(metadata+c[3]));
        XConv_Set_ch_in(&engine,c[4]); XConv_Set_ch_out(&engine,c[5]);
        XConv_Set_fsize(&engine,c[6]); XConv_Set_stride(&engine,c[7]);
        XConv_Set_kernel(&engine,c[8]); XConv_Set_act(&engine,c[9]);
        XConv_Start(&engine);
        while(!XConv_IsDone(&engine)) {
            XTime_GetTime(&now);
            if(now-begin>2*(COUNTS_PER_SECOND)) return false;
        }
    }
    Xil_DCacheInvalidateRange((INTPTR)(features+out0_offset),33*7*8);
    Xil_DCacheInvalidateRange((INTPTR)(features+out1_offset),33*14*16);
    for(unsigned i=0;i<1617;++i) out0[i]=features[out0_offset+(i/7)*8+i%7];
    for(unsigned i=0;i<6468;++i) out1[i]=features[out1_offset+(i/14)*16+i%14];
    return true;
}

int main() {
    XConv engine;
    if(XConv_Initialize(&engine,0x43c00000)!=0) return 1;
    Xil_DCacheFlush();
    if(!camera_init() || !camera_udp_init()) return 1;
    while(!udp_client_ready()) udp_poll();
    CameraStatus status={0x31545343,0,0x7020,0,0,0,0,0,0,0,0,0};
    unsigned current=0;
    bool pending=false;
    auto microseconds=[](XTime ticks) { return uint32_t(ticks*1000000u/(COUNTS_PER_SECOND)); };
    for(uint32_t frame=0;;++frame) {
        udp_poll();
        while(!udp_running()) { udp_poll(); usleep(1000); }
        if(status.brightness!=udp_brightness()) {
            if(!camera_set_brightness(udp_brightness())) { status.errors=1; udp_send_status(status); return 1; }
            status.brightness=udp_brightness();
        }
        XTime begin,captured,converted,predicted,sent;
        XTime_GetTime(&begin);
        if((!pending && !camera_begin(pixels[current])) || !camera_finish(pixels[current])) {
            status.errors=2; udp_send_status(status); return 2;
        }
        pending=false;
        XTime_GetTime(&captured);
        if(!camera_begin(pixels[1-current])) { status.errors=2; udp_send_status(status); return 2; }
        pending=true;
        const bool inference=!udp_camera_only();
        if(inference) {
            gray_input(pixels[current],gray_data);
            for(unsigned row=0;row<224;++row) std::memcpy(features+row*256,gray_data+row*224,224);
        }
        XTime_GetTime(&converted);
        if(inference && !forward(engine)) { status.errors=4; udp_send_status(status); return 4; }
        XTime_GetTime(&predicted);
        if((inference && (!udp_send_frame(frame,0,out0,1617) ||
            !udp_send_frame(frame,1,out1,6468))) ||
            (udp_preview_enabled() && !udp_send_frame(frame,2,pixels[current],CAMERA_BYTES))) {
            status.errors=3; udp_send_status(status); return 3;
        }
        XTime_GetTime(&sent);
        status.frame=frame;
        status.capture_us=microseconds(captured-begin);
        status.conversion_us=microseconds(converted-captured);
        status.inference_us=microseconds(predicted-converted);
        status.transfer_us=microseconds(sent-predicted);
        status.cycle_us=microseconds(sent-begin);
        udp_send_status(status);
        current=1-current;
    }
}
