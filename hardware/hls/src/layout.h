#pragma once
#include "type.h"
static unsigned size_level(unsigned size) {
#pragma HLS INLINE
    return size==7?0:size==14?1:size==28?2:size==56?3:size==112?4:5;
}
static unsigned row_pitch(unsigned size) {
#pragma HLS INLINE
    return 8u<<size_level(size);
}
static unsigned plane_size(unsigned size) {
#pragma HLS INLINE
    return 7u<<(2*size_level(size)+3);
}
static unsigned channel_base(unsigned channel,unsigned size) {
#pragma HLS INLINE
    return ((channel<<3)-channel)<<(2*size_level(size)+3);
}
