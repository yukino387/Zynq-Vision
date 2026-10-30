#pragma once
#include "core.h"
#include <algorithm>
#include <cmath>
#include <map>

namespace terminal {
// Product ROI and the required class's optional ROI both constrain counting.
struct CountingRegion {
    unsigned class_id=6;
    double x1,y1,x2,y2;
    explicit CountingRegion(const Rules& rules):x1(rules.region[0]*416),y1(rules.region[1]*416),
        x2((rules.region[0]+rules.region[2])*416),y2((rules.region[1]+rules.region[3])*416) {
        const Check* primary=nullptr;
        for(const auto& c:rules.checks)if(c.minimum>0 && c.class_id<class_id){class_id=c.class_id;primary=&c;}
        if(primary && primary->positioned) {
            x1=std::max(x1,primary->region[0]*416);y1=std::max(y1,primary->region[1]*416);
            x2=std::min(x2,(primary->region[0]+primary->region[2])*416);
            y2=std::min(y2,(primary->region[1]+primary->region[3])*416);
        }
    }
    bool overlaps(const Box& b) const {
        return b.class_id==class_id && x2>x1 && y2>y1 && b.x2>x1-2 && b.x1<x2+2 && b.y2>y1-2 && b.y1<y2+2;
    }
    bool complete(const Box& b) const {
        return b.class_id==class_id && b.x1>=x1+2 && b.y1>=y1+2 && b.x2<=x2-2 && b.y2<=y2-2;
    }
};

// Each track proves its own passage across the ROI centre. Two observations
// on each side suppress boundary jitter; the larger displacement selects the
// crossing axis, so horizontal, vertical and diagonal belts need no setup.
class BeltCounter {
    struct Track {
        std::array<double,2> first{};
        std::array<int,2> origin{},candidate{};
        std::array<unsigned,2> entering{},leaving{};
        uint64_t last_ns=0,sequence=0;
        bool counted=false;
    };
    std::map<unsigned,Track> tracks_;
    uint64_t last_ns_=0,sequence_=0;
    unsigned total_=0,lost_=0;
public:
    void reset(){*this=BeltCounter{};}
    unsigned total() const{return total_;}
    unsigned lost() const{return lost_;}
    void update(const std::vector<Box>& boxes,uint64_t now,const Rules& rules) {
        if(!now || now<=last_ns_)return;
        last_ns_=now;++sequence_;
        const CountingRegion region(rules);
        const uint64_t gap=uint64_t(rules.postprocess.track_max_gap_ms)*1000000ULL;
        for(const auto& b:boxes) {
            if(!b.track_id || !b.track_confirmed || b.confidence<rules.confidence || !region.complete(b))continue;
            const std::array<double,2> p{((b.x1+b.x2)/2-region.x1)/(region.x2-region.x1),
                                       ((b.y1+b.y2)/2-region.y1)/(region.y2-region.y1)};
            auto& t=tracks_[b.track_id];
            if(t.last_ns && now-t.last_ns>gap) {
                if(!t.counted)++lost_;
                const bool counted=t.counted;t=Track{};t.counted=counted;
            }
            if(!t.last_ns)t.first=p;
            if(t.sequence+1!=sequence_)t.entering=t.leaving={};
            t.last_ns=now;t.sequence=sequence_;
            if(t.counted)continue;
            const std::array<double,2> displacement{p[0]-t.first[0],p[1]-t.first[1]};
            for(unsigned axis=0;axis<2;++axis) {
                const int side=p[axis]<=.42?-1:p[axis]>=.58?1:0;
                if(!t.origin[axis]) {
                    t.entering[axis]=side && side==t.candidate[axis]?t.entering[axis]+1:side?1:0;
                    t.candidate[axis]=side;
                    if(t.entering[axis]>=2)t.origin[axis]=side;
                }
                t.leaving[axis]=side && side==-t.origin[axis]?t.leaving[axis]+1:0;
                // Require motion through the centre on the dominant axis;
                // a new downstream ID or a stationary target cannot pass this.
                if(t.leaving[axis]>=2 && std::abs(displacement[axis])>=std::abs(displacement[axis^1])) {
                    t.counted=true;++total_;break;
                }
            }
        }
        for(auto it=tracks_.begin();it!=tracks_.end();) {
            if(now-it->second.last_ns>gap) {
                if(!it->second.counted)++lost_;
                it=tracks_.erase(it);
            } else ++it;
        }
        while(tracks_.size()>2*rules.postprocess.max_detections) {
            const auto oldest=std::min_element(tracks_.begin(),tracks_.end(),[](const auto& a,const auto& b){return a.second.last_ns<b.second.last_ns;});
            if(!oldest->second.counted)++lost_;
            tracks_.erase(oldest);
        }
    }
};
}
