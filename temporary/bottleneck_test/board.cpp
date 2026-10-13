#include "temporary/int8_rebuild_test/build/model.h"
#include "xconv.h"
#include "xil_cache.h"
#include "xiltimer.h"
#include <cstring>
#include "camera/int8/gray.h"
static unsigned pitch(unsigned size) { return size==7?8:size==14?16:size==28?32:size==56?64:size==112?128:256; }
#include "temporary/int8_rebuild_test/build/gray_expected.h"

extern "C" {
int8_t features[feature_bytes+64] __attribute__((aligned(64)));
int8_t weights[weight_bytes+64] __attribute__((aligned(64)));
int32_t metadata[metadata_words+16] __attribute__((aligned(64)));
volatile unsigned test_stage, test_errors, forward_us[3], stage_hashes[35];
volatile unsigned layer_us[command_count];
volatile unsigned all_layer_us[3][command_count],setup_us[3][command_count],input_flush_us[3];
volatile unsigned probe_us[19][3];
int8_t probe_input[8*224*256] __attribute__((aligned(64)));
int8_t probe_weight[48*512*9] __attribute__((aligned(64)));
int8_t probe_output[48*112*128+64] __attribute__((aligned(64)));
int32_t probe_bias[5*48] __attribute__((aligned(64)));
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
        XTime flush_begin,flush_end;
        XTime_GetTime(&flush_begin);
        Xil_DCacheFlushRange((INTPTR)features,224*256);
        XTime_GetTime(&flush_end);
        input_flush_us[run]=(flush_end-flush_begin)*1000000u/(COUNTS_PER_SECOND);
        XTime_GetTime(&begin);
        for(unsigned layer=0;layer<command_count;++layer) {
            XTime setup_begin;
            XTime_GetTime(&setup_begin);
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
            setup_us[run][layer]=(layer_begin-setup_begin)*1000000u/(COUNTS_PER_SECOND);
            XConv_Start(&engine);
            while(!XConv_IsDone(&engine)) {
                XTime_GetTime(&now);
                if(now-layer_begin>2*(COUNTS_PER_SECOND)) { ++test_errors;test_stage=99;test_finished();return 1; }
            }
            XTime_GetTime(&now);
            layer_us[layer]=(now-layer_begin)*1000000u/(COUNTS_PER_SECOND);
            all_layer_us[run][layer]=layer_us[layer];
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
    Xil_DCacheFlush();
    Xil_DCacheInvalidate();
    for(unsigned i=0;i<64;++i) {
        if(features[feature_bytes+i]!=0x55 || weights[weight_bytes+i]!=0x55 ||
           reinterpret_cast<uint8_t*>(metadata+metadata_words)[i]!=0x55) ++test_errors;
    }
    for(unsigned i=0;i<1617;++i) out0[i]=features[out0_offset+(i/7)*8+i%7];
    for(unsigned i=0;i<6468;++i) out1[i]=features[out1_offset+(i/14)*16+i%14];
    Xil_DCacheFlushRange((INTPTR)out0,sizeof(out0));
    Xil_DCacheFlushRange((INTPTR)out1,sizeof(out1));

    const unsigned cases[19][5]={{512,4,7,1,3},{512,24,7,1,3},{512,48,7,1,3},{512,4,14,1,3},{512,24,14,1,3},{512,48,14,1,3},{8,4,7,1,3},{64,4,7,1,3},{128,4,7,1,3},{256,4,7,1,3},{512,4,7,1,1},{512,48,7,1,1},{1,32,224,2,3},{3,32,224,2,3},{8,32,224,2,3},{128,4,28,1,3},{136,4,28,1,3},{1,4,224,2,3},{1,48,224,2,3}};
    std::memset(probe_input,1,sizeof(probe_input));
    Xil_DCacheFlushRange((INTPTR)probe_input,sizeof(probe_input));
    Xil_DCacheFlushRange((INTPTR)probe_weight,sizeof(probe_weight));
    for(unsigned probe=0;probe<19;++probe) {
        unsigned ci=cases[probe][0],co=cases[probe][1],size=cases[probe][2],stride=cases[probe][3],kernel=cases[probe][4];
        for(unsigned ch=0;ch<co;++ch) {
            probe_bias[ch]=16;
            probe_bias[co+ch]=1;probe_bias[2*co+ch]=1;
            probe_bias[3*co+ch]=1;probe_bias[4*co+ch]=1;
        }
        Xil_DCacheFlushRange((INTPTR)probe_bias,sizeof(probe_bias));
        for(unsigned run=0;run<3;++run) {
            std::memset(probe_output,0x55,sizeof(probe_output));
            Xil_DCacheFlushRange((INTPTR)probe_output,sizeof(probe_output));
            XConv_Set_in1(&engine,(uintptr_t)probe_input); XConv_Set_in2(&engine,(uintptr_t)probe_input);
            XConv_Set_in3(&engine,(uintptr_t)probe_input); XConv_Set_in4(&engine,(uintptr_t)probe_input);
            XConv_Set_w1_r(&engine,(uintptr_t)probe_weight); XConv_Set_w2_r(&engine,(uintptr_t)probe_weight);
            XConv_Set_w3_r(&engine,(uintptr_t)probe_weight); XConv_Set_w4_r(&engine,(uintptr_t)probe_weight);
            XConv_Set_out1(&engine,(uintptr_t)probe_output); XConv_Set_out2(&engine,(uintptr_t)probe_output);
            XConv_Set_out3(&engine,(uintptr_t)probe_output); XConv_Set_out4(&engine,(uintptr_t)probe_output);
            XConv_Set_b(&engine,(uintptr_t)probe_bias);
            XConv_Set_ch_in(&engine,ci);XConv_Set_ch_out(&engine,co);XConv_Set_fsize(&engine,size);
            XConv_Set_stride(&engine,stride);XConv_Set_kernel(&engine,kernel);XConv_Set_act(&engine,1);
            XTime begin,end;
            XTime_GetTime(&begin); XConv_Start(&engine);
            while(!XConv_IsDone(&engine)) {
                XTime_GetTime(&end);
                if(end-begin>2*(COUNTS_PER_SECOND)) {++test_errors;test_stage=99;test_finished();return 1;}
            }
            XTime_GetTime(&end);
            probe_us[probe][run]=(end-begin)*1000000u/(COUNTS_PER_SECOND);
            Xil_DCacheInvalidateRange((INTPTR)probe_output,sizeof(probe_output));
            unsigned out_size=stride==2?size/2:size;
            for(unsigned row=0;row<co*out_size;++row) for(unsigned col=0;col<pitch(out_size);++col)
                if(probe_output[row*pitch(out_size)+col]!=(col<out_size?8:0)) ++test_errors;
            for(unsigned i=0;i<64;++i) if(probe_output[co*out_size*pitch(out_size)+i]!=0x55) ++test_errors;
        }
    }
    test_stage=3;
    Xil_DCacheFlush();
    test_finished();
    return test_errors ? 1 : 0;
}
