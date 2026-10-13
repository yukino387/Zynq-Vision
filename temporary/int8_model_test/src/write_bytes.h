#pragma once
#include "type.h"

template<unsigned Lane,unsigned Capacity>
static void write_bytes(uint64_t* output,unsigned start,const data_t values[Capacity],unsigned count) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=values cyclic factor=8
    unsigned consumed=0;
    if(start&7) {
        const unsigned first=start&7;
        const unsigned bytes=count<8-first ? count : 8-first;
        uint64_t word=output[start>>3];
        for(unsigned byte=0;byte<8;++byte) {
#pragma HLS UNROLL
            if(byte>=first && byte<first+bytes) {
                word &= ~(uint64_t(255)<<(byte*8));
                word |= uint64_t(uint8_t(values[byte-first]))<<(byte*8);
            }
        }
        output[start>>3]=word;
        start+=bytes;
        consumed=bytes;
    }
    const unsigned words=(count-consumed)>>3;
    for(unsigned index=0;index<words;++index) {
#pragma HLS PIPELINE II=1
        uint64_t word=0;
        for(unsigned byte=0;byte<8;++byte) {
#pragma HLS UNROLL
            word |= uint64_t(uint8_t(values[consumed+index*8+byte]))<<(byte*8);
        }
        output[(start>>3)+index]=word;
    }
    start+=words*8;
    consumed+=words*8;
    if(consumed<count) {
        uint64_t word=output[start>>3];
        for(unsigned byte=0;byte<8;++byte) {
#pragma HLS UNROLL
            if(consumed+byte<count) {
                word &= ~(uint64_t(255)<<(byte*8));
                word |= uint64_t(uint8_t(values[consumed+byte]))<<(byte*8);
            }
        }
        output[start>>3]=word;
    }
}
