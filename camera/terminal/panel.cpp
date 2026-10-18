#include "lvgl.h"
#include "nlohmann/json.hpp"
#include "httplib.h"
#include "framebuffer.h"
#include <algorithm>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <fcntl.h>
#include <unistd.h>
using json=nlohmann::json;
namespace {
httplib::Client engine("http://127.0.0.1:8877");
lv_obj_t *job_label,*statistics,*result_label,*error_label,*fresh_label,*job_select,*picture,*pause_button;
lv_group_t* focus_group;
lv_image_dsc_t image{};
std::vector<uint8_t> pixels(416*416*2);
std::vector<lv_obj_t*> rectangles;
std::vector<std::string> job_ids;
std::string pending,options_cache;
bool paused=false,picture_valid=false,jobs_loaded=false;
const char* pending_file="/var/lib/vision/panel-request";
void store_pending(const std::string& value) {
    const std::string temporary=std::string(pending_file)+".tmp";
    const int fd=open(temporary.c_str(),O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0600);
    if(fd<0)throw std::runtime_error("无法保存检查编号");
    const bool written=write(fd,value.data(),value.size())==ssize_t(value.size());const int synced=fsync(fd);close(fd);
    if(!written || synced || rename(temporary.c_str(),pending_file))throw std::runtime_error("检查编号保存失败");
    const int directory=open("/var/lib/vision",O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    if(directory<0)throw std::runtime_error("无法确认检查编号");const int result=fsync(directory);close(directory);
    if(result)throw std::runtime_error("检查编号确认失败");
}
uint32_t tick(){return uint32_t(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
std::string translated(const std::string& result){return result=="PASS"?"符合要求":result=="FAIL"?"不符合要求":result=="REVIEW"?"待人工复核":"执行错误";}
void text(lv_obj_t* label,const std::string& value){lv_label_set_text(label,value.c_str());}
void clear_picture() {
    if(!picture_valid)return;
    std::fill(pixels.begin(),pixels.end(),0);
    lv_image_set_src(picture,&image);lv_obj_invalidate(picture);
    for(auto object:rectangles)lv_obj_delete(object);
    rectangles.clear();picture_valid=false;
}
json get(const std::string& path) {
    const auto response=engine.Get(path);if(!response || response->status!=200)throw std::runtime_error("检测服务尚未就绪");return json::parse(response->body);
}
json post(const std::string& path,const json& payload) {
    const auto response=engine.Post(path,payload.dump(),"application/json");if(!response)throw std::runtime_error("检测服务暂时不可达，请核对上一次操作");
    const auto body=json::parse(response->body);
    if(response->status!=200){if(path=="/check" && body.contains("mayHaveSaved") && !body.at("mayHaveSaved").get<bool>()){store_pending("");pending.clear();}throw std::runtime_error(body.value("error","检测服务拒绝了本次操作"));}return body;
}
lv_obj_t* label(lv_obj_t* parent,const char* value) {auto object=lv_label_create(parent);lv_label_set_text(object,value);lv_label_set_long_mode(object,LV_LABEL_LONG_WRAP);return object;}
lv_obj_t* button(lv_obj_t* parent,const char* value,lv_event_cb_t action) {
    auto object=lv_button_create(parent);lv_obj_set_height(object,48);label(object,value);lv_obj_add_event_cb(object,action,LV_EVENT_CLICKED,nullptr);lv_group_add_obj(focus_group,object);return object;
}
void check(lv_event_t*) {
    try {
        if(pending.empty()){std::ifstream file("/proc/sys/kernel/random/uuid");std::getline(file,pending);if(pending.size()!=36)throw std::runtime_error("无法建立检查编号");}
        store_pending(pending);
        const auto saved=post("/check",{{"requestId",pending}});store_pending("");pending.clear();text(result_label,"第 "+std::to_string(saved.at("sequence").get<unsigned>())+" 件 · "+translated(saved.at("result")));text(error_label,"");
    }catch(const std::exception& e){text(error_label,e.what());}
}
void select_job(lv_event_t*) {
    try {
        if(!pending.empty())throw std::runtime_error("请先再次点击检查，核对上一次操作");
        const auto selected=lv_dropdown_get_selected(job_select);if(selected>=job_ids.size())throw std::runtime_error("没有可执行的作业包");
        post("/select",{{"id",job_ids[selected]}});paused=false;text(error_label,"");
    }catch(const std::exception& e){text(error_label,e.what());}
}
void pause(lv_event_t*) {
    try {post("/pause",{{"paused",!paused}});paused=!paused;text(lv_obj_get_child(pause_button,0),paused?"继续检测":"暂停检测");}
    catch(const std::exception& e){text(error_label,e.what());}
}
void discover(lv_indev_t* input,lv_evdev_type_t type,void*) {
    if(type==LV_EVDEV_TYPE_KEY)lv_indev_set_group(input,focus_group);
    else if(type==LV_EVDEV_TYPE_REL){auto cursor=label(lv_screen_active(),"●");lv_indev_set_cursor(input,cursor);}
}
void jobs(lv_timer_t*) {
    try {
        const auto list=get("/jobs");std::string options;std::vector<std::string> ids;
        for(const auto& job:list){if(!options.empty())options+='\n';options+=job.at("name").get<std::string>();ids.push_back(job.at("id"));}
        if(!jobs_loaded || options!=options_cache || ids!=job_ids){jobs_loaded=true;options_cache=options;job_ids=std::move(ids);lv_dropdown_set_options(job_select,options.empty()?"尚未导入作业包":options.c_str());}
    }catch(const std::exception&){ }
}
void refresh(lv_timer_t*) {
    try {
        const auto state=get("/state");
        paused=state.at("paused");text(lv_obj_get_child(pause_button,0),paused?"继续检测":"暂停检测");
        text(job_label,state.at("job").is_null()?"请选择已经下发的作业":state["job"].at("name").get<std::string>()+" · "+state["job"].at("instructions").get<std::string>());
        text(statistics,"本批次已检查 "+std::to_string(state.at("total").get<unsigned>())+" 件    本地符合 "+std::to_string(state["counts"]["PASS"].get<unsigned>())+"    本地不符合 "+std::to_string(state["counts"]["FAIL"].get<unsigned>())+"    待复核 "+std::to_string(state["counts"]["REVIEW"].get<unsigned>())+"    待同步 "+std::to_string(state["pendingSync"].get<unsigned>()));
        if(!state.at("last").is_null()) {
            const auto& last=state.at("last");std::string report="最近检查：第 "+std::to_string(last.at("sequence").get<unsigned>())+" 件 · "+translated(last.at("result"));
            if(last.contains("findings"))for(const auto& finding:last["findings"])report+='\n'+finding.at("label").get<std::string>()+"：确认 "+std::to_string(finding.at("count").get<unsigned>())+"，待确认 "+std::to_string(finding.at("uncertain").get<unsigned>())+"，要求 "+std::to_string(finding.at("min").get<unsigned>())+"–"+std::to_string(finding.at("max").get<unsigned>());
            text(result_label,report);
        }else text(result_label,"当前作业尚无检查记录");
        text(error_label,state.at("error").get<std::string>()+(!state.at("syncError").get<std::string>().empty()?"\n同步暂不可用，检查记录保存在本地":""));
        const auto response=engine.Get("/frame");
        if(!response || response->status!=200 || response->body.size()<4){clear_picture();text(fresh_label,"暂无有效画面");return;}
        uint32_t size=0;std::memcpy(&size,response->body.data(),4);
        if(size>100000 || response->body.size()!=4+size+pixels.size())throw std::runtime_error("画面数据长度异常");
        const auto frame=json::parse(response->body.substr(4,size));std::memcpy(pixels.data(),response->body.data()+4+size,pixels.size());
        lv_image_set_src(picture,&image);lv_obj_invalidate(picture);picture_valid=true;
        text(fresh_label,(frame.at("fresh").get<bool>()?"实时画面":"画面已超时")+std::string(" · #")+std::to_string(frame.at("frameId").get<unsigned>()));
        for(auto object:rectangles)lv_obj_delete(object);rectangles.clear();
        if(frame.at("fresh").get<bool>())for(const auto& box:frame.at("boxes")) {
            auto rectangle=lv_obj_create(picture);lv_obj_remove_style_all(rectangle);
            lv_obj_set_pos(rectangle,int(box["x1"].get<double>()),int(box["y1"].get<double>()));lv_obj_set_size(rectangle,int(box["x2"].get<double>()-box["x1"].get<double>()),int(box["y2"].get<double>()-box["y1"].get<double>()));lv_obj_set_style_border_width(rectangle,2,0);lv_obj_set_style_border_color(rectangle,lv_color_hex(0xd8e5dc),0);rectangles.push_back(rectangle);
        }
    }catch(const std::exception& e){text(fresh_label,"画面不可用");text(error_label,e.what());}
}
}
int main(int argc,char** argv) {
    if(argc!=2){std::cerr<<"Usage: vision-panel CHINESE_FONT_FILE\n";return 2;}
    {std::ifstream file(pending_file);std::getline(file,pending);if(!pending.empty() && (pending.size()!=36 || pending.find_first_not_of("0123456789abcdef-")!=std::string::npos)){std::cerr<<"Invalid saved panel operation\n";return 1;}}
    lv_init();lv_tick_set_cb(tick);focus_group=lv_group_create();lv_group_set_default(focus_group);
    lv_log_register_print_cb([](lv_log_level_t,const char* message){std::cerr<<message;});
    Framebuffer framebuffer;
    auto font=lv_freetype_font_create(argv[1],LV_FREETYPE_FONT_RENDER_MODE_BITMAP,20,LV_FREETYPE_FONT_STYLE_NORMAL);
    if(!font){std::cerr<<"Cannot load terminal font\n";return 1;}
    font->fallback=&lv_font_montserrat_14;
    auto root=lv_screen_active();lv_obj_set_style_text_font(root,font,0);lv_obj_set_style_bg_color(root,lv_color_hex(0x11151b),0);lv_obj_set_style_text_color(root,lv_color_hex(0xe3e7eb),0);lv_obj_set_flex_flow(root,LV_FLEX_FLOW_COLUMN);lv_obj_set_style_pad_all(root,12,0);lv_obj_set_style_pad_row(root,6,0);
    job_label=label(root,"正在连接本地检测服务…");lv_obj_set_width(job_label,LV_PCT(100));
    auto controls=lv_obj_create(root);lv_obj_set_size(controls,LV_PCT(100),64);lv_obj_set_flex_flow(controls,LV_FLEX_FLOW_ROW);lv_obj_set_style_bg_opa(controls,LV_OPA_TRANSP,0);lv_obj_set_style_pad_all(controls,6,0);
    job_select=lv_dropdown_create(controls);lv_dropdown_set_options(job_select,"正在读取作业…");lv_obj_set_width(job_select,400);lv_group_add_obj(focus_group,job_select);button(controls,"选择作业",select_job);button(controls,"检查一件",check);pause_button=button(controls,"暂停检测",pause);
    statistics=label(root,"等待作业记录");lv_obj_set_width(statistics,LV_PCT(100));
    auto workspace=lv_obj_create(root);lv_obj_set_size(workspace,LV_PCT(100),440);lv_obj_set_flex_flow(workspace,LV_FLEX_FLOW_ROW);lv_obj_set_style_bg_opa(workspace,LV_OPA_TRANSP,0);lv_obj_set_style_pad_all(workspace,10,0);
    image.header.magic=LV_IMAGE_HEADER_MAGIC;image.header.cf=LV_COLOR_FORMAT_RGB565;image.header.w=416;image.header.h=416;image.header.stride=416*2;image.data_size=pixels.size();image.data=pixels.data();
    picture=lv_image_create(workspace);lv_image_set_src(picture,&image);result_label=label(workspace,"本次启动尚无检查记录");lv_obj_set_style_text_color(result_label,lv_color_hex(0xe3e7eb),0);lv_obj_set_flex_grow(result_label,1);
    fresh_label=label(root,"等待画面");error_label=label(root,"");lv_obj_set_width(error_label,LV_PCT(100));
    lv_evdev_discovery_start(discover,nullptr);
    engine.set_connection_timeout(0,300000);engine.set_read_timeout(0,600000);engine.set_write_timeout(0,600000);
    jobs(nullptr);lv_timer_create(jobs,2000,nullptr);lv_timer_create(refresh,100,nullptr);
    for(;;){lv_timer_handler();std::this_thread::sleep_for(std::chrono::milliseconds(5));}
}
