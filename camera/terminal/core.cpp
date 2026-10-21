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
// Both INT8 heads have only 256 possible inputs. Keep double precision and the
// original formulas: table lookup changes the cost, not quantization or thresholds.
struct DecodeTables {
    std::array<std::array<double,256>,2> probability{},dimension{};
    DecodeTables() {
        const double scales[]={.11581249687615341,.15977688286248154};
        for(unsigned h=0;h<2;++h)for(int v=-128;v<128;++v){
            probability[h][v+128]=sigmoid(v*scales[h]);
            dimension[h][v+128]=std::exp(v*scales[h]);
        }
    }
};
static double overlap(const Box& a,const Box& b) {
    const double intersection=std::max(0.0,std::min(a.x2,b.x2)-std::max(a.x1,b.x1))*std::max(0.0,std::min(a.y2,b.y2)-std::max(a.y1,b.y1));
    const double total=(a.x2-a.x1)*(a.y2-a.y1)+(b.x2-b.x1)*(b.y2-b.y1)-intersection;
    return total>0?intersection/total:0;
}
static std::vector<Box> decode_candidates(const int8_t* out0,const int8_t* out1) {
    static const double anchors[2][6]={{1.3629538461538462,1.3798076923076923,2.2716615384615384,2.843723076923077,5.788461538461538,5.367815384615384},{.7740384615384615,.9086538461538461,1.2451923076923077,1.9519230769230769,2.7259615384615383,2.7596153846153846}};
    static const DecodeTables tables;
    std::vector<Box> candidates;
    candidates.reserve(3*(7*7+14*14));
    for(unsigned head=0;head<2;++head) {
        const auto raw=head?out1:out0; const unsigned size=head?14:7;
        for(unsigned a=0;a<3;++a) for(unsigned cell=0;cell<size*size;++cell) {
            auto value=[&](unsigned channel){return int(raw[(a*11+channel)*size*size+cell]);};
            auto probability=[&](unsigned channel){return tables.probability[head][value(channel)+128];};
            const double obj=probability(4); if(obj<.35)continue;
            unsigned cls=0; for(unsigned c=1;c<6;++c)if(value(5+c)>value(5+cls))cls=c;
            const double score=obj*probability(5+cls);if(score<.35)continue;
            const double x=(probability(0)+cell%size)*416/size,y=(probability(1)+cell/size)*416/size;
            const double w=tables.dimension[head][value(2)+128]*anchors[head][a*2]*416/size,h=tables.dimension[head][value(3)+128]*anchors[head][a*2+1]*416/size;
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
    if(policy.algorithm_version==3) {
        // Only surviving, stronger evidence can suppress a candidate. This avoids
        // a weak small box deleting a reliable product, and avoids deletion chains.
        std::stable_sort(clean.begin(),clean.end(),[](const Box& a,const Box& b){return a.confidence==b.confidence?box_area(a)<box_area(b):a.confidence>b.confidence;});
        for(const auto& b:clean) {
            bool removed=false;
            for(const auto& k:kept) {
                if(k.class_id!=b.class_id)continue;
                const double small=std::min(box_area(k),box_area(b)),large=std::max(box_area(k),box_area(b));
                const double intersection=std::max(0.0,std::min(k.x2,b.x2)-std::max(k.x1,b.x1))*std::max(0.0,std::min(k.y2,b.y2)-std::max(k.y1,b.y1));
                if(large>=1.5*small && intersection/small>=policy.containment){++result.nested;removed=true;break;}
                if(overlap(k,b)>policy.nms_iou){++result.suppressed;removed=true;break;}
            }
            if(!removed)kept.push_back(b);
        }
        result.overflow=kept.size()>policy.max_detections;
        if(result.overflow)kept.resize(policy.max_detections);
        result.boxes=std::move(kept);return result;
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
// Rectangular Hungarian assignment. Dummy columns let observations remain unmatched;
// solve each class and confidence group independently to bound work on the Cortex-A9.
static std::vector<unsigned> assign_tracks(const std::vector<std::vector<double>>& cost) {
    const unsigned n=cost.size(),m=cost.front().size();
    std::vector<double> u(n+1),v(m+1),minimum(m+1);
    std::vector<unsigned> p(m+1),way(m+1),assignment(n,m);
    std::vector<bool> used(m+1);
    for(unsigned i=1;i<=n;++i) {
        p[0]=i;unsigned column=0;
        std::fill(minimum.begin(),minimum.end(),1e9);std::fill(used.begin(),used.end(),false);
        do {
            used[column]=true;const unsigned row=p[column];unsigned next=0;double delta=1e9;
            for(unsigned j=1;j<=m;++j)if(!used[j]) {
                const double current=cost[row-1][j-1]-u[row]-v[j];
                if(current<minimum[j]){minimum[j]=current;way[j]=column;}
                if(minimum[j]<delta){delta=minimum[j];next=j;}
            }
            for(unsigned j=0;j<=m;++j)if(used[j]){u[p[j]]+=delta;v[j]-=delta;}else minimum[j]-=delta;
            column=next;
        }while(p[column]);
        do {const unsigned previous=way[column];p[column]=p[previous];column=previous;}while(column);
    }
    for(unsigned j=1;j<=m;++j)if(p[j])assignment[p[j]-1]=j-1;
    return assignment;
}
static std::array<double,19> appearance(const Box& box,const uint16_t* pixels) {
    std::array<double,19> feature{};
    for(unsigned y=0;y<4;++y)for(unsigned x=0;x<4;++x) {
        const int cx=std::clamp(int(box.x1+(x+.5)*(box.x2-box.x1)/4),0,415);
        const int cy=std::clamp(int(box.y1+(y+.5)*(box.y2-box.y1)/4),0,415);
        double red=0,green=0,blue=0;
        for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx) {
            const auto p=pixels[std::clamp(cy+dy,0,415)*416+std::clamp(cx+dx,0,415)];
            red+=(p>>11)/31.0;green+=((p>>5)&63)/63.0;blue+=(p&31)/31.0;
        }
        red/=9;green/=9;blue/=9;
        feature[y*4+x]=.299*red+.587*green+.114*blue;
        feature[16]+=red/16;feature[17]+=green/16;feature[18]+=blue/16;
    }
    const double mean=.299*feature[16]+.587*feature[17]+.114*feature[18];
    for(unsigned i=0;i<16;++i)feature[i]-=mean;
    return feature;
}
static double appearance_distance(const std::array<double,19>& a,const std::array<double,19>& b) {
    double texture=0,color=0;
    for(unsigned i=0;i<16;++i)texture+=std::abs(a[i]-b[i])/16;
    for(unsigned i=16;i<19;++i)color+=std::abs(a[i]-b[i])/3;
    return .5*(texture+color);
}
void Tracker::update(std::vector<Box>& boxes,uint64_t now,const Postprocess& policy,const uint16_t* pixels,double confidence) {
    for(auto& b:boxes){b.track_id=0;b.track_confirmed=false;}
    if(!now || (last_ns && now<=last_ns))return;
    tracks.erase(std::remove_if(tracks.begin(),tracks.end(),[&](const Track& t){return now-t.last_ns>uint64_t(policy.track_max_gap_ms)*1000000ULL;}),tracks.end());
    std::vector<std::array<double,19>> features(boxes.size());
    if(pixels)for(size_t i=0;i<boxes.size();++i)features[i]=appearance(boxes[i],pixels);
    std::vector<bool> matched_track(tracks.size()),matched_box(boxes.size());
    // Strong detections claim identities first. Weak detections can maintain an
    // existing identity, but never create or confirm a new one.
    for(unsigned pass=0;pass<2;++pass)for(unsigned cls=0;cls<6;++cls) {
        std::vector<size_t> observations,identities;
        for(size_t i=0;i<boxes.size();++i)if(boxes[i].class_id==cls && (boxes[i].confidence>=confidence)==(pass==0))observations.push_back(i);
        for(size_t i=0;i<tracks.size();++i)if(tracks[i].box.class_id==cls && !matched_track[i])identities.push_back(i);
        if(observations.empty() || identities.empty())continue;
        std::vector<std::vector<double>> cost(observations.size(),std::vector<double>(identities.size()+observations.size(),1));
        for(size_t row=0;row<observations.size();++row)for(size_t col=0;col<identities.size();++col) {
            const auto& t=tracks[identities[col]];const auto& b=boxes[observations[row]];
            auto predicted=t.box;const double dt=std::min(.5,double(now-t.last_ns)/1e9);
            predicted.x1+=t.vx*dt;predicted.x2+=t.vx*dt;predicted.y1+=t.vy*dt;predicted.y2+=t.vy*dt;
            const double wr=(b.x2-b.x1)/(t.box.x2-t.box.x1),hr=(b.y2-b.y1)/(t.box.y2-t.box.y1);
            const double dx=((b.x1+b.x2)-(predicted.x1+predicted.x2))/((b.x2-b.x1)+(predicted.x2-predicted.x1));
            const double dy=((b.y1+b.y2)-(predicted.y1+predicted.y2))/((b.y2-b.y1)+(predicted.y2-predicted.y1));
            const double distance=std::sqrt(dx*dx+dy*dy),iou=overlap(predicted,b);
            const double visual=pixels && t.has_appearance?appearance_distance(t.appearance,features[observations[row]]):.15;
            const bool near=iou>=policy.track_iou || distance<=.9 || (pixels && t.has_appearance && visual<.15 && distance<=1.75);
            if(wr<.5 || wr>2 || hr<.5 || hr>2 || !near || (visual>.35 && iou<.5)){cost[row][col]=2;continue;}
            cost[row][col]=1-(.55*iou+.35/(1+distance)+.1*std::max(0.0,1-visual*3));
        }
        const auto assignment=assign_tracks(cost);
        for(size_t row=0;row<observations.size();++row) {
            const auto col=assignment[row];if(col>=identities.size() || cost[row][col]>=1)continue;
            const auto ti=identities[col],bi=observations[row];auto& t=tracks[ti];auto& b=boxes[bi];
            const double dt=double(now-t.last_ns)/1e9;
            const double vx=((b.x1+b.x2)-(t.box.x1+t.box.x2))/(2*dt),vy=((b.y1+b.y2)-(t.box.y1+t.box.y2))/(2*dt);
            t.vx=t.moving?.65*vx+.35*t.vx:vx;t.vy=t.moving?.65*vy+.35*t.vy:vy;t.moving=true;
            if(pass==0)t.hits=std::min(policy.track_min_hits,t.hits+1);else if(t.hits<policy.track_min_hits)t.hits=0;
            t.box=b;t.last_ns=now;t.misses=0;
            if(pixels && pass==0){t.appearance=features[bi];t.has_appearance=true;}
            b.track_id=t.id;b.track_confirmed=t.hits>=policy.track_min_hits;matched_track[ti]=matched_box[bi]=true;
        }
    }
    for(size_t i=0;i<tracks.size();++i)if(!matched_track[i]){
        ++tracks[i].misses;
        // Tentative tracks need consecutive observations; isolated flicker must
        // not accumulate into confirmation. Confirmed IDs still survive occlusion.
        if(tracks[i].hits<policy.track_min_hits)tracks[i].hits=0;
    }
    tracks.erase(std::remove_if(tracks.begin(),tracks.end(),[&](const Track& t){return t.misses>policy.track_max_misses;}),tracks.end());
    for(size_t i=0;i<boxes.size();++i)if(!matched_box[i] && boxes[i].confidence>=confidence){
        if(next_id==0xffffffffu)throw std::runtime_error("Tracking identifiers exhausted");
        auto& b=boxes[i];b.track_id=next_id++;b.track_confirmed=policy.track_min_hits<=1;tracks.push_back({b,b.track_id,1,0,now});
        if(pixels){tracks.back().appearance=features[i];tracks.back().has_appearance=true;}
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
