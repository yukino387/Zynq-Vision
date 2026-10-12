#include "build/model.h"
#include "xconv.h"
#include "xil_cache.h"
#include "xiltimer.h"
#include <cstring>
#include "gray.h"
#include "build/gray_expected.h"

extern "C" {
int8_t features[feature_bytes+64] __attribute__((aligned(64)));
int8_t weights[weight_bytes+64] __attribute__((aligned(64)));
int32_t metadata[metadata_words+16] __attribute__((aligned(64)));
volatile unsigned test_stage, test_errors, forward_us[3], stage_hashes[35];
uint16_t gray_pixels[416*416] __attribute__((aligned(64)));
int8_t gray_data[224*224] __attribute__((aligned(64)));
volatile unsigned preprocessing_us;
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
    preprocessing_us=(preprocessing_end-preprocessing_begin)*1000000u/COUNTS_PER_SECOND;
    uint32_t gray_hash=2166136261u;
    for(unsigned i=0;i<224*224;++i) gray_hash=(gray_hash^uint8_t(gray_data[i]))*16777619u;
    if(gray_hash!=gray_expected_hash) ++test_errors;
    std::memset(features+feature_bytes,0x55,64);
    std::memset(weights+weight_bytes,0x55,64);
    std::memset(metadata+metadata_words,0x55,64);
    Xil_DCacheFlush();
    XConv_Set_in1(&engine,(uintptr_t)features); XConv_Set_in2(&engine,(uintptr_t)features);
    XConv_Set_in3(&engine,(uintptr_t)features); XConv_Set_in4(&engine,(uintptr_t)features);
    XConv_Set_w1_r(&engine,(uintptr_t)weights); XConv_Set_w2_r(&engine,(uintptr_t)weights);
    XConv_Set_w3_r(&engine,(uintptr_t)weights); XConv_Set_w4_r(&engine,(uintptr_t)weights);
    XConv_Set_out1(&engine,(uintptr_t)features); XConv_Set_out2(&engine,(uintptr_t)features);
    XConv_Set_out3(&engine,(uintptr_t)features); XConv_Set_out4(&engine,(uintptr_t)features);
    XConv_Set_b(&engine,(uintptr_t)metadata); XConv_Set_ch_in(&engine,command_count);
    XConv_Set_kernel(&engine,4);
    test_stage=2;
    for (unsigned run=0;run<3;++run) {
        XTime begin,end,now;
        XTime_GetTime(&begin);
        XConv_Start(&engine);
        while(!XConv_IsDone(&engine)) {
            XTime_GetTime(&now);
            if(now-begin>2*COUNTS_PER_SECOND) { ++test_errors; test_stage=99; test_finished(); return 1; }
        }
        XTime_GetTime(&end);
        forward_us[run]=(end-begin)*1000000u/COUNTS_PER_SECOND;
        Xil_DCacheInvalidateRange((INTPTR)features,sizeof(features));
        for (unsigned j=0;j<sizeof(checks)/sizeof(checks[0]);++j) {
            uint32_t hash=2166136261u;
            for (unsigned i=0;i<checks[j].count;++i) hash=(hash^uint8_t(features[checks[j].offset+i]))*16777619u;
            stage_hashes[j]=hash;
            if(hash!=expected_hashes[j]) ++test_errors;
        }
    }
    Xil_DCacheInvalidate();
    for(unsigned i=0;i<64;++i) {
        if(features[feature_bytes+i]!=0x55 || weights[weight_bytes+i]!=0x55 ||
           reinterpret_cast<uint8_t*>(metadata+metadata_words)[i]!=0x55) ++test_errors;
    }
    test_stage=3;
    test_finished();
    return test_errors ? 1 : 0;
}
