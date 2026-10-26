#include "lvgl.h"
#include "nlohmann/json.hpp"
#include "httplib.h"
#include "framebuffer.h"
#include "management.h"
#include "xp_style.h"
#include <algorithm>
#include <atomic>
#include <mutex>
#include <chrono>
#include <ctime>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <fcntl.h>
#include <sched.h>
#include <unistd.h>
using json=nlohmann::json;
namespace {
httplib::Client engine("http://127.0.0.1:8877");
lv_obj_t *result_label,*result_badge,*error_label,*fresh_label,*picture,*empty_label,*run_label;
lv_obj_t* counters[5];
lv_obj_t* counter_names[5];
lv_obj_t *product_label,*model_label,*batch_label,*result_eyebrow,*result_symbol,*result_surface;
lv_obj_t *app_window,*titlebar,*toolbar,*preview,*results,*report,*notices,*task_button,*clock_label,*health_dot,*mouse_cursor=nullptr;
lv_obj_t *check_button,*production_button;
std::mutex inspection_mailbox;
json polled_state,inspection_command;
std::string polled_frame,poll_error,command_error;
std::atomic<bool> inspection_busy{false},unconfirmed{false};
uint32_t poll_revision=0,painted_revision=0,polled_at=0;
void submit_inspection(const char* action,json payload=json::object()){
    std::lock_guard<std::mutex> lock(inspection_mailbox);if(inspection_busy)return;inspection_command={{"path",action},{"payload",payload}};inspection_busy=true;
}
const lv_font_t *ui_font,*title_font;
enum class Action { Show,Check,Production,Manage };
lv_group_t* focus_group;
lv_image_dsc_t image{};
std::vector<uint8_t> pixels(416*416*2);
std::vector<lv_obj_t*> rectangles;
std::string pending;
bool paused=false,production=false,picture_valid=false;
uint32_t displayed_frame=0,frame_at=0;
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
void text(lv_obj_t* label,const std::string& value){if(value!=lv_label_get_text(label))lv_label_set_text(label,value.c_str());}
void clear_picture() {
    if(!picture_valid)return;
    std::fill(pixels.begin(),pixels.end(),0);
    lv_image_set_src(picture,&image);lv_obj_invalidate(picture);
    for(auto object:rectangles)lv_obj_delete(object);
    rectangles.clear();picture_valid=false;
    if(empty_label)lv_obj_remove_flag(empty_label,LV_OBJ_FLAG_HIDDEN);
}
json get(const std::string& path) {
    const auto response=engine.Get(path);if(!response || response->status!=200)throw std::runtime_error("检测服务尚未就绪");return json::parse(response->body);
}
json post(const std::string& path,const json& payload) {
    const auto response=engine.Post(path,payload.dump(),"application/json");if(!response)throw std::runtime_error("检测服务暂时不可达，请核对上一次操作");
    const auto body=json::parse(response->body);
    if(response->status!=200){if(path=="/check" && body.contains("mayHaveSaved") && !body.at("mayHaveSaved").get<bool>()){store_pending("");pending.clear();unconfirmed=false;}throw std::runtime_error(body.value("error","检测服务拒绝了本次操作"));}return body;
}
lv_obj_t* label(lv_obj_t* parent,const char* value) {auto object=lv_label_create(parent);lv_label_set_text(object,value);lv_label_set_long_mode(object,LV_LABEL_LONG_WRAP);return object;}
lv_obj_t* panel(lv_obj_t* parent,int x,int y,int width,int height,uint32_t color) {
    auto object=lv_obj_create(parent);lv_obj_remove_style_all(object);lv_obj_set_pos(object,x,y);lv_obj_set_size(object,width,height);
    lv_obj_set_style_bg_color(object,lv_color_hex(color),0);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,0);
    lv_obj_remove_flag(object,LV_OBJ_FLAG_SCROLLABLE);lv_obj_remove_flag(object,LV_OBJ_FLAG_CLICKABLE);return object;
}
lv_obj_t* caption(lv_obj_t* parent,const char* value,int x,int y,int width,uint32_t color=0x182c43) {
    auto object=label(parent,value);lv_obj_set_pos(object,x,y);lv_obj_set_width(object,width);lv_obj_set_style_text_color(object,lv_color_hex(color),0);return object;
}
void vertical_scroll(lv_obj_t* object) {
    lv_obj_add_flag(object,LV_OBJ_FLAG_SCROLLABLE);lv_obj_add_flag(object,LV_OBJ_FLAG_CLICKABLE);lv_obj_set_scroll_dir(object,LV_DIR_VER);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x9cb8df),LV_PART_SCROLLBAR);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,LV_PART_SCROLLBAR);
    xp::scrollbar(object);
}
lv_obj_t* button(lv_obj_t* parent,const char* value,lv_event_cb_t action) {
    auto object=lv_button_create(parent);lv_obj_set_size(object,112,42);xp::skin(object,xp::Skin::Button);
    lv_obj_set_style_text_color(object,lv_color_hex(0x243950),0);
    lv_obj_set_style_text_color(object,lv_color_hex(0xa1a192),LV_STATE_DISABLED);
    auto title=label(object,value);lv_obj_center(title);lv_obj_add_event_cb(object,action,LV_EVENT_CLICKED,nullptr);lv_group_add_obj(focus_group,object);return object;
}
void check(lv_event_t*) {submit_inspection("/check");}
void production_toggle(lv_event_t*) {
    if(!production && unconfirmed){text(error_label,"请先再次点击检查，核对上一次操作");return;}
    submit_inspection("/production",{{"enabled",!production}});
}
void notify_refresh() {
    try {httplib::Client manager("http://127.0.0.1:8878");manager.set_connection_timeout(0,300000);manager.Post("/refresh","","application/json");}catch(const std::exception&){}
}
void inspection_worker(){
    uint32_t last_frame=0;
    for(;;){
        const auto poll_started=tick();
        json command;{std::lock_guard<std::mutex> lock(inspection_mailbox);command=std::move(inspection_command);inspection_command=nullptr;}
        std::string message;
        if(!command.is_null()){
            try{
                const std::string path=command.at("path");
                if(path=="/check"){
                    if(pending.empty()){std::ifstream file("/proc/sys/kernel/random/uuid");std::getline(file,pending);if(pending.size()!=36)throw std::runtime_error("无法建立检查编号");}
                    unconfirmed=true;store_pending(pending);post(path,{{"requestId",pending}});store_pending("");pending.clear();unconfirmed=false;
                }else post(path,command.at("payload"));
                notify_refresh();
            }catch(const std::exception& e){message=e.what();}
            {std::lock_guard<std::mutex> lock(inspection_mailbox);command_error=message;}
            inspection_busy=false;
        }
        try{
            auto state=get("/state");
            const auto unresolved=(state.contains("pendingRequestId") && state["pendingRequestId"].is_string())?state["pendingRequestId"].get<std::string>():std::string();
            if(pending.empty() && !unresolved.empty()){pending=unresolved;store_pending(pending);unconfirmed=true;}
            const auto frame=engine.Get("/frame?after="+std::to_string(last_frame));std::string data=frame && frame->status==200?std::move(frame->body):std::string();
            if(data.size()>=4){uint32_t size=0;std::memcpy(&size,data.data(),4);if(size<=100000 && data.size()>=4+size)last_frame=json::parse(data.substr(4,size)).at("frameId").get<uint32_t>();}
            {std::lock_guard<std::mutex> lock(inspection_mailbox);polled_state=std::move(state);polled_frame=std::move(data);poll_error.clear();polled_at=tick();if(polled_frame.size()>=4)frame_at=polled_at;++poll_revision;}
        }catch(const std::exception& e){std::lock_guard<std::mutex> lock(inspection_mailbox);poll_error=e.what();polled_frame.clear();++poll_revision;}
        const auto elapsed=tick()-poll_started;if(elapsed<40)std::this_thread::sleep_for(std::chrono::milliseconds(40-elapsed));
    }
}
void perform(Action action) {
    if(action==Action::Show){terminal::hide_management();lv_obj_move_foreground(app_window);lv_group_focus_obj(production_button);}
    else if(action==Action::Check)check(nullptr);
    else if(action==Action::Production)production_toggle(nullptr);
    else if(action==Action::Manage)terminal::show_management();
}
void update_clock(lv_timer_t*) {
    const auto now=std::time(nullptr);char value[16];std::strftime(value,sizeof(value),"%H:%M:%S",std::localtime(&now));text(clock_label,value);
}
void discover(lv_indev_t* input,lv_evdev_type_t type,void*) {
    if(type==LV_EVDEV_TYPE_KEY)lv_indev_set_group(input,terminal::management_input_group()?terminal::management_input_group():focus_group);
    else if(type==LV_EVDEV_TYPE_REL){
        if(!mouse_cursor){
            static uint32_t data[16*20]{};static lv_image_dsc_t cursor_image{};
            const char* shape[]={"B","BB","BWB","BWWB","BWWWB","BWWWWB","BWWWWWB","BWWWWWWB","BWWWWWWWB","BWWWWWWWWB","BWWWWWWWWWB","BWWWWWWBBBBB","BWWBWWB","BWB BWWB","BB  BWWB","B    BWWB","     BWWB","      BB"};
            for(unsigned y=0;y<18;++y)for(unsigned x=0;x<std::strlen(shape[y]);++x)data[y*16+x]=shape[y][x]=='B'?0xff000000:shape[y][x]=='W'?0xffffffff:0;
            cursor_image.header.magic=LV_IMAGE_HEADER_MAGIC;cursor_image.header.cf=LV_COLOR_FORMAT_ARGB8888;cursor_image.header.w=16;cursor_image.header.h=20;cursor_image.header.stride=64;cursor_image.data_size=sizeof(data);cursor_image.data=reinterpret_cast<const uint8_t*>(data);
            mouse_cursor=lv_image_create(lv_layer_sys());lv_image_set_src(mouse_cursor,&cursor_image);
        }
        lv_indev_set_cursor(input,mouse_cursor);
    }
}
void refresh(lv_timer_t*) {
    if(terminal::take_inspection_focus())perform(Action::Show);
    if(inspection_busy){lv_obj_add_state(check_button,LV_STATE_DISABLED);lv_obj_add_state(production_button,LV_STATE_DISABLED);}else if(unconfirmed)lv_obj_remove_state(check_button,LV_STATE_DISABLED);
    try {
        json state;std::string frame_data,error,action_error;uint32_t age;
        {std::lock_guard<std::mutex> lock(inspection_mailbox);if(painted_revision==poll_revision && tick()-polled_at<1500)return;painted_revision=poll_revision;state=polled_state;frame_data=polled_frame;error=poll_error;action_error=command_error;age=tick()-polled_at;}
        if(!error.empty() || state.is_null() || age>1500){clear_picture();lv_obj_add_state(check_button,LV_STATE_DISABLED);if(unconfirmed && !inspection_busy)lv_obj_remove_state(check_button,LV_STATE_DISABLED);lv_obj_add_state(production_button,LV_STATE_DISABLED);throw std::runtime_error(error.empty()?"等待检测服务…":error);}
        lv_obj_set_style_bg_color(health_dot,lv_color_hex(0x2bdf50),0);
        paused=state.at("paused");production=state.value("production",false);
        text(lv_obj_get_child(production_button,0),production?"停止检测":"开始检测");
        lv_obj_set_style_bg_color(production_button,lv_color_hex(production?0xb93846:0x176bde),0);
        lv_obj_set_style_text_color(production_button,lv_color_white(),0);
        const bool has_model=!state.at("model").is_null();
        const bool has_product=!state.at("product").is_null();
        const std::string phase=state.value("passagePhase",std::string());
        const bool pending=state.contains("pendingRequestId") && state["pendingRequestId"].is_string();
        const bool ready=has_model && has_product && !paused && state.at("error").get<std::string>().empty() && !pending && !unconfirmed && state.value("fresh",false);
        text(run_label,pending?"上次记录尚未确认":!state.at("error").get<std::string>().empty()?"检测异常":!has_model?"未部署模型":!has_product?"未分配产品方案":paused?"检测服务已暂停":!state.value("fresh",false)?"等待有效图像":production?(phase=="CLEARING"?"请移走当前产品，等待空场景":phase=="INSPECTING"?"正在检查 · 离开后自动保存":phase=="SAVING"?"正在保存单件记录":"自动检测 · 等待产品"):"已停止自动检测");
        const bool can_check=!inspection_busy && (unconfirmed || pending || (ready && !production));
        if(can_check)lv_obj_remove_state(check_button,LV_STATE_DISABLED);else lv_obj_add_state(check_button,LV_STATE_DISABLED);
        if((production || ready) && !inspection_busy)lv_obj_remove_state(production_button,LV_STATE_DISABLED);else lv_obj_add_state(production_button,LV_STATE_DISABLED);
        text(lv_obj_get_child(check_button,0),unconfirmed?"核对上次":"检查一件");
        const std::string model_text=has_model?state["model"].value("version",std::string()):"未部署";
        const std::string product_text=has_product?state["product"].value("product",state["product"].value("name",std::string())):"未分配";
        const std::string plan_text=has_product?state["product"].at("name").get<std::string>()+" / V"+std::to_string(state["product"].at("version").get<unsigned>()):"未分配";
        const std::string run=state["productionRunId"].is_string()?state["productionRunId"].get<std::string>():"";
        text(product_label,product_text);
        text(model_label,"模型  "+model_text+"    /    方案  "+plan_text);
        text(batch_label,"批次  "+(run.empty()?std::string("尚未开始"):run.substr(0,8)));
        text(empty_label,!has_model?"未部署模型\n请在平台下发模型":!has_product?"未分配产品\n请在平台分配产品":"等待画面…");
        const bool has_run=state.contains("productionRunId") && state["productionRunId"].is_string() && !state["productionRunId"].get<std::string>().empty();
        const auto& counts=has_run?state.at("runCounts"):state.at("counts");
        const unsigned values[]={state.at(has_run?"runTotal":"total").get<unsigned>(),counts["PASS"].get<unsigned>(),counts["FAIL"].get<unsigned>(),counts["REVIEW"].get<unsigned>()+counts["ERROR"].get<unsigned>(),state["pendingSync"].get<unsigned>()};
        const char* names[]={has_run?"本批次检测":"累计检测","合格","不合格","待处理","待同步"};
        for(unsigned i=0;i<5;++i){text(counter_names[i],names[i]);text(counters[i],std::to_string(values[i]));}
        std::string requirements=has_product?"当前方案要求":"请在 Web 配置并分配产品方案";
        if(has_product && state["product"].contains("checks"))for(const auto& check:state["product"]["checks"]) {
            requirements+='\n'+check.at("label").get<std::string>()+"："+std::to_string(check.at("min").get<unsigned>())+"–"+std::to_string(check.at("max").get<unsigned>())+" 个";
            if(check.contains("region")){const auto& r=check["region"];requirements+="；中心 X "+std::to_string(int(r["x"].get<double>()*100))+"–"+std::to_string(int((r["x"].get<double>()+r["width"].get<double>())*100))+"%，Y "+std::to_string(int(r["y"].get<double>()*100))+"–"+std::to_string(int((r["y"].get<double>()+r["height"].get<double>())*100))+"%";}
        }
        const bool liquid_model=has_model && state["model"].contains("classes") && std::find(state["model"]["classes"].begin(),state["model"]["classes"].end(),"level_deviation")!=state["model"]["classes"].end();
        if(liquid_model && has_product)requirements="检测项目   液位高度\n判定方式   目标识别与液位测量\n操作提示   放入瓶体后开始检测";
        else if(has_product)requirements+="\n\n"+state["product"].value("instructions",std::string());
        if(!state.at("last").is_null()) {
            const auto& last=state.at("last");std::string report;
            text(result_eyebrow,"最近一次检测   /   第 "+std::to_string(last.at("sequence").get<unsigned>())+" 件");
            const std::string result=last.at("result");text(result_badge,result=="PASS"?"检测合格":result=="FAIL"?"检测不合格":result=="REVIEW"?"待人工复核":"检测异常");
            const uint32_t tint=result=="PASS"?0xeaf7f1:result=="FAIL"?0xffeff0:0xfff7e8;
            const uint32_t ink=result=="PASS"?0x148362:result=="FAIL"?0xc83c4e:0xb47a18;
            lv_obj_set_style_bg_color(result_surface,lv_color_hex(tint),0);
            text(result_symbol,result=="PASS"?"PASS":result=="FAIL"?"FAIL":result=="REVIEW"?"REVIEW":"ERROR");
            lv_obj_set_style_text_color(result_symbol,lv_color_hex(ink),0);
            if(last.contains("reason"))report=last.at("reason").get<std::string>();
            lv_obj_set_style_text_color(result_badge,lv_color_hex(result=="PASS"?0x22712b:result=="FAIL"?0xb3261e:0x925b00),0);
            if(last.contains("findings"))for(const auto& finding:last["findings"]){if(!report.empty())report+='\n';report+=(finding.at("label")=="level_deviation"?std::string("液位检测"):finding.at("label").get<std::string>())+"：确认 "+std::to_string(finding.at("count").get<unsigned>())+"，待确认 "+std::to_string(finding.at("uncertain").get<unsigned>())+"，要求 "+std::to_string(finding.at("min").get<unsigned>())+"–"+std::to_string(finding.at("max").get<unsigned>());}
            text(result_label,report.empty()?requirements:report);
        }else {text(result_label,requirements);text(result_eyebrow,"单件判定   /   等待检测");text(result_badge,"准备就绪");text(result_symbol,"READY");lv_obj_set_style_bg_color(result_surface,lv_color_hex(0xeef4fd),0);lv_obj_set_style_text_color(result_badge,lv_color_hex(0x234a7c),0);lv_obj_set_style_text_color(result_symbol,lv_color_hex(0x176bde),0);}
        const bool sync_error=!state.at("syncError").get<std::string>().empty();
        std::string notice=action_error+(!action_error.empty()?"\n":"")+state.at("error").get<std::string>()+(sync_error?"\n记录同步异常 · 请查看平台连接":"");
        text(error_label,notice.empty()?"检测记录自动保存 · 结果同步至 CNN Studio":notice);
        lv_obj_set_style_text_color(error_label,lv_color_hex(notice.empty()?0x718197:action_error.empty() && state.at("error").get<std::string>().empty()?0xb47a18:0xc83c4e),0);
        if(frame_data.size()<4){
            // 单帧缺失不清屏：保留上一帧与跟踪框，只有持续拿不到新帧才提示。
            if(picture_valid && tick()-frame_at<1500)return;
            clear_picture();text(fresh_label,"无图像");return;
        }
        uint32_t size=0;std::memcpy(&size,frame_data.data(),4);
        if(size>100000 || frame_data.size()!=4+size+pixels.size())throw std::runtime_error("画面数据长度异常");
        const auto frame=json::parse(frame_data.substr(4,size));
        const auto frame_id=frame.at("frameId").get<uint32_t>();
        if(picture_valid && frame.at("fresh").get<bool>() && displayed_frame==frame_id)return;
        std::memcpy(pixels.data(),frame_data.data()+4+size,pixels.size());displayed_frame=frame_id;
        lv_image_set_src(picture,&image);lv_obj_invalidate(picture);picture_valid=true;lv_obj_add_flag(empty_label,LV_OBJ_FLAG_HIDDEN);
        unsigned confirmed=0;for(const auto& b:frame.at("boxes"))if(b.value("trackConfirmed",false))++confirmed;
        const bool truncated=frame.contains("postprocess") && (frame["postprocess"].value("overflow",false) || frame["postprocess"].value("invalid",0u));
        text(fresh_label,(frame.at("fresh").get<bool>()?"实时画面":"画面已超时")+std::string(" · #")+std::to_string(frame.at("frameId").get<unsigned>())+" · 本帧目标 "+std::to_string(frame.at("boxes").size())+" · 稳定跟踪 "+std::to_string(confirmed)+(truncated?" · 目标异常，请复核":""));
        if(frame.contains("level")){
            const auto& level=frame.at("level");std::string value=level.at("status");
            if(!level.at("row").is_null()){const auto row=std::to_string(level.at("row").get<double>());value+=" · "+row.substr(0,row.find('.')+3)+" 行";}
            text(fresh_label,(frame.at("fresh").get<bool>()?"实时 · ":"超时 · ")+value+" · 合格带 85.00–102.90");
        }
        for(auto object:rectangles)lv_obj_delete(object);rectangles.clear();
        if(has_product && frame.at("planId")==state["product"].at("id") && frame.at("planVersion")==state["product"].at("version") && state["product"].contains("checks"))for(const auto& check:state["product"]["checks"])if(check.contains("region")) {
            const auto& r=check["region"];auto rectangle=lv_obj_create(picture);lv_obj_remove_style_all(rectangle);
            lv_obj_set_pos(rectangle,int(r["x"].get<double>()*416),int(r["y"].get<double>()*416));lv_obj_set_size(rectangle,int(r["width"].get<double>()*416),int(r["height"].get<double>()*416));
            lv_obj_set_style_border_width(rectangle,2,0);lv_obj_set_style_border_color(rectangle,lv_color_hex(0xe6ad39),0);rectangles.push_back(rectangle);
            caption(rectangle,(check.at("label").get<std::string>()+" 合格中心范围").c_str(),3,2,200,0xe6ad39);
        }
        if(frame.at("fresh").get<bool>())for(const auto& box:frame.at("boxes")) {
            const uint32_t palette[]={0x60c5ff,0xffc857,0xd495ff,0x75d69c,0xff9292,0x5fdfd4};
            const unsigned cls=box.at("classId").get<unsigned>();const auto color=palette[cls%6];
            auto rectangle=lv_obj_create(picture);lv_obj_remove_style_all(rectangle);
            lv_obj_set_pos(rectangle,int(box["x1"].get<double>()),int(box["y1"].get<double>()));lv_obj_set_size(rectangle,int(box["x2"].get<double>()-box["x1"].get<double>()),int(box["y2"].get<double>()-box["y1"].get<double>()));lv_obj_set_style_border_width(rectangle,2,0);lv_obj_set_style_border_color(rectangle,lv_color_hex(color),0);rectangles.push_back(rectangle);
            const std::string label=cls<frame.at("modelClasses").size()?frame["modelClasses"][cls].get<std::string>():"类别 "+std::to_string(cls);
            std::string value=label+" "+std::to_string(unsigned(box.at("confidence").get<double>()*100+.5))+"%";
            const unsigned id=box.value("trackId",0u);if(id)value+=" #"+std::to_string(id)+(box.value("trackConfirmed",false)?"":"?");
            lv_point_t extent;lv_text_get_size(&extent,value.c_str(),ui_font,0,0,1000,LV_TEXT_FLAG_NONE);
            const int width=std::min(416,int(extent.x)+8),x=std::clamp(int(box["x1"].get<double>()),0,416-width),y=std::clamp(int(box["y1"].get<double>())>=18?int(box["y1"].get<double>())-18:int(box["y1"].get<double>()),0,398);
            auto tag=panel(picture,x,y,width,18,color);auto title=caption(tag,value.c_str(),4,1,width-8);lv_label_set_long_mode(title,LV_LABEL_LONG_DOT);rectangles.push_back(tag);
        }
    }catch(const std::exception& e){clear_picture();lv_obj_set_style_bg_color(health_dot,lv_color_hex(0xd93025),0);text(fresh_label,"画面不可用");text(run_label,"服务连接异常");text(error_label,e.what());text(result_badge,"等待连接");text(result_symbol,"OFFLINE");lv_obj_set_style_text_color(result_badge,lv_color_hex(0x718197),0);lv_obj_set_style_text_color(result_symbol,lv_color_hex(0x718197),0);lv_obj_set_style_bg_color(result_surface,lv_color_hex(0xf0f3f7),0);}
}
}
int main(int argc,char** argv) {
    if(argc!=2){std::cerr<<"Usage: vision-panel CHINESE_FONT_FILE\n";return 2;}
    cpu_set_t cpu;CPU_ZERO(&cpu);CPU_SET(0,&cpu);
    if(sched_setaffinity(0,sizeof(cpu),&cpu)){std::cerr<<"Cannot assign panel CPU\n";return 1;}
    {std::ifstream file(pending_file);std::getline(file,pending);if(!pending.empty() && (pending.size()!=36 || pending.find_first_not_of("0123456789abcdef-")!=std::string::npos)){std::cerr<<"Invalid saved panel operation\n";return 1;}}
    lv_init();lv_tick_set_cb(tick);focus_group=lv_group_create();lv_group_set_default(focus_group);
    lv_log_register_print_cb([](lv_log_level_t,const char* message){std::cerr<<message;});
    Framebuffer framebuffer;
    ui_font=xp::pixel_font(argv[1],16);title_font=xp::pixel_font(argv[1],22,true);
    auto small_font=xp::pixel_font(argv[1],13);auto result_font=xp::pixel_font(argv[1],36,true);auto number_font=xp::pixel_font(argv[1],30,true);
    auto root=lv_screen_active();lv_obj_set_style_text_font(root,ui_font,0);lv_obj_set_style_text_color(root,lv_color_hex(0x182c43),0);
    lv_obj_set_style_bg_color(root,lv_color_hex(0xf0f4f8),0);lv_obj_set_style_pad_all(root,0,0);lv_obj_remove_flag(root,LV_OBJ_FLAG_SCROLLABLE);
    app_window=panel(root,0,0,1280,720,0xf0f4f8);
    auto card=[](lv_obj_t* parent,int x,int y,int w,int h){auto object=panel(parent,x,y,w,h,0xffffff);lv_obj_set_style_radius(object,12,0);lv_obj_set_style_border_width(object,1,0);lv_obj_set_style_border_color(object,lv_color_hex(0xe0e7ef),0);return object;};
    titlebar=panel(app_window,0,0,1280,72,0x14283f);
    auto mark=panel(titlebar,24,17,38,38,0x2677eb);lv_obj_set_style_radius(mark,10,0);
    for(int row=0;row<3;++row)for(int col=0;col<3;++col){auto dot=panel(mark,9+col*8,9+row*8,4,4,0xffffff);lv_obj_set_style_radius(dot,1,0);}
    auto heading=caption(titlebar,"CNN STUDIO",76,13,230,0xffffff);lv_obj_set_style_text_font(heading,title_font,0);
    auto subtitle=caption(titlebar,"FPGA 视觉检测终端",77,42,240,0x97abc2);lv_obj_set_style_text_font(subtitle,small_font,0);
    auto active=panel(titlebar,358,16,132,40,0x25425f);lv_obj_set_style_radius(active,8,0);caption(active,"检测工作台",24,10,110,0xffffff);
    auto record=button(titlebar,"检测记录",[](lv_event_t*){terminal::show_management_tab(6);});lv_obj_set_pos(record,506,16);lv_obj_set_style_bg_color(record,lv_color_hex(0x14283f),0);lv_obj_set_style_text_color(record,lv_color_hex(0xb8c9db),0);lv_obj_set_style_border_width(record,0,0);
    auto manage=button(titlebar,"系统管理",[](lv_event_t*){terminal::show_management_tab(0);});lv_obj_set_pos(manage,634,16);lv_obj_set_style_bg_color(manage,lv_color_hex(0x14283f),0);lv_obj_set_style_text_color(manage,lv_color_hex(0xb8c9db),0);lv_obj_set_style_border_width(manage,0,0);
    health_dot=panel(titlebar,966,32,8,8,0x8ca1b8);lv_obj_set_style_radius(health_dot,4,0);
    caption(titlebar,"设备连接",984,27,100,0xb8c9db);
    clock_label=caption(titlebar,"",1122,25,134,0xffffff);lv_obj_set_style_text_align(clock_label,LV_TEXT_ALIGN_RIGHT,0);update_clock(nullptr);lv_timer_create(update_clock,1000,nullptr);
    toolbar=card(app_window,24,88,1232,80);
    auto config_mark=panel(toolbar,0,17,4,46,0x2677eb);lv_obj_set_style_radius(config_mark,2,0);
    product_label=caption(toolbar,"未分配产品",20,10,600);lv_obj_set_style_text_font(product_label,title_font,0);lv_label_set_long_mode(product_label,LV_LABEL_LONG_DOT);
    model_label=caption(toolbar,"模型与方案等待平台下发",20,46,710,0x718197);lv_obj_set_style_text_font(model_label,small_font,0);lv_label_set_long_mode(model_label,LV_LABEL_LONG_DOT);
    batch_label=caption(toolbar,"批次  尚未开始",740,29,180,0x718197);lv_obj_set_style_text_font(batch_label,small_font,0);lv_label_set_long_mode(batch_label,LV_LABEL_LONG_DOT);
    production_button=button(toolbar,"开始检测",production_toggle);lv_obj_set_pos(production_button,934,18);lv_obj_set_size(production_button,152,44);lv_obj_set_style_bg_color(production_button,lv_color_hex(0x176bde),0);lv_obj_set_style_text_color(production_button,lv_color_white(),0);lv_obj_set_style_border_width(production_button,0,0);
    check_button=button(toolbar,"检查一件",check);lv_obj_set_pos(check_button,1098,18);lv_obj_set_size(check_button,114,44);
    preview=card(app_window,24,188,464,500);
    caption(preview,"相机画面",24,16,220);auto live=caption(preview,"LIVE  /  416 × 416",257,19,183,0x718197);lv_obj_set_style_text_font(live,small_font,0);lv_obj_set_style_text_align(live,LV_TEXT_ALIGN_RIGHT,0);
    image.header.magic=LV_IMAGE_HEADER_MAGIC;image.header.cf=LV_COLOR_FORMAT_RGB565;image.header.w=416;image.header.h=416;image.header.stride=416*2;image.data_size=pixels.size();image.data=pixels.data();
    picture=lv_image_create(preview);lv_obj_set_pos(picture,24,52);lv_image_set_src(picture,&image);
    empty_label=caption(preview,"等待相机画面",48,240,368,0x98aac0);lv_obj_set_style_text_align(empty_label,LV_TEXT_ALIGN_CENTER,0);lv_obj_set_style_text_line_space(empty_label,12,0);
    fresh_label=caption(preview,"无图像",24,478,416,0x718197);lv_obj_set_style_text_font(fresh_label,small_font,0);lv_label_set_long_mode(fresh_label,LV_LABEL_LONG_DOT);
    const char* initial[]={"累计检测","合格","不合格","待处理","待同步"};const uint32_t colors[]={0x243950,0x148362,0xc83c4e,0xb47a18,0x176bde};
    for(unsigned i=0;i<5;++i){auto cell=card(app_window,508+int(i)*152,188,140,90);counter_names[i]=caption(cell,initial[i],16,12,118,0x718197);lv_obj_set_style_text_font(counter_names[i],small_font,0);counters[i]=caption(cell,"0",16,39,116,colors[i]);lv_obj_set_style_text_font(counters[i],number_font,0);}
    results=card(app_window,508,294,748,394);
    result_eyebrow=caption(results,"单件判定   /   等待检测",24,18,680,0x718197);lv_obj_set_style_text_font(result_eyebrow,small_font,0);
    result_surface=panel(results,24,48,700,100,0xeef4fd);lv_obj_set_style_radius(result_surface,10,0);
    result_badge=caption(result_surface,"等待检测",20,24,470,0x234a7c);lv_obj_set_style_text_font(result_badge,result_font,0);
    result_symbol=caption(result_surface,"READY",500,36,176,0x176bde);lv_obj_set_style_text_font(result_symbol,title_font,0);lv_obj_set_style_text_align(result_symbol,LV_TEXT_ALIGN_RIGHT,0);
    report=panel(results,24,166,700,150,0xffffff);vertical_scroll(report);result_label=caption(report,"等待检测服务就绪",0,0,680,0x41566e);lv_obj_set_style_text_line_space(result_label,9,0);
    panel(results,24,333,700,1,0xe5ebf2);notices=panel(results,24,346,700,38,0xffffff);vertical_scroll(notices);error_label=caption(notices,"",0,0,680,0x718197);lv_obj_set_style_text_font(error_label,small_font,0);
    run_label=caption(app_window,"等待检测服务",32,699,850,0x718197);lv_obj_set_style_text_font(run_label,small_font,0);
    auto signature=caption(app_window,"ZYNQ-7020   /   EDGE AI VISION",908,699,340,0x8d9bad);lv_obj_set_style_text_font(signature,small_font,0);lv_obj_set_style_text_align(signature,LV_TEXT_ALIGN_RIGHT,0);
    // Management owns a full-screen page; this hidden host carries its focus state.
    auto taskbar=panel(root,0,0,1,1,0x14283f);lv_obj_add_flag(taskbar,LV_OBJ_FLAG_HIDDEN);task_button=button(taskbar,"",[](lv_event_t*){});
    terminal::create_management(root,taskbar,ui_font,title_font,task_button,focus_group);
    lv_group_focus_obj(production_button);
    lv_evdev_discovery_start(discover,nullptr);
    engine.set_connection_timeout(0,300000);engine.set_read_timeout(0,600000);engine.set_write_timeout(0,600000);
    unconfirmed=!pending.empty();std::thread(inspection_worker).detach();lv_timer_create(refresh,40,nullptr);
    for(;;){lv_timer_handler();std::this_thread::sleep_for(std::chrono::milliseconds(5));}
}
