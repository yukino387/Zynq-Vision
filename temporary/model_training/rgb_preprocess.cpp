#include <cstdint>
#include <fstream>
#include <vector>
#include <iostream>
#include <cstring>
#include "gray_coefficients.h"
static uint8_t clip(int v){return v<0?0:v>255?255:v;}
void gray_input_rows(const uint16_t*,int8_t*,unsigned,unsigned){}
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

int main(){std::ifstream a("temporary/model_training/artifacts/sensor.rgb565",std::ios::binary),b("temporary/model_training/artifacts/RGB-input.bin",std::ios::binary);std::vector<uint16_t> p(416*416);std::vector<int8_t> o(3*224*224),e(o.size());a.read((char*)p.data(),p.size()*2);b.read((char*)e.data(),e.size());for(unsigned r=0;r<640;r+=8)model_input_rows(p.data(),o.data(),r,8,3);if(o!=e)return 1;std::cout<<"PASS: PS RGB preprocessing matches Python at every byte"<<std::endl;}