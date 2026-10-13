#include "build/model.h"
#include "xconv.h"
#include "xil_cache.h"
#include "xiltimer.h"
#include <cstring>
#include "camera/int8/gray.h"
static unsigned pitch(unsigned size) { return size==7?8:size==14?16:size==28?32:size==56?64:size==112?128:256; }
#include "build/gray_expected.h"

extern "C" {
int8_t features[feature_bytes+64] __attribute__((aligned(64)));
int8_t weights[weight_bytes+64] __attribute__((aligned(64)));
int32_t metadata[metadata_words+16] __attribute__((aligned(64)));
volatile unsigned test_stage, test_errors, forward_us[3], stage_hashes[35];
volatile unsigned layer_us[command_count];
uint16_t gray_pixels[416*416] __attribute__((aligned(64)));
int8_t gray_data[224*224] __attribute__((aligned(64)));
volatile unsigned preprocessing_us;
int8_t out0[1617],out1[6468];
__attribute__((noinline)) void test_load_ready() { asm volatile("nop"); }
__attribute__((noinline)) void test_finished() { asm volatile("nop"); }
}

int main() {
    XConv engine;
    if (XConv_Initialize(&engine,0x43c00000)!=0) { test_errors=1; test_finished(); return 1; }
    Xil_DCacheFlush();
    test_stage=1;
    test_load_ready();
    Xil_DCacheInvalidate();
    XTime preprocessing_begin,preprocessing_end;
    XTime_GetTime(&preprocessing_begin);
    gray_input(gray_pixels,gray_data);
    XTime_GetTime(&preprocessing_end);
    preprocessing_us=(preprocessing_end-preprocessing_begin)*1000000u/(COUNTS_PER_SECOND);
    uint32_t gray_hash=2166136261u;
    for(unsigned i=0;i<224*224;++i) gray_hash=(gray_hash^uint8_t(gray_data[i]))*16777619u;
    if(gray_hash!=gray_expected_hash) ++test_errors;
    std::memset(features+feature_bytes,0x55,64);
    std::memset(weights+weight_bytes,0x55,64);
    std::memset(metadata+metadata_words,0x55,64);
    Xil_DCacheFlush();
    for (unsigned run=0;run<3;++run) {
        XTime begin,end,now;
        XTime_GetTime(&begin);
        for(unsigned layer=0;layer<command_count;++layer) {
            const int32_t* command=metadata+layer*10;
            XConv_Set_in1(&engine,(uintptr_t)(features+command[0]));
            XConv_Set_in2(&engine,(uintptr_t)(features+command[0]));
            XConv_Set_in3(&engine,(uintptr_t)(features+command[0]));
            XConv_Set_in4(&engine,(uintptr_t)(features+command[0]));
            XConv_Set_out1(&engine,(uintptr_t)(features+command[1]));
            XConv_Set_out2(&engine,(uintptr_t)(features+command[1]));
            XConv_Set_out3(&engine,(uintptr_t)(features+command[1]));
            XConv_Set_out4(&engine,(uintptr_t)(features+command[1]));
            XConv_Set_w1_r(&engine,(uintptr_t)(weights+command[2]));
            XConv_Set_w2_r(&engine,(uintptr_t)(weights+command[2]));
            XConv_Set_w3_r(&engine,(uintptr_t)(weights+command[2]));
            XConv_Set_w4_r(&engine,(uintptr_t)(weights+command[2]));
            XConv_Set_b(&engine,(uintptr_t)(metadata+command[3]));
            XConv_Set_ch_in(&engine,command[4]); XConv_Set_ch_out(&engine,command[5]);
            XConv_Set_fsize(&engine,command[6]); XConv_Set_stride(&engine,command[7]);
            XConv_Set_kernel(&engine,command[8]); XConv_Set_act(&engine,command[9]);
            XTime layer_begin;
            XTime_GetTime(&layer_begin);
            XConv_Start(&engine);
            while(!XConv_IsDone(&engine)) {
                XTime_GetTime(&now);
                if(now-layer_begin>2*(COUNTS_PER_SECOND)) { ++test_errors;test_stage=99;test_finished();return 1; }
            }
            XTime_GetTime(&now);
            layer_us[layer]=(now-layer_begin)*1000000u/(COUNTS_PER_SECOND);
        }
        XTime_GetTime(&end);
        forward_us[run]=(end-begin)*1000000u/(COUNTS_PER_SECOND);
        Xil_DCacheInvalidateRange((INTPTR)features,sizeof(features));
        for (unsigned j=0;j<sizeof(checks)/sizeof(checks[0]);++j) {
            uint32_t hash=2166136261u;
            for (unsigned i=0;i<checks[j].channels*checks[j].size*checks[j].size;++i) hash=(hash^uint8_t(features[checks[j].offset+(i/checks[j].size)*pitch(checks[j].size)+i%checks[j].size]))*16777619u;
            stage_hashes[j]=hash;
            if(hash!=expected_hashes[j]) ++test_errors;
            for(unsigned row=0;row<checks[j].channels*checks[j].size;++row)
                for(unsigned col=checks[j].size;col<pitch(checks[j].size);++col)
                    if(features[checks[j].offset+row*pitch(checks[j].size)+col]!=0) ++test_errors;
        }
    }
    Xil_DCacheFlushRange((INTPTR)layer_us,sizeof(layer_us));
    Xil_DCacheInvalidate();
    for(unsigned i=0;i<64;++i) {
        if(features[feature_bytes+i]!=0x55 || weights[weight_bytes+i]!=0x55 ||
           reinterpret_cast<uint8_t*>(metadata+metadata_words)[i]!=0x55) ++test_errors;
    }
    for(unsigned i=0;i<1617;++i) out0[i]=features[out0_offset+(i/7)*8+i%7];
    for(unsigned i=0;i<6468;++i) out1[i]=features[out1_offset+(i/14)*16+i%14];
    Xil_DCacheFlushRange((INTPTR)out0,sizeof(out0));
    Xil_DCacheFlushRange((INTPTR)out1,sizeof(out1));
    test_stage=3;
    test_finished();
    return test_errors ? 1 : 0;
}
