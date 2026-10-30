#pragma once
#include <array>
#include <algorithm>
#include <cstdint>

namespace terminal {
struct ExposureMeter {
    unsigned p60=0,p95=0,dark=0,high=0; // fractions in permille
};
inline ExposureMeter exposure_meter(const uint16_t* pixels,bool sensor_order) {
    std::array<unsigned,256> histogram{};unsigned count=0,dark=0,high=0;
    // The visible workspace excludes the ceiling and a narrow side border.
    for(unsigned y=112;y<400;y+=12)for(unsigned x=16;x<400;x+=12){
        const unsigned i=sensor_order?(415-y)*416+415-x:y*416+x;
        const auto p=pixels[i];const unsigned r=p>>11,g=(p>>5)&63,b=p&31;
        const unsigned value=(77*((r<<3)|(r>>2))+150*((g<<2)|(g>>4))+29*((b<<3)|(b>>2)))>>8;
        ++histogram[value];++count;dark+=value<20;high+=value>245;
    }
    unsigned sum=0,p60=0,p95=0;
    for(unsigned i=0;i<256;++i){sum+=histogram[i];if(sum*100>=count*60){p60=i;break;}}
    sum=0;for(unsigned i=0;i<256;++i){sum+=histogram[i];if(sum*100>=count*95){p95=i;break;}}
    return {p60,p95,dark*1000/count,high*1000/count};
}
struct ExposurePolicy {
    unsigned target=38;
    int direction=0;
    unsigned consecutive=0;
    uint64_t last_change=0;
    unsigned update(const ExposureMeter& meter,uint64_t now){
        const int next=meter.high>=20?-1:(meter.p60<80 && meter.p95<220 && meter.high<=5)?1:meter.p60>144?-1:0;
        if(!next){direction=0;consecutive=0;return target;}
        if(next!=direction){direction=next;consecutive=1;}else ++consecutive;
        if(consecutive<3 || now-last_change<2000000000ULL)return target;
        target=unsigned(std::clamp(int(target)+2*direction,32,54));
        consecutive=0;last_change=now;return target;
    }
};
}
