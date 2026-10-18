#include "model.h"
#include "model_store.h"
#include "firmware_ota.h"
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
uint16_t pixels[2][CAMERA_PIXELS] __attribute__((aligned(64)));
int8_t gray_data[3*224*224];
int8_t out0[1617],out1[6468];
}

static uint32_t microseconds(XTime ticks) {
    return uint32_t(ticks*1000000u/(COUNTS_PER_SECOND));
}

static unsigned forward(XConv& engine,unsigned current,uint32_t frame,bool preview,
                        bool& pending,bool& armed,unsigned& prepared_rows,uint32_t& conversion_us,uint32_t& transfer_us,bool& transmission_failed) {
    Xil_DCacheFlushRange((INTPTR)features,metadata[4]*224*256);
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
        // BasicConv3 is the longest layer; send this frame while it runs.
        if(layer==23 && preview) {
            XTime send_begin,send_end;
            XTime_GetTime(&send_begin);
            if(!udp_send_frame(frame,2,pixels[current],CAMERA_BYTES)) transmission_failed=true;
            XTime_GetTime(&send_end);
            transfer_us+=microseconds(send_end-send_begin);
        }
        while(!XConv_IsDone(&engine)) {
            XTime_GetTime(&now);
            if(now-begin>2*(COUNTS_PER_SECOND)) return 4;
            firmware_watchdog_kick();
            udp_poll();
            if(pending && camera_ready()) {
                if(!camera_finish(pixels[1-current])) return 2;
                pending=false;
            }
            if(!pending && !armed && (!preview || layer>=23)) {
                if(!camera_begin(pixels[current])) return 2;
                armed=true;
            }
            if(!pending && prepared_rows<640) {
                XTime work_begin,work_end;
                XTime_GetTime(&work_begin);
                model_input_rows(pixels[1-current],gray_data,prepared_rows,8,metadata[4]);
                prepared_rows+=8;
                XTime_GetTime(&work_end);
                conversion_us+=microseconds(work_end-work_begin);
            }
        }
    }
    Xil_DCacheInvalidateRange((INTPTR)(features+out0_offset),33*7*8);
    Xil_DCacheInvalidateRange((INTPTR)(features+out1_offset),33*14*16);
    for(unsigned i=0;i<1617;++i) out0[i]=features[out0_offset+(i/7)*8+i%7];
    for(unsigned i=0;i<6468;++i) out1[i]=features[out1_offset+(i/14)*16+i%14];
    return 0;
}

int main() {
    // Start the watchdog and load the OTA record before any init that can fail:
    // a trial image that cannot reach the main loop must still reset and roll back.
    firmware_init();
    XConv engine;
    if(XConv_Initialize(&engine,0x43c00000)!=0) return 1;
    Xil_DCacheFlush();
    if(!camera_udp_init()) return 1;
    model_store_init();
    CameraStatus status={0x31545343,0,0x7020,0,0,0,0,0,0,0,0,0};
    XTime trial_deadline=0;
    if(firmware_trial_pending()) {
        XTime_GetTime(&trial_deadline);
        trial_deadline+=20ULL*COUNTS_PER_SECOND;
    }
    while(!camera_init()) {
        firmware_watchdog_kick();
        firmware_service();
        if(firmware_trial_pending()) {
            XTime now;XTime_GetTime(&now);
            if(now>=trial_deadline) firmware_confirm_fail();
        }
        status.errors=1;udp_pause();udp_send_status(status);
        while(!udp_running()){
            firmware_watchdog_kick();firmware_service();udp_poll();usleep(1000);
        }
    }
    if(firmware_trial_pending()) firmware_confirm_ok();
    unsigned current=0;
    bool pending=false;
    bool frame_captured=false,armed=false;
    unsigned prepared_rows=0;
    unsigned prepared_channels=0;
    for(uint32_t frame=0;;++frame) {
        udp_poll();
        model_service();
        firmware_watchdog_kick();
        firmware_service();
        while((!udp_running() || !model_available()) && !model_test_pending()) {
            firmware_watchdog_kick();firmware_service();
            udp_poll(); model_service();
            status.errors=model_available()?status.errors:5;
            static XTime heartbeat=0;XTime now;XTime_GetTime(&now);
            if(now-heartbeat>=COUNTS_PER_SECOND){udp_send_status(status);heartbeat=now;}
            usleep(1000);
        }
        const unsigned channels=metadata[4];
        if(prepared_channels!=channels) {prepared_rows=0;prepared_channels=channels;}
        if(status.brightness!=udp_brightness()) {
            if(!camera_set_brightness(udp_brightness())) { status.errors=1; udp_send_status(status);udp_pause();continue; }
            status.brightness=udp_brightness();
        }
        const bool inference=!udp_camera_only() || model_test_pending();
        const bool preview=udp_client_ready() && udp_preview_enabled();
        XTime begin,captured,converted,predicted,sent;
        XTime_GetTime(&begin);
        if(!frame_captured && ((!pending && !camera_begin(pixels[current])) || !camera_finish(pixels[current]))) {
            status.errors=2; model_complete_test(false); udp_send_status(status); udp_pause();
            frame_captured=false;pending=false;armed=false;prepared_rows=0;continue;
        }
        pending=false;
        XTime_GetTime(&captured);
        if(!armed && !camera_begin(pixels[1-current])) { status.errors=2;model_complete_test(false);udp_send_status(status);udp_pause();frame_captured=false;pending=false;armed=false;prepared_rows=0;continue; }
        armed=false;
        pending=true;
        if(inference) {
            if(prepared_rows<640) model_input_rows(pixels[current],gray_data,prepared_rows,640-prepared_rows,channels);
            for(unsigned c=0;c<channels;++c) for(unsigned row=0;row<224;++row)
                std::memcpy(features+c*224*256+row*256,gray_data+c*224*224+row*224,224);
        }
        XTime_GetTime(&converted);
        prepared_rows=0;
        uint32_t conversion_us=0,transfer_us=0;
        bool transmission_failed=false;
        const unsigned error=inference ? forward(engine,current,frame,preview,pending,armed,prepared_rows,conversion_us,transfer_us,transmission_failed) : 0;
        model_complete_test(!error);
        if(error) { status.errors=error; udp_send_status(status);udp_pause();frame_captured=false;pending=false;armed=false;prepared_rows=0;continue; }
        XTime_GetTime(&predicted);
        if(udp_client_ready() && ((inference && (!udp_send_frame(frame,0,out0,1617) ||
            !udp_send_frame(frame,1,out1,6468))) ||
            (!inference && preview && !udp_send_frame(frame,2,pixels[current],CAMERA_BYTES)))) transmission_failed=true;
        status.errors=transmission_failed?3:0;
        XTime_GetTime(&sent);
        status.frame=frame;
        status.capture_us=microseconds(captured-begin);
        status.conversion_us=conversion_us+microseconds(converted-captured);
        status.inference_us=microseconds(predicted-converted);
        status.transfer_us=transfer_us+microseconds(sent-predicted);
        status.cycle_us=microseconds(sent-begin);
        udp_send_status(status);
        frame_captured=!pending;
        current=1-current;
    }
}
