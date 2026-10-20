#pragma once
#include "core.h"
#include "hardware.h"
#include <array>
#include <algorithm>

namespace terminal {
// A single separated product per passage. Empty-field confirmation arms the next one.
class Passage {
    bool armed_=false,active_=false,ready_=false,interrupted_=false;
    unsigned entering_=0,empty_=0,samples_=0;
    uint64_t empty_since_=0,last_ns_=0;
    std::array<unsigned,4> votes_{};
    std::array<Frame,4> evidence_;
    std::array<Decision,4> decisions_;
    unsigned chosen_=0;
public:
    void reset() {*this=Passage{};}
    const char* phase() const {return ready_?"SAVING":active_?"INSPECTING":armed_?"WAITING":"CLEARING";}
    bool active() const {return active_;}
    unsigned samples() const {return samples_;}
    const std::array<unsigned,4>& votes() const {return votes_;}
    bool interrupted() const {return interrupted_;}
    bool ready() const {return ready_;}
    const Frame& evidence() const {return evidence_[chosen_];}
    Decision decision() const {
        auto result=decisions_[chosen_];
        if(interrupted_ || samples_<3 || votes_[chosen_]*5<samples_*3)result.result=Result::Review;
        return result;
    }
    void finish(bool interrupted=false) {
        if(!active_ || !samples_)return;
        interrupted_|=interrupted;ready_=true;
        // Ties prefer uncertainty/failure; never combine boxes from different frames.
        chosen_=unsigned(Result::Review);
        for(unsigned candidate:{unsigned(Result::Error),unsigned(Result::Fail),unsigned(Result::Pass)})
            if(votes_[candidate]>votes_[chosen_])chosen_=candidate;
    }
    bool observe(const Frame& frame,const std::vector<Box>& boxes,const Rules& rules,const Decision& decision) {
        if(ready_ || !frame.monotonic_ns || frame.monotonic_ns<=last_ns_)return ready_;
        if(last_ns_ && frame.monotonic_ns-last_ns_>1000000000ULL){
            interrupted_|=active_;entering_=0;empty_=0;empty_since_=0;
            if(!active_)armed_=false;
        }
        last_ns_=frame.monotonic_ns;
        bool present=false;
        for(const auto& box:boxes) {
            const auto x=(box.x1+box.x2)/832.0,y=(box.y1+box.y2)/832.0;
            const bool required=std::any_of(rules.checks.begin(),rules.checks.end(),[&](const Check& check){return check.class_id==box.class_id && check.minimum>0;});
            if(required && box.class_id<rules.classes && box.confidence>=.35 &&
               x>=rules.region[0] && x<=rules.region[0]+rules.region[2] &&
               y>=rules.region[1] && y<=rules.region[1]+rules.region[3]){present=true;break;}
        }
        if(!present) {
            entering_=0;if(!empty_++)empty_since_=frame.monotonic_ns;
            if(empty_>=3 && frame.monotonic_ns-empty_since_>=200000000ULL) {
                if(active_)finish();else armed_=true;
            }
        } else {
            empty_=0;empty_since_=0;
            if(!armed_)return false;
            if(!active_ && ++entering_<3)return false;
            active_=true;
            const unsigned index=unsigned(decision.result);
            ++votes_[index];++samples_;
            evidence_[index]=frame;decisions_[index]=decision;
        }
        return ready_;
    }
    void committed() {
        // The leaving window already established an empty field.
        reset();armed_=true;
    }
};
}
