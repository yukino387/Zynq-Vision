#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <vector>

namespace terminal {
// Empty-field reference for a fixed camera: veto exits, never invent counts.
class ScenePresence {
public:
    enum class State { Unknown, Empty, Occupied };
private:
    std::array<uint16_t,1024> background_{};
    unsigned stable_=0;
    bool calibrated_=false;
    static int channel(uint16_t p,unsigned c){return c==0?int((p>>11)*255/31):c==1?int(((p>>5)&63)*255/63):int((p&31)*255/31);}
public:
    State observe(const std::vector<uint16_t>& pixels,const std::array<double,4>& roi,bool learn) {
        if(pixels.size()!=416*416)return State::Unknown;
        std::array<uint16_t,1024> current{};
        for(unsigned y=0;y<32;++y)for(unsigned x=0;x<32;++x) {
            const auto px=std::clamp(int((roi[0]+(x+.5)*roi[2]/32)*416),0,415);
            const auto py=std::clamp(int((roi[1]+(y+.5)*roi[3]/32)*416),0,415);
            const auto p=pixels[py*416+px];current[y*32+x]=p;
        }
        if(!stable_) {
            if(learn){background_=current;stable_=1;}
            return State::Unknown;
        }
        std::array<int,3> shift{};std::array<int,1024> differences;
        for(unsigned c=0;c<3;++c) {
            for(unsigned i=0;i<1024;++i)differences[i]=channel(current[i],c)-channel(background_[i],c);
            std::nth_element(differences.begin(),differences.begin()+512,differences.end());shift[c]=differences[512];
        }
        unsigned changed=0;
        for(unsigned i=0;i<1024;++i) {
            bool foreground=false;
            for(unsigned c=0;c<3;++c)if(std::abs(channel(current[i],c)-channel(background_[i],c)-shift[c])>24)foreground=true;
            changed+=foreground;
        }
        const bool illumination=std::any_of(shift.begin(),shift.end(),[](int v){return std::abs(v)>24;});
        const bool empty=changed<=10 && !illumination;
        if(!calibrated_) {
            if(!learn){stable_=0;return State::Unknown;}
            if(empty){if(++stable_>=3)calibrated_=true;}else{background_=current;stable_=1;}
            return calibrated_?State::Empty:State::Unknown;
        }
        if(empty && learn)for(unsigned i=0;i<1024;++i) {
            const auto a=background_[i],b=current[i];
            const unsigned r=(7*(a>>11)+(b>>11)+4)/8,g=(7*((a>>5)&63)+((b>>5)&63)+4)/8,blue=(7*(a&31)+(b&31)+4)/8;
            background_[i]=uint16_t((r<<11)|(g<<5)|blue);
        }
        return empty?State::Empty:changed>=31?State::Occupied:State::Unknown;
    }
};
}
