#include "core.h"
#include "../int8/sha256.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace terminal {
bool product_classes_match(const std::vector<std::string>& product, const std::vector<std::string>& model) {
    if(product.empty() || product.size()>6 || model.size()!=6)return false;
    for(size_t i=0;i<model.size();++i)if(model[i]!=(i<product.size()?product[i]:"_unused_"+std::to_string(i)))return false;
    return true;
}
const char* name(Result result) {
    switch(result) { case Result::Pass:return "PASS"; case Result::Fail:return "FAIL"; case Result::Review:return "REVIEW"; default:return "ERROR"; }
}
std::string sha256(const void* data, unsigned size) {
    Sha256 hash; hash.update(data, size); uint8_t digest[32]; hash.finish(digest);
    const char* hex="0123456789abcdef"; std::string text;
    for (unsigned i=0;i<32;++i) { text+=hex[digest[i]>>4]; text+=hex[digest[i]&15]; }
    return text;
}
Decision evaluate(const Rules& rules, const std::vector<Box>& boxes, bool has_output, bool quality_pass, unsigned error) {
    Decision result;
    if(error) { result.result=Result::Error;return result; }
    if(!has_output || (rules.quality_gate && !quality_pass)) return result;
    if(!rules.classes || rules.classes>6 || rules.checks.size()!=rules.classes || !std::isfinite(rules.confidence) || rules.confidence<.35 || rules.confidence>.99) return result;
    std::array<bool,6> configured{};
    for(const auto& c:rules.checks) {
        if(c.class_id>=rules.classes || configured[c.class_id] || c.maximum<c.minimum) return result;
        if(c.positioned) {
            for(auto v:c.region)if(!std::isfinite(v) || v<0 || v>1)return result;
            if(c.region[2]<=0 || c.region[3]<=0 || c.region[0]+c.region[2]>1.000001 || c.region[1]+c.region[3]>1.000001)return result;
        }
        configured[c.class_id]=true;
    }
    const auto& r=rules.region;
    for(auto v:r) if(!std::isfinite(v) || v<0 || v>1) return result;
    if(r[2]<=0 || r[3]<=0 || r[0]+r[2]>1.000001 || r[1]+r[3]>1.000001) return result;
    std::array<unsigned,6> count{}, uncertain{};
    bool unexpected=false, uncertain_extra=false;
    for(const auto& b:boxes) {
        if(!std::isfinite(b.confidence) || !std::isfinite(b.x1) || !std::isfinite(b.y1) || !std::isfinite(b.x2) || !std::isfinite(b.y2) || b.confidence<0 || b.confidence>1 || b.x1<0 || b.y1<0 || b.x2>416 || b.y2>416 || b.x2<=b.x1 || b.y2<=b.y1) { result.result=Result::Error; return result; }
        const double x=(b.x1+b.x2)/832.0,y=(b.y1+b.y2)/832.0;
        if(x<r[0] || y<r[1] || x>r[0]+r[2] || y>r[1]+r[3]) { ++result.outside;continue; }
        if(b.confidence<.35) continue;
        const auto check=std::find_if(rules.checks.begin(),rules.checks.end(),[&](const Check& c){return c.class_id==b.class_id;});
        if(check!=rules.checks.end() && check->positioned){const auto& p=check->region;if(x<p[0] || x>p[0]+p[2] || y<p[1] || y>p[1]+p[3])continue;}
        if(b.class_id>=rules.classes) { if(b.confidence>=rules.confidence) unexpected=true;else uncertain_extra=true; }
        else if(b.confidence>=rules.confidence) ++count[b.class_id];else ++uncertain[b.class_id];
    }
    result.result=unexpected?Result::Fail:uncertain_extra?Result::Review:Result::Pass;
    for(const auto& c:rules.checks) {
        const unsigned n=count[c.class_id],u=uncertain[c.class_id];
        const auto state=n>c.maximum || n+u<c.minimum?Result::Fail:n<c.minimum || n+u>c.maximum?Result::Review:Result::Pass;
        result.findings.push_back({c,n,u,state});
        if(state==Result::Fail) result.result=Result::Fail;
        else if(state==Result::Review && result.result!=Result::Fail) result.result=Result::Review;
    }
    return result;
}
static double sigmoid(double x) { return 1/(1+std::exp(-x)); }
static double overlap(const Box& a,const Box& b) {
    const double intersection=std::max(0.0,std::min(a.x2,b.x2)-std::max(a.x1,b.x1))*std::max(0.0,std::min(a.y2,b.y2)-std::max(a.y1,b.y1));
    const double total=(a.x2-a.x1)*(a.y2-a.y1)+(b.x2-b.x1)*(b.y2-b.y1)-intersection;
    return total>0?intersection/total:0;
}
static std::vector<Box> decode_candidates(const int8_t* out0,const int8_t* out1) {
    static const double anchors[2][6]={{1.3629538461538462,1.3798076923076923,2.2716615384615384,2.843723076923077,5.788461538461538,5.367815384615384},{.7740384615384615,.9086538461538461,1.2451923076923077,1.9519230769230769,2.7259615384615383,2.7596153846153846}};
    static const double scales[]={.11581249687615341,.15977688286248154};
    std::vector<Box> candidates;
    for(unsigned head=0;head<2;++head) {
        const auto raw=head?out1:out0; const unsigned size=head?14:7;
        for(unsigned a=0;a<3;++a) for(unsigned cell=0;cell<size*size;++cell) {
            auto value=[&](unsigned channel){return raw[(a*11+channel)*size*size+cell]*scales[head];};
            const double obj=sigmoid(value(4)); if(obj<.35)continue;
            unsigned cls=0; for(unsigned c=1;c<6;++c)if(value(5+c)>value(5+cls))cls=c;
            const double score=obj*sigmoid(value(5+cls));if(score<.35)continue;
            const double x=(sigmoid(value(0))+cell%size)*416/size,y=(sigmoid(value(1))+cell/size)*416/size;
            const double w=std::exp(value(2))*anchors[head][a*2]*416/size,h=std::exp(value(3))*anchors[head][a*2+1]*416/size;
            candidates.push_back({cls,score,x-w/2,y-h/2,x+w/2,y+h/2});
        }
    }
    return candidates;
}
std::vector<Box> detect(const int8_t* out0,const int8_t* out1) {
    auto candidates=decode_candidates(out0,out1);
    std::stable_sort(candidates.begin(),candidates.end(),[](const Box& a,const Box& b){return a.confidence>b.confidence;});
    std::vector<Box> kept;
    for(const auto& box:candidates) {
        bool suppress=false;for(const auto& k:kept)if(k.class_id==box.class_id && overlap(k,box)>.45){suppress=true;break;}
        if(!suppress) kept.push_back(box);
    }
    for(auto& b:kept){b.x1=std::max(0.0,b.x1);b.y1=std::max(0.0,b.y1);b.x2=std::min(416.0,b.x2);b.y2=std::min(416.0,b.y2);}
    return kept;
}
static double box_area(const Box& b){return (b.x2-b.x1)*(b.y2-b.y1);}
FilterResult filter_boxes(const std::vector<Box>& candidates,const Postprocess& policy) {
    FilterResult result;result.candidates=candidates.size();std::vector<Box> clean,leaves,kept;
    for(auto b:candidates) {
        if(b.class_id>5 || !std::isfinite(b.confidence) || !std::isfinite(b.x1) || !std::isfinite(b.y1) || !std::isfinite(b.x2) || !std::isfinite(b.y2) || b.confidence<0 || b.confidence>1 || b.x2<=b.x1 || b.y2<=b.y1){++result.invalid;continue;}
        if(b.confidence<.35)continue;
        b.x1=std::clamp(b.x1,0.0,416.0);b.y1=std::clamp(b.y1,0.0,416.0);b.x2=std::clamp(b.x2,0.0,416.0);b.y2=std::clamp(b.y2,0.0,416.0);
        if(b.x2-b.x1<1 || b.y2-b.y1<1 || box_area(b)<policy.min_area*416*416){++result.tiny;continue;}
        clean.push_back(b);
    }
    for(size_t i=0;i<clean.size();++i) {
        bool nested=false;const auto& outer=clean[i];
        for(size_t j=0;j<clean.size();++j){const auto& inner=clean[j];
            if(i==j || outer.class_id!=inner.class_id || box_area(outer)<1.5*box_area(inner))continue;
            const double intersection=std::max(0.0,std::min(outer.x2,inner.x2)-std::max(outer.x1,inner.x1))*std::max(0.0,std::min(outer.y2,inner.y2)-std::max(outer.y1,inner.y1));
            if(intersection/box_area(inner)>=policy.containment){nested=true;break;}
        }
        if(nested)++result.nested;else leaves.push_back(outer);
    }
    std::stable_sort(leaves.begin(),leaves.end(),[](const Box& a,const Box& b){return a.confidence==b.confidence?box_area(a)<box_area(b):a.confidence>b.confidence;});
    for(const auto& b:leaves){
        const bool suppressed=std::any_of(kept.begin(),kept.end(),[&](const Box& k){return k.class_id==b.class_id && overlap(k,b)>policy.nms_iou;});
        if(suppressed)++result.suppressed;else kept.push_back(b);
    }
    result.overflow=kept.size()>policy.max_detections;
    if(result.overflow)kept.resize(policy.max_detections);
    result.boxes=std::move(kept);return result;
}
FilterResult detect_objects(const int8_t* out0,const int8_t* out1,const Postprocess& policy){return filter_boxes(decode_candidates(out0,out1),policy);}
void Tracker::reset(){tracks.clear();next_id=1;last_ns=0;}
void Tracker::update(std::vector<Box>& boxes,uint64_t now,const Postprocess& policy) {
    if(!now || (last_ns && now<=last_ns))return;
    tracks.erase(std::remove_if(tracks.begin(),tracks.end(),[&](const Track& t){return now-t.last_ns>uint64_t(policy.track_max_gap_ms)*1000000ULL;}),tracks.end());
    struct Pair {double score;size_t track,box;};std::vector<Pair> pairs;
    for(size_t t=0;t<tracks.size();++t)for(size_t b=0;b<boxes.size();++b)
        if(tracks[t].box.class_id==boxes[b].class_id){const double score=overlap(tracks[t].box,boxes[b]);if(score>=policy.track_iou)pairs.push_back({score,t,b});}
    std::sort(pairs.begin(),pairs.end(),[](const Pair& a,const Pair& b){return a.score!=b.score?a.score>b.score:a.track!=b.track?a.track<b.track:a.box<b.box;});
    std::vector<bool> matched_track(tracks.size()),matched_box(boxes.size());
    for(const auto& p:pairs)if(!matched_track[p.track] && !matched_box[p.box]){
        auto& t=tracks[p.track];auto& b=boxes[p.box];t.box=b;t.last_ns=now;++t.hits;t.misses=0;b.track_id=t.id;b.track_confirmed=t.hits>=policy.track_min_hits;matched_track[p.track]=matched_box[p.box]=true;
    }
    for(size_t i=0;i<tracks.size();++i)if(!matched_track[i]){++tracks[i].misses;}
    tracks.erase(std::remove_if(tracks.begin(),tracks.end(),[&](const Track& t){return t.misses>policy.track_max_misses;}),tracks.end());
    for(size_t i=0;i<boxes.size();++i)if(!matched_box[i]){
        if(next_id==0xffffffffu)throw std::runtime_error("Tracking identifiers exhausted");
        auto& b=boxes[i];b.track_id=next_id++;b.track_confirmed=policy.track_min_hits<=1;tracks.push_back({b,b.track_id,1,0,now});
    }
    if(tracks.size()>2*policy.max_detections){
        std::stable_sort(tracks.begin(),tracks.end(),[](const Track& a,const Track& b){return a.misses!=b.misses?a.misses<b.misses:a.last_ns!=b.last_ns?a.last_ns>b.last_ns:a.id<b.id;});
        tracks.resize(2*policy.max_detections);
    }
    // Lost tracks retain identity briefly, but never create predicted boxes or extra counts.
    last_ns=now;
}
// Conservative on-device quality gate. Server recalculates quality from stored evidence.
bool quality(const uint16_t* pixels) {
    unsigned mean=0,n=0;int lap=0;uint64_t squares=0;
    auto luma=[&](unsigned x,unsigned y){const unsigned p=pixels[y*416+x],r=p>>11,g=(p>>5)&63,b=p&31;return int((19595*((r<<3)|(r>>2))+38470*((g<<2)|(g>>4))+7471*((b<<3)|(b>>2))+32768)>>16);};
    for(unsigned y=4;y<412;y+=4)for(unsigned x=4;x<412;x+=4) {
        const int v=luma(x,y),d=4*v-luma(x-4,y)-luma(x+4,y)-luma(x,y-4)-luma(x,y+4);
        mean+=v;lap+=d;squares+=unsigned(d*d);++n;
    }
    // Integer sums are exact here: |d| <= 1020, n = 10404; only squares needs 64 bits.
    const double average=double(mean)/n,lap_average=double(lap)/n;
    return average>=30 && average<=230 && double(squares)/n-lap_average*lap_average>=20;
}
}
