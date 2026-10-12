#include "gray.h"
#include "build/gray_coefficients.h"

static uint8_t horizontal[416][224];
static uint8_t gray[416];
static uint8_t clip(int value) { return value<0 ? 0 : value>255 ? 255 : value; }

void gray_input(const uint16_t* pixels,int8_t* input) {
    for(unsigned y=0;y<416;++y) {
        for(unsigned x=0;x<416;++x) {
            const unsigned pixel=pixels[y*416+x];
            const unsigned r5=pixel>>11,g6=(pixel>>5)&63,b5=pixel&31;
            const unsigned r=(r5<<3)|(r5>>2),g=(g6<<2)|(g6>>4),b=(b5<<3)|(b5>>2);
            gray[x]=(19595*r+38470*g+7471*b+32768)>>16;
        }
        for(unsigned x=0;x<224;++x) {
            const auto& coeff=resize_coefficients[x];
            int32_t sum=1<<21;
            for(unsigned k=0;k<coeff.count;++k) sum+=gray[coeff.start+k]*coeff.value[k];
            horizontal[y][x]=clip(sum>>22);
        }
    }
    for(unsigned y=0;y<224;++y) {
        const auto& coeff=resize_coefficients[y];
        for(unsigned x=0;x<224;++x) {
            int32_t sum=1<<21;
            for(unsigned k=0;k<coeff.count;++k) sum+=horizontal[coeff.start+k][x]*coeff.value[k];
            const unsigned value=clip(sum>>22);
            input[y*224+x]=(value*127+127)/255;
        }
    }
}
