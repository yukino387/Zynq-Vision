#include "core.h"
#include "nlohmann/json.hpp"
#include <fstream>
#include <iostream>
#include <cmath>
#include <stdexcept>
using nlohmann::json;
void require(bool pass,const std::string& name){if(!pass)throw std::runtime_error(name);}
terminal::Postprocess policy(const json& p){terminal::Postprocess r;r.nms_iou=p["nmsIou"];r.containment=p["containment"];r.min_area=p["minArea"];r.max_detections=p["maxDetections"];return r;}
terminal::Box box(const json& b){return {b["classId"],b["confidence"],b["x1"],b["y1"],b["x2"],b["y2"]};}
void compare(const terminal::FilterResult& actual,const json& expected,const std::string& name){
 const auto& boxes=expected["boxes"];const auto& report=expected["report"];
 require(actual.boxes.size()==boxes.size(),name+": count");
 require(actual.candidates==report["candidates"] && actual.invalid==report["invalid"] && actual.tiny==report["tiny"] && actual.nested==report["nested"] && actual.suppressed==report["suppressed"] && actual.overflow==report["overflow"],name+": report");
 for(size_t i=0;i<boxes.size();++i){const auto& a=actual.boxes[i];const auto b=box(boxes[i]);require(a.class_id==b.class_id && std::abs(a.confidence-b.confidence)<1e-10 && std::abs(a.x1-b.x1)<1e-9 && std::abs(a.y1-b.y1)<1e-9 && std::abs(a.x2-b.x2)<1e-9 && std::abs(a.y2-b.y2)<1e-9,name+": coordinates");}
}
int main(int argc,char** argv){try{
 require(argc==2,"cases path required");json data;std::ifstream(argv[1])>>data;
 for(const auto& c:data["cases"]){std::vector<terminal::Box> boxes;for(const auto& b:c["boxes"])boxes.push_back(box(b));compare(terminal::filter_boxes(boxes,policy(c["policy"])),c["expected"],c["name"]);}
 for(const auto& c:data["tensorCases"]){auto out0=c["out0"].get<std::vector<int8_t>>(),out1=c["out1"].get<std::vector<int8_t>>();compare(terminal::detect_objects(out0.data(),out1.data()),c["expected"],"tensor decode");}
 terminal::Tracker tracker;terminal::Postprocess p;uint64_t now=1000000000ULL;
 auto a=terminal::Box{0,.9,20,20,60,60},b=terminal::Box{0,.9,180,20,220,60};std::vector<terminal::Box> boxes{a,b};
 tracker.update(boxes,now,p);require(boxes[0].track_id==1 && boxes[1].track_id==2 && !boxes[0].track_confirmed,"first frame tentative");
 boxes={b,a};tracker.update(boxes,now+=70000000ULL,p);require(boxes[0].track_id==2 && boxes[1].track_id==1 && boxes[0].track_confirmed,"one-to-one stable order");
 boxes={};tracker.update(boxes,now+=70000000ULL,p);require(boxes.empty(),"no ghost detections");
 boxes={a};tracker.update(boxes,now+=70000000ULL,p);require(boxes[0].track_id==1,"occlusion identity");
 auto other=a;other.class_id=1;boxes={other};tracker.update(boxes,now+=70000000ULL,p);require(boxes[0].track_id==3,"class separation");
 boxes={other};tracker.update(boxes,now+=1100000000ULL,p);require(boxes[0].track_id==4 && !boxes[0].track_confirmed,"age expiration");
 for(int i=0;i<4;i++){boxes={};tracker.update(boxes,now+=70000000ULL,p);}
 boxes={other};tracker.update(boxes,now+=70000000ULL,p);require(boxes[0].track_id==5,"miss expiration");
 tracker.reset();boxes={a};tracker.update(boxes,now,p);require(boxes[0].track_id==1,"plan reset");
 auto shifted=a;shifted.x1+=5;shifted.x2+=5;boxes={a,shifted};tracker.update(boxes,now+=70000000ULL,p);require(boxes[0].track_id==1 && boxes[1].track_id==2,"one detection per track");
 std::cout<<"POSTPROCESS_ARM_PASS "<<data["cases"].size()<<" box cases + "<<data["tensorCases"].size()<<" tensor cases + 9 tracking checks\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
