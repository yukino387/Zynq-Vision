#include "level_compat.h"
#include <algorithm>
#include <cmath>
#include <limits>

namespace terminal {
namespace {
using Image=std::vector<uint8_t>;
int rounded(double value){return int(std::lrint(value));}
void morph_axis(const Image& src,Image& dst,int width,int height,int radius,bool maximum,bool vertical) {
    const int length=vertical?height:width,lines=vertical?width:height;
    for(int line=0;line<lines;++line){
        auto at=[&](int index){return vertical?index*width+line:line*width+index;};
        int sum=0;for(int i=0;i<=std::min(radius,length-1);++i)sum+=src[at(i)]!=0;
        for(int x=0;x<length;++x){
            const int count=std::min(length-1,x+radius)-std::max(0,x-radius)+1;
            dst[at(x)]=(maximum?sum>0:sum==count)?255:0;
            if(x-radius>=0)sum-=src[at(x-radius)]!=0;
            if(x+radius+1<length)sum+=src[at(x+radius+1)]!=0;
        }
    }
}
void morph(Image& image,int width,int height,int radius,bool maximum){
    Image temp(image.size());morph_axis(image,temp,width,height,radius,maximum,false);morph_axis(temp,image,width,height,radius,maximum,true);
}
double contour_area(const Image& mask,int width,int height,int start,size_t pixels){
    static const int dx[]={1,1,0,-1,-1,-1,0,1},dy[]={0,1,1,1,0,-1,-1,-1};
    const int sx=start%width,sy=start/width;int x=sx,y=sy,back=4,first_x=-1,first_y=-1;double twice=0;
    for(size_t step=0;step<=pixels*8;++step){
        int direction=-1;
        for(int k=1;k<=8;++k){const int d=(back+k)%8,nx=x+dx[d],ny=y+dy[d];if(nx>=0 && ny>=0 && nx<width && ny<height && mask[ny*width+nx]){direction=d;break;}}
        if(direction<0)return 0;
        const int nx=x+dx[direction],ny=y+dy[direction];
        if(first_x<0){first_x=nx;first_y=ny;}
        else if(x==sx && y==sy && nx==first_x && ny==first_y)break;
        twice+=double(x)*ny-double(nx)*y;
        const int px=x+dx[(direction+7)%8]-nx,py=y+dy[(direction+7)%8]-ny;
        for(int d=0;d<8;++d)if(dx[d]==px && dy[d]==py){back=d;break;}
        x=nx;y=ny;
    }
    return std::abs(twice)*.5;
}
double median(std::vector<double>& values){
    const size_t n=values.size(),middle=n/2;std::nth_element(values.begin(),values.begin()+middle,values.end());
    const double upper=values[middle];return n%2?upper:(upper+*std::max_element(values.begin(),values.begin()+middle))*.5;
}
double percentile(const std::array<unsigned,256>& histogram,unsigned total,double fraction){
    const double index=(total-1)*fraction;const unsigned lower=unsigned(index),upper=unsigned(std::ceil(index));
    unsigned count=0;int lo=-1,hi=255;
    for(int i=0;i<256;++i){count+=histogram[i];if(lo<0 && count>lower)lo=i;if(count>upper){hi=i;break;}}
    return lo+(hi-lo)*(index-lower);
}
}

LevelFrame prepare_level_bgr(const uint8_t* bgr,unsigned width,unsigned height){
    LevelFrame result;result.active=true;result.gray.assign(224*224,0);
    if(width<32 || height<32)return result;
    Image mask(width*height);std::array<int,256> saturation{},hue{};
    for(int i=1;i<256;++i){saturation[i]=rounded(double(255<<12)/i);hue[i]=rounded(double(180<<12)/(6*i));}
    for(unsigned i=0;i<width*height;++i){
        const int b=bgr[3*i],g=bgr[3*i+1],r=bgr[3*i+2],v=std::max({r,g,b}),minimum=std::min({r,g,b}),delta=v-minimum;
        const int s=(delta*saturation[v]+2048)>>12;
        int h=(v==r?g-b:v==g?b-r+2*delta:r-g+4*delta);h=(h*hue[delta]+2048)>>12;if(h<0)h+=180;
        mask[i]=((h<=8 || h>=170) && s>=110 && v>=60)?255:0;
    }
    morph(mask,width,height,7,true);morph(mask,width,height,7,false);morph(mask,width,height,4,false);morph(mask,width,height,4,true);
    Image visited(mask.size());std::vector<int> component;double best=0;
    for(unsigned start=0;start<mask.size();++start)if(mask[start] && !visited[start]){
        component.clear();component.push_back(start);visited[start]=1;int xmin=start%width,xmax=xmin,ymin=start/width,ymax=ymin;
        for(size_t j=0;j<component.size();++j){const int x=component[j]%width,y=component[j]/width;xmin=std::min(xmin,x);xmax=std::max(xmax,x);ymin=std::min(ymin,y);ymax=std::max(ymax,y);
            for(int yy=std::max(0,y-1);yy<=std::min(int(height)-1,y+1);++yy)for(int xx=std::max(0,x-1);xx<=std::min(int(width)-1,x+1);++xx){const int next=yy*width+xx;if(mask[next] && !visited[next]){visited[next]=1;component.push_back(next);}}
        }
        const int w=xmax-xmin+1,h=ymax-ymin+1;
        if(component.size()<.0015*width*height || std::abs(xmin+w*.5-width*.5)>.3*width || h>1.6*w)continue;
        const double area=contour_area(mask,width,height,start,component.size());
        if(area>=.0015*width*height && area>best){best=area;result.bbox={xmin,ymin,w,h};}
    }
    if(!best)return result;
    const auto& box=result.bbox;const double lab=std::min(box[2],box[3]),cx=box[0]+box[2]*.5;if(lab<12)return result;
    const int x0=std::max(0,rounded(cx-1.15*lab)),x1=std::min(int(width),rounded(cx+1.15*lab));
    const int y0=std::max(0,rounded(box[1]-1.9*lab)),y1=std::min(int(height),rounded(box[1]+1.4*lab));
    if(x1-x0<32 || y1-y0<32)return result;
    result.label_found=true;result.crop={x0,y0,x1,y1};const double scale=224.0/(y1-y0);
    result.label_top=(box[1]-y0)*scale;result.label_height=lab*scale;result.resized_width=std::max(8,rounded((x1-x0)*scale));
    const int resized=result.resized_width,offset=resized<224?-(224-resized)/2:(resized-224)/2;
    std::array<int,224> xindex{},xweight{};
    for(int x=0;x<224;++x){const int rx=std::clamp(x+offset,0,resized-1);double sx=(rx+.5)*(x1-x0)/resized-.5;int ix=int(std::floor(sx));sx-=ix;if(ix<0){ix=0;sx=0;}if(ix>=x1-x0-1){ix=x1-x0-1;sx=0;}xindex[x]=ix;xweight[x]=rounded(sx*2048);}
    std::array<unsigned,256> histogram{};
    for(int y=0;y<224;++y){
        double sy=(y+.5)*(y1-y0)/224-.5;int iy=int(std::floor(sy));sy-=iy;if(iy<0){iy=0;sy=0;}if(iy>=y1-y0-1){iy=y1-y0-1;sy=0;}
        const int by=rounded(sy*2048),ay=2048-by,iy1=std::min(y1-y0-1,iy+1);
        for(int x=0;x<224;++x){
            const int ix=xindex[x],bx=xweight[x],ax=2048-bx,ix1=std::min(x1-x0-1,ix+1);int color[3];
            for(int c=0;c<3;++c){auto at=[&](int yy,int xx){return bgr[3*((y0+yy)*width+x0+xx)+c];};
                const int top=at(iy,ix)*ax+at(iy,ix1)*bx,bottom=at(iy1,ix)*ax+at(iy1,ix1)*bx;
                color[c]=(top*ay+bottom*by+(1<<21))>>22;
            }
            const int value=(77*color[2]+150*color[1]+29*color[0])>>8;result.gray[y*224+x]=value;++histogram[value];
        }
    }
    const double lo=percentile(histogram,224*224,.05),hi=percentile(histogram,224*224,.95);
    if(hi-lo>=8){std::array<uint8_t,256> lut{};for(int i=0;i<256;++i)lut[i]=uint8_t(std::clamp((float(i)-float(lo))*float(255.0/(hi-lo)),0.0f,255.0f));for(auto& value:result.gray)value=lut[value];}
    measure_level(result);return result;
}
LevelFrame prepare_level_rgb565(const uint16_t* pixels){
    Image bgr(416*416*3);for(unsigned i=0;i<416*416;++i){const unsigned p=pixels[i];bgr[i*3]=(p&31)*255/31;bgr[i*3+1]=((p>>5)&63)*255/63;bgr[i*3+2]=(p>>11)*255/31;}
    return prepare_level_bgr(bgr.data(),416,416);
}
void measure_level(LevelFrame& frame){
    frame.row=-1;frame.strength=0;frame.fallback=false;if(!frame.label_found || frame.gray.size()!=224*224)return;
    // With no visible surface above the label, report no row at all: the
    // missing line is itself the evidence (LEVEL-ROW-v1.3 "invisible = low").
    auto fallback=[&]{frame.row=-1;frame.fallback=true;};
    const int lo=std::max(3,int(frame.label_top-1.2*frame.label_height)),hi=std::min(220,int(frame.label_top-.25*frame.label_height)),n=hi-lo;
    if(n<6){fallback();return;}
    constexpr int c0=78,c1=145;std::vector<double> baseline(c1-c0),values;values.reserve(std::max(n,c1-c0));
    for(int x=c0;x<c1;++x){values.clear();for(int y=lo;y<hi;++y)values.push_back(frame.gray[y*224+x]);baseline[x-c0]=median(values);}
    std::vector<double> profile(n);for(int y=lo;y<hi;++y){values.clear();for(int x=c0;x<c1;++x)values.push_back(frame.gray[y*224+x]-baseline[x-c0]);profile[y-lo]=median(values);}
    const int sup=std::max(1,rounded(.03*frame.label_height));int best_i=sup;double best=-1;
    auto score=[&](int i){double a=0,b=0;for(int k=0;k<sup;++k){a+=profile[i+k];b+=profile[i-sup+k];}return std::abs((a-b)/sup);};
    for(int i=sup;i<n-sup;++i){const auto value=score(i);if(value>best){best=value;best_i=i;}}
    frame.strength=best;if(best<4){fallback();return;}
    // A liquid line is a broad dark-below step across the measured columns.
    // Cap/neck edges are narrow and shallow; reject them instead of reporting
    // the cap as the level (empty bottles used to pass this way).
    const int y=lo+best_i;std::vector<int> steps(c1-c0);
    for(int x=c0;x<c1;++x){
        int above=0,below=0;
        for(int k=0;k<sup;++k){above+=frame.gray[(y-sup+k)*224+x];below+=frame.gray[(y+k)*224+x];}
        steps[x-c0]=below-above;
    }
    std::vector<int> ordered=steps;
    std::nth_element(ordered.begin(),ordered.begin()+ordered.size()/2,ordered.end());
    const int median_dark=ordered[ordered.size()/2];
    const int dark=std::count_if(steps.begin(),steps.end(),[&](int value){return value<=-4*sup;});
    if(median_dark>-9*sup || dark*10<7*int(steps.size())){fallback();return;}
    const double a=best_i>=2*sup?score(best_i-sup):best,c=best_i+2*sup<=n?score(best_i+sup):best,d=a-2*best+c;
    frame.row=lo+best_i+(std::abs(d)>1e-9?.5*(a-c)/d:0);
}
FilterResult level_detections(FilterResult filtered,const LevelFrame& frame){
    if(!frame.active)return filtered;
    // Display keeps the network's liquid-line box; decisions/passage use the
    // red label as presence so a missed network box cannot hide the bottle.
    std::vector<Box> display;
    if(frame.label_found)for(const auto& box:filtered.boxes)if(box.class_id==0 && (display.empty() || box.confidence>display[0].confidence))display={box};
    const auto& r=frame.crop;const int width=frame.resized_width,offset=width<224?-(224-width)/2:(width-224)/2;
    for(auto& box:display){auto x=[&](double v){return std::clamp(r[0]+(v*224/416+offset)*(r[2]-r[0])/width,0.0,416.0);};auto y=[&](double v){return std::clamp(r[1]+v*(r[3]-r[1])/416,0.0,416.0);};box.x1=x(box.x1);box.x2=x(box.x2);box.y1=y(box.y1);box.y2=y(box.y2);}
    filtered.display=std::move(display);
    std::vector<Box> presence;
    if(frame.label_found)presence.push_back({0,1.0,double(frame.bbox[0]),double(frame.bbox[1]),double(frame.bbox[0]+frame.bbox[2]),double(frame.bbox[1]+frame.bbox[3])});
    filtered.boxes=std::move(presence);return filtered;
}
const char* level_status(const LevelFrame& frame,bool target){
    if(!frame.label_found)return "未找到红标签";
    if(!target)return "未检出本产品";
    if(frame.row<0)return "液位过低（未测到液面）";
    return frame.row<level_band_low?"液位过高":frame.row>level_band_high?"液位过低":"液位合格";
}
Decision level_decision(const Rules& rules,const FilterResult& filtered,const LevelFrame& frame,bool quality_pass){
    auto result=evaluate(rules,filtered.boxes,true,quality_pass);
    if(filtered.invalid || filtered.overflow){result.result=Result::Review;return result;}
    if(result.result==Result::Error || (rules.quality_gate && !quality_pass))return result;
    if(!frame.label_found || filtered.boxes.empty()){result.result=Result::Review;return result;}
    if(result.result!=Result::Pass)return result;
    // Bottle present but no valid liquid line (cap/neck edge rejected, or the
    // surface hidden by the label): treat it as an underfilled bottle.
    // Rows outside the two-sided band are high (<85) or low (>102.9).
    if(frame.row<0 || frame.row<level_band_low || frame.row>level_band_high){result.result=Result::Fail;for(auto& finding:result.findings)if(finding.check.class_id==0)finding.result=Result::Fail;}
    return result;
}
}
