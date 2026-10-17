#include "gray.h"
#include "gray_coefficients.h"
#include <arm_neon.h>

static uint8_t horizontal[416][224];
static uint8_t gray[424];
static uint8_t clip(int value) { return value<0 ? 0 : value>255 ? 255 : value; }

void gray_input_rows(const uint16_t* pixels,int8_t* input,unsigned first,unsigned count) {
    const unsigned end=first+count;
    for(unsigned y=first;y<end && y<416;++y) {
        for(unsigned x=0;x<416;x+=8) {
            const uint16x8_t p=vld1q_u16(pixels+y*416+x);
            const uint16x8_t r5=vshrq_n_u16(p,11),g6=vandq_u16(vshrq_n_u16(p,5),vdupq_n_u16(63));
            const uint16x8_t b5=vandq_u16(p,vdupq_n_u16(31));
            const uint16x8_t r=vorrq_u16(vshlq_n_u16(r5,3),vshrq_n_u16(r5,2));
            const uint16x8_t g=vorrq_u16(vshlq_n_u16(g6,2),vshrq_n_u16(g6,4));
            const uint16x8_t b=vorrq_u16(vshlq_n_u16(b5,3),vshrq_n_u16(b5,2));
            uint32x4_t low=vmull_n_u16(vget_low_u16(r),19595);
            low=vmlal_n_u16(low,vget_low_u16(g),38470);
            low=vmlal_n_u16(low,vget_low_u16(b),7471);
            uint32x4_t high=vmull_n_u16(vget_high_u16(r),19595);
            high=vmlal_n_u16(high,vget_high_u16(g),38470);
            high=vmlal_n_u16(high,vget_high_u16(b),7471);
            low=vaddq_u32(low,vdupq_n_u32(32768));
            high=vaddq_u32(high,vdupq_n_u32(32768));
            const uint16x8_t luma=vcombine_u16(vshrn_n_u32(low,16),vshrn_n_u32(high,16));
            vst1_u8(gray+x,vmovn_u16(luma));
        }
        for(unsigned x=0;x<224;++x) {
            const auto& coeff=resize_coefficients[x];
            const uint16x8_t values=vmovl_u8(vld1_u8(gray+coeff.start));
            const int32x4_t low=vmulq_s32(vreinterpretq_s32_u32(vmovl_u16(vget_low_u16(values))),vld1q_s32(coeff.value));
            const int32x4_t high=vmulq_s32(vreinterpretq_s32_u32(vmovl_u16(vget_high_u16(values))),vld1q_s32(coeff.value+4));
            const int32x4_t sum=vaddq_s32(low,high);
            const int32x2_t pairs=vpadd_s32(vget_low_s32(sum),vget_high_s32(sum));
            const int result=vget_lane_s32(vpadd_s32(pairs,pairs),0);
            horizontal[y][x]=clip((result+(1<<21))>>22);
        }
    }
    for(unsigned row=first<416 ? 416 : first;row<end && row<640;++row) {
        const unsigned y=row-416;
        const auto& coeff=resize_coefficients[y];
        for(unsigned x=0;x<224;x+=8) {
            int32x4_t low=vdupq_n_s32(1<<21),high=low;
            for(unsigned k=0;k<coeff.count;++k) {
                const uint16x8_t values=vmovl_u8(vld1_u8(horizontal[coeff.start+k]+x));
                low=vmlaq_n_s32(low,vreinterpretq_s32_u32(vmovl_u16(vget_low_u16(values))),coeff.value[k]);
                high=vmlaq_n_s32(high,vreinterpretq_s32_u32(vmovl_u16(vget_high_u16(values))),coeff.value[k]);
            }
            const uint16x8_t bounded=vcombine_u16(vqmovun_s32(vshrq_n_s32(low,22)),vqmovun_s32(vshrq_n_s32(high,22)));
            const uint8x8_t values=vqmovn_u16(bounded);
            const uint16x8_t numerator=vaddq_u16(vmull_u8(values,vdup_n_u8(127)),vdupq_n_u16(127));
            const uint16x8_t quotient=vshrq_n_u16(vaddq_u16(vaddq_u16(numerator,vdupq_n_u16(1)),vshrq_n_u16(numerator,8)),8);
            vst1_s8(input+y*224+x,vreinterpret_s8_u8(vmovn_u16(quotient)));
        }
    }
}

void gray_input(const uint16_t* pixels,int8_t* input) {
    gray_input_rows(pixels,input,0,640);
}

void model_input_rows(const uint16_t* pixels,int8_t* input,unsigned first,unsigned count,unsigned channels) {
    if(channels==1) {gray_input_rows(pixels,input,first,count);return;}
    static uint8_t rgb_horizontal[3][416][224];
    uint8_t rgb[3][416];
    const unsigned end=first+count;
    for(unsigned y=first;y<end && y<416;++y) {
        for(unsigned x=0;x<416;++x) {
            const unsigned p=pixels[y*416+x],r=p>>11,g=(p>>5)&63,b=p&31;
            rgb[0][x]=(r<<3)|(r>>2);rgb[1][x]=(g<<2)|(g>>4);rgb[2][x]=(b<<3)|(b>>2);
        }
        for(unsigned c=0;c<3;++c) for(unsigned x=0;x<224;++x) {
            const auto& coeff=resize_coefficients[x];
            int sum=1<<21;
            for(unsigned k=0;k<coeff.count;++k) sum+=rgb[c][coeff.start+k]*coeff.value[k];
            rgb_horizontal[c][y][x]=clip(sum>>22);
        }
    }
    for(unsigned row=first<416?416:first;row<end && row<640;++row) {
        const unsigned y=row-416;
        const auto& coeff=resize_coefficients[y];
        for(unsigned c=0;c<3;++c) for(unsigned x=0;x<224;++x) {
            int sum=1<<21;
            for(unsigned k=0;k<coeff.count;++k) sum+=rgb_horizontal[c][coeff.start+k][x]*coeff.value[k];
            input[c*224*224+y*224+x]=(clip(sum>>22)*127+127)/255;
        }
    }
}
