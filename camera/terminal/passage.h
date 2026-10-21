#pragma once
#include "core.h"
#include "hardware.h"
#include "presence.h"
#include <array>
#include <algorithm>

namespace terminal {
// Consensus compares complete count vectors; it never adds boxes across frames.
class Passage {
    struct Pattern {
        Decision decision;
        Frame frame;
        unsigned support=0,run=0,best_run=0;
        uint64_t run_start_ns=0,last_ns=0,best_span_ns=0;
        bool forbidden=false;
    };
    bool armed_=false,active_=false,ready_=false,interrupted_=false,overflow_=false,conflicting_=false;
    unsigned entering_=0,empty_=0,samples_=0,chosen_=0,previous_=8;
    uint64_t empty_since_=0,last_ns_=0,lost_since_=0;
    std::array<unsigned,4> votes_{};
    std::vector<Pattern> patterns_;
    std::array<Frame,2> entering_frames_;
    std::array<Decision,2> entering_decisions_;
    ScenePresence scene_;
    static bool same(const Decision& a,const Decision& b) {
        if(a.result!=b.result || a.findings.size()!=b.findings.size())return false;
        for(size_t i=0;i<a.findings.size();++i) {
            const auto& x=a.findings[i];const auto& y=b.findings[i];
            if(x.check.class_id!=y.check.class_id || x.count!=y.count || x.uncertain!=y.uncertain)return false;
        }
        return true;
    }
    static bool persistent_defect(const Pattern& p){return p.forbidden && p.best_run>=2 && p.best_span_ns>=60000000ULL;}
    void sample(const Frame& frame,const Decision& decision) {
        ++votes_[unsigned(decision.result)];++samples_;
        size_t index=0;while(index<patterns_.size() && !same(patterns_[index].decision,decision))++index;
        if(index==patterns_.size()) {
            if(index==8){overflow_=true;previous_=8;return;}
            Pattern p;p.decision=decision;
            p.forbidden=decision.result==Result::Fail && std::any_of(decision.findings.begin(),decision.findings.end(),[](const Finding& f){return f.check.maximum==0 && f.count>0;});
            patterns_.push_back(std::move(p));
        }
        auto& p=patterns_[index];
        p.run=previous_==index && frame.monotonic_ns-p.last_ns<=250000000ULL?p.run+1:1;
        if(p.run==1)p.run_start_ns=frame.monotonic_ns;
        if(p.run>p.best_run){p.best_run=p.run;p.best_span_ns=frame.monotonic_ns-p.run_start_ns;}
        else if(p.run==p.best_run)p.best_span_ns=std::max(p.best_span_ns,frame.monotonic_ns-p.run_start_ns);
        ++p.support;p.last_ns=frame.monotonic_ns;p.frame=frame;previous_=index;
    }
public:
    void reset() {*this=Passage{};}
    const char* phase() const {return ready_?"SAVING":active_?"INSPECTING":armed_?"WAITING":"CLEARING";}
    bool active() const {return active_;}
    unsigned samples() const {return samples_;}
    const std::array<unsigned,4>& votes() const {return votes_;}
    bool interrupted() const {return interrupted_;}
    bool ready() const {return ready_;}
    const Frame& evidence() const {return patterns_.at(chosen_).frame;}
    unsigned support() const {return patterns_.at(chosen_).support;}
    unsigned consecutive() const {return patterns_.at(chosen_).best_run;}
    unsigned span_ms() const {return unsigned(patterns_.at(chosen_).best_span_ns/1000000ULL);}
    unsigned patterns() const {return patterns_.size();}
    bool unstable() const {return overflow_ || (conflicting_ && !defect());}
    bool defect() const {return persistent_defect(patterns_.at(chosen_));}
    Decision decision() const {
        auto result=patterns_.at(chosen_).decision;
        if(interrupted_ || samples_<3 || overflow_ || (!defect() && (conflicting_ || support()*5ULL<samples_*3ULL || consecutive()<3 || span_ms()<140)))result.result=Result::Review;
        return result;
    }
    void finish(bool interrupted=false) {
        if(!active_ || !samples_)return;
        interrupted_|=interrupted;ready_=true;chosen_=0;
        unsigned stable=0;
        for(unsigned i=0;i<patterns_.size();++i) {
            const auto& p=patterns_[i];
            if(p.best_run>=3 && p.best_span_ns>=140000000ULL && p.decision.result!=Result::Review)++stable;
            const auto& best=patterns_[chosen_];
            const bool safer=p.decision.result==Result::Review || (p.decision.result==Result::Fail && best.decision.result==Result::Pass);
            if(persistent_defect(p)!=persistent_defect(best)?persistent_defect(p):p.support>best.support || (p.support==best.support && safer))chosen_=i;
        }
        conflicting_=stable>1;
    }
    bool observe(const Frame& frame,const std::vector<Box>& boxes,const Rules& rules,const Decision& decision) {
        if(ready_ || !frame.monotonic_ns || frame.monotonic_ns<=last_ns_)return ready_;
        if(last_ns_ && frame.monotonic_ns-last_ns_>1000000000ULL){
            interrupted_|=active_;entering_=0;empty_=0;empty_since_=0;previous_=8;
            if(!active_)armed_=false;
        }
        last_ns_=frame.monotonic_ns;
        unsigned primary=6;for(const auto& c:rules.checks)if(c.minimum>0)primary=std::min(primary,c.class_id);
        bool detected=false,strong=false,complete=false;
        for(const auto& box:boxes) {
            const auto x=(box.x1+box.x2)/832.0,y=(box.y1+box.y2)/832.0;
            if(box.class_id!=primary || box.confidence<.35 || x<rules.region[0] || x>rules.region[0]+rules.region[2] || y<rules.region[1] || y>rules.region[1]+rules.region[3])continue;
            detected=true;
            if(box.confidence>=rules.confidence && box.track_confirmed) {
                strong=true;
                if(box.x1>=rules.region[0]*416+2 && box.y1>=rules.region[1]*416+2 && box.x2<=(rules.region[0]+rules.region[2])*416-2 && box.y2<=(rules.region[1]+rules.region[3])*416-2)complete=true;
            }
        }
        const auto scene=scene_.observe(frame.pixels,rules.region,!detected && !active_);
        if(active_ && !strong && scene!=ScenePresence::State::Empty) {
            if(!lost_since_)lost_since_=frame.monotonic_ns;
            if(frame.monotonic_ns-lost_since_>uint64_t(rules.postprocess.track_max_gap_ms)*1000000ULL)interrupted_=true;
        }else lost_since_=0;
        if(!detected && scene==ScenePresence::State::Empty) {
            entering_=0;if(!empty_++)empty_since_=frame.monotonic_ns;
            if(empty_>=3 && frame.monotonic_ns-empty_since_>=200000000ULL){if(active_)finish();else armed_=true;}
            previous_=8;
        } else {
            empty_=0;empty_since_=0;
            if(!armed_)return false;
            if(!strong){entering_=0;previous_=8;return false;}
            auto observed=decision;if(!complete)observed.result=Result::Review;
            if(!active_) {
                if(entering_<2){entering_frames_[entering_]=frame;entering_decisions_[entering_]=observed;++entering_;return false;}
                active_=true;
                for(unsigned i=0;i<2;++i)sample(entering_frames_[i],entering_decisions_[i]);
            }
            sample(frame,observed);
        }
        return ready_;
    }
    void committed() {
        auto scene=std::move(scene_);reset();scene_=std::move(scene);armed_=true;
    }
};
}
