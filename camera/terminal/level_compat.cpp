#include "level_compat.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <arm_neon.h>

namespace terminal {
namespace {
using Image=std::vector<uint8_t>;
int rounded(double value){return int(std::lrint(value));}
void morph_axis(const Image& src,Image& dst,int width,int height,int radius,bool maximum,bool vertical) {
    if(vertical){
        // Update all columns together so each source row is read contiguously.
        std::vector<uint8_t> sums(width,0),zeros(width,0);
        for(int y=0;y<=std::min(radius,height-1);++y)
            for(int x=0;x<width;++x)sums[x]+=src[y*width+x]!=0;
        for(int y=0;y<height;++y){
            const auto count=vdupq_n_u8(std::min(height-1,y+radius)-std::max(0,y-radius)+1);
            const auto remove=y>=radius?src.data()+(y-radius)*width:zeros.data();
            const auto add=y+radius+1<height?src.data()+(y+radius+1)*width:zeros.data();
            int x=0;
            for(;x+16<=width;x+=16){
                auto sum=vld1q_u8(sums.data()+x);
                vst1q_u8(dst.data()+y*width+x,maximum?vcgtq_u8(sum,vdupq_n_u8(0)):vceqq_u8(sum,count));
                sum=vsubq_u8(sum,vshrq_n_u8(vld1q_u8(remove+x),7));
                sum=vaddq_u8(sum,vshrq_n_u8(vld1q_u8(add+x),7));
                vst1q_u8(sums.data()+x,sum);
            }
            const int required=std::min(height-1,y+radius)-std::max(0,y-radius)+1;
            for(;x<width;++x){dst[y*width+x]=(maximum?sums[x]>0:sums[x]==required)?255:0;sums[x]-=remove[x]!=0;sums[x]+=add[x]!=0;}
        }
        return;
    }
    Image padded(width+2*radius,maximum?0:255);
    for(int y=0;y<height;++y){
        std::copy_n(src.data()+y*width,width,padded.data()+radius);
        int x=0;
        if(radius==4 || radius==7)for(;x+16<=width && x+32<=int(padded.size());x+=16){
            auto a=vld1q_u8(padded.data()+x),b=vld1q_u8(padded.data()+x+16);
            auto combine=[&](uint8x16_t u,uint8x16_t v){return maximum?vorrq_u8(u,v):vandq_u8(u,v);};
            a=combine(a,vextq_u8(a,b,1));b=combine(b,vextq_u8(b,b,1));
            a=combine(a,vextq_u8(a,b,2));b=combine(b,vextq_u8(b,b,2));
            a=combine(a,vextq_u8(a,b,4));b=combine(b,vextq_u8(b,b,4));
            const auto shifted=radius==4?vextq_u8(a,b,1):vextq_u8(a,b,7);
            vst1q_u8(dst.data()+y*width+x,combine(a,shifted));
        }
        for(;x+16<=width;x+=16){
            auto value=vld1q_u8(padded.data()+x);
            if(maximum)for(int k=1;k<=2*radius;++k)value=vorrq_u8(value,vld1q_u8(padded.data()+x+k));
            else for(int k=1;k<=2*radius;++k)value=vandq_u8(value,vld1q_u8(padded.data()+x+k));
            vst1q_u8(dst.data()+y*width+x,value);
        }
        for(;x<width;++x){
            uint8_t value=padded[x];
            for(int k=1;k<=2*radius;++k)value=maximum?(value|padded[x+k]):(value&padded[x+k]);
            dst[y*width+x]=value;
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

namespace {
struct RedTables {
    std::array<int,256> saturation{},hue{};
    RedTables(){for(int i=1;i<256;++i){saturation[i]=rounded(double(255<<12)/i);hue[i]=rounded(double(180<<12)/(6*i));}}
};
bool red_pixel(int b,int g,int r){
    static const RedTables tables;
    const int v=std::max({r,g,b}),delta=v-std::min({r,g,b});
    const int s=(delta*tables.saturation[v]+2048)>>12;
    int h=(v==r?g-b:v==g?b-r+2*delta:r-g+4*delta);h=(h*tables.hue[delta]+2048)>>12;if(h<0)h+=180;
    return (h<=8 || h>=170) && s>=110 && v>=40;
}
struct PixelTables {
    std::array<std::array<uint8_t,4>,65536> values{};
    PixelTables(){for(unsigned p=0;p<values.size();++p){auto& c=values[p];c[0]=(p&31)*255/31;c[1]=((p>>5)&63)*255/63;c[2]=(p>>11)*255/31;c[3]=red_pixel(c[0],c[1],c[2])?255:0;}}
};
LevelFrame prepare_level(const uint8_t* bgr,const uint16_t* pixels,unsigned width,unsigned height){
    LevelFrame result;result.active=true;result.gray.assign(224*224,0);
    if(width<32 || height<32)return result;
    const PixelTables* lookup=nullptr;
    if(pixels){static const PixelTables tables;lookup=&tables;}
    Image mask(width*height);
    int left=width,top=height,right=-1,bottom=-1;
    for(unsigned y=0;y<height;++y)for(unsigned x=0;x<width;++x){
        const unsigned i=y*width+x;
        const bool red=pixels?lookup->values[pixels[i]][3]!=0:red_pixel(bgr[3*i],bgr[3*i+1],bgr[3*i+2]);
        if(red){mask[i]=255;left=std::min(left,int(x));right=std::max(right,int(x));top=std::min(top,int(y));bottom=std::max(bottom,int(y));}
    }
    if(right<0)return result;
    // Closing radius 7 then opening radius 4 has a 22-pixel dependency halo.
    // Keep 24 pixels and original image borders so ROI processing is identical.
    left=std::max(0,left-24);right=std::min(int(width)-1,right+24);
    top=std::max(0,top-24);bottom=std::min(int(height)-1,bottom+24);
    const int roi_width=right-left+1,roi_height=bottom-top+1;
    Image roi(roi_width*roi_height);
    for(int y=0;y<roi_height;++y)std::copy_n(mask.data()+(top+y)*width+left,roi_width,roi.data()+y*roi_width);
    morph(roi,roi_width,roi_height,7,true);morph(roi,roi_width,roi_height,7,false);morph(roi,roi_width,roi_height,4,false);morph(roi,roi_width,roi_height,4,true);
    std::fill(mask.begin(),mask.end(),0);
    for(int y=0;y<roi_height;++y)std::copy_n(roi.data()+y*roi_width,roi_width,mask.data()+(top+y)*width+left);
    Image visited(mask.size());std::vector<int> component;double best=0;
    for(unsigned start=0;start<mask.size();++start)if(mask[start] && !visited[start]){
        component.clear();component.push_back(start);visited[start]=1;int xmin=start%width,xmax=xmin,ymin=start/width,ymax=ymin;
        for(size_t j=0;j<component.size();++j){const int x=component[j]%width,y=component[j]/width;xmin=std::min(xmin,x);xmax=std::max(xmax,x);ymin=std::min(ymin,y);ymax=std::max(ymax,y);
            for(int yy=std::max(0,y-1);yy<=std::min(int(height)-1,y+1);++yy)for(int xx=std::max(0,x-1);xx<=std::min(int(width)-1,x+1);++xx){const int next=yy*width+xx;if(mask[next] && !visited[next]){visited[next]=1;component.push_back(next);}}
        }
        const int w=xmax-xmin+1,h=ymax-ymin+1;
        if(component.size()<.0015*width*height || std::abs(xmin+w*.5-width*.5)>.3*width || h>1.6*w || h*20<9*w)continue;
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
            for(int c=0;c<3;++c){auto at=[&](int yy,int xx){const unsigned i=(y0+yy)*width+x0+xx;return pixels?lookup->values[pixels[i]][c]:bgr[3*i+c];};
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
} // namespace
LevelFrame prepare_level_bgr(const uint8_t* bgr,unsigned width,unsigned height){return prepare_level(bgr,nullptr,width,height);}
LevelFrame prepare_level_rgb565(const uint16_t* pixels){return prepare_level(nullptr,pixels,416,416);}
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
