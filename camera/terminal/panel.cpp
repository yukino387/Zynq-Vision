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
lv_obj_t *job_label,*result_label,*result_badge,*error_label,*fresh_label,*job_select,*picture,*empty_label,*run_label;
lv_obj_t* counters[5];
lv_obj_t *app_window,*titlebar,*toolbar,*workspace,*preview,*results,*report,*notices,*statusbar,*task_button,*start_button,*clock_label,*health_dot,*popup_layer=nullptr,*mouse_cursor=nullptr;
lv_obj_t *min_button,*max_button,*close_button,*check_button,*production_button,*login_button;
std::mutex inspection_mailbox;
json polled_state,inspection_command;
std::string polled_frame,poll_error,command_error;
std::atomic<bool> inspection_busy{false},unconfirmed{false};
uint32_t poll_revision=0,painted_revision=0,polled_at=0;
void submit_inspection(const char* action,json payload=json::object()){
    std::lock_guard<std::mutex> lock(inspection_mailbox);if(inspection_busy)return;inspection_command={{"path",action},{"payload",payload}};inspection_busy=true;
}
lv_group_t* menu_group=nullptr;
const lv_font_t *ui_font,*title_font,*menu_title_font;
bool maximized=false;
int window_x=20,window_y=16;
lv_point_t drag_point;
enum class Action { Show,Minimize,Maximize,Close,Check,Production,Manage,ShowDesktop };
lv_group_t* focus_group;
lv_image_dsc_t image{};
std::vector<uint8_t> pixels(416*416*2);
std::vector<lv_obj_t*> rectangles;
std::string pending,selector_cache;
bool paused=false,production=false,picture_valid=false;
uint32_t displayed_frame=0;
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
lv_obj_t* caption(lv_obj_t* parent,const char* value,int x,int y,int width,uint32_t color=0x000000) {
    auto object=label(parent,value);lv_obj_set_pos(object,x,y);lv_obj_set_width(object,width);lv_obj_set_style_text_color(object,lv_color_hex(color),0);return object;
}
void bevel(lv_obj_t* object,uint32_t edge=0x7f9db9) {
    lv_obj_set_style_border_width(object,1,0);lv_obj_set_style_border_color(object,lv_color_hex(edge),0);
    lv_obj_set_style_radius(object,3,0);lv_obj_set_style_shadow_width(object,0,0);
}
void vertical_scroll(lv_obj_t* object) {
    lv_obj_add_flag(object,LV_OBJ_FLAG_SCROLLABLE);lv_obj_add_flag(object,LV_OBJ_FLAG_CLICKABLE);lv_obj_set_scroll_dir(object,LV_DIR_VER);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x9cb8df),LV_PART_SCROLLBAR);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,LV_PART_SCROLLBAR);
    xp::scrollbar(object);
}
lv_obj_t* button(lv_obj_t* parent,const char* value,lv_event_cb_t action) {
    auto object=lv_button_create(parent);lv_obj_set_size(object,88,23);xp::skin(object,xp::Skin::Button);
    lv_obj_set_style_text_color(object,lv_color_black(),0);
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
            {std::lock_guard<std::mutex> lock(inspection_mailbox);polled_state=std::move(state);polled_frame=std::move(data);poll_error.clear();polled_at=tick();++poll_revision;}
        }catch(const std::exception& e){std::lock_guard<std::mutex> lock(inspection_mailbox);poll_error=e.what();polled_frame.clear();++poll_revision;}
        if(tick()-poll_started<10)std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}
void close_popup() {
    if(!popup_layer)return;lv_obj_delete(popup_layer);popup_layer=nullptr;
    if(menu_group){lv_group_delete(menu_group);menu_group=nullptr;}
    lv_obj_remove_state(start_button,LV_STATE_CHECKED);
    for(auto input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,terminal::management_input_group()?terminal::management_input_group():focus_group);
}
void layout_window() {
    const int width=maximized?1280:1240,height=maximized?690:658;
    lv_obj_set_pos(app_window,maximized?0:window_x,maximized?0:window_y);lv_obj_set_size(app_window,width,height);
    lv_obj_set_width(titlebar,width);lv_obj_set_width(toolbar,width-6);
    lv_obj_set_pos(min_button,width-72,5);lv_obj_set_pos(max_button,width-49,5);lv_obj_set_pos(close_button,width-26,5);
    lv_obj_set_width(job_label,width-32);
    const int cell=(width-24)/5;
    for(unsigned i=0;i<5;++i){auto parent=lv_obj_get_parent(counters[i]);lv_obj_set_pos(parent,12+int(i)*cell,124);lv_obj_set_width(parent,cell-4);lv_obj_set_width(counters[i],cell-18);}
    lv_obj_set_size(workspace,width-24,height-194);lv_obj_set_height(preview,height-194);
    lv_obj_set_size(results,width-472,height-194);lv_obj_set_width(lv_obj_get_child(results,0),width-474);
    lv_obj_set_width(result_badge,width-500);lv_obj_set_size(report,width-496,height-380);lv_obj_set_width(result_label,width-520);
    lv_obj_set_pos(notices,10,height-292);lv_obj_set_size(notices,width-496,84);lv_obj_set_width(error_label,width-520);
    lv_obj_set_pos(statusbar,8,height-26);lv_obj_set_width(statusbar,width-16);lv_obj_set_pos(run_label,width-230,1);
    xp::skin(max_button,maximized?xp::Skin::Restore:xp::Skin::Maximize);
}
void perform(Action action) {
    close_popup();
    if(action==Action::Show || action==Action::Minimize || action==Action::Close || action==Action::Maximize)lv_dropdown_close(job_select);
    if(action==Action::Show){terminal::blur_management();lv_obj_remove_flag(app_window,LV_OBJ_FLAG_HIDDEN);lv_obj_move_foreground(app_window);lv_obj_remove_flag(task_button,LV_OBJ_FLAG_HIDDEN);lv_obj_add_state(task_button,LV_STATE_CHECKED);xp::activate_window(app_window);lv_group_focus_obj(job_select);}
    else if(action==Action::Minimize || action==Action::Close){lv_obj_add_flag(app_window,LV_OBJ_FLAG_HIDDEN);xp::deactivate_window(app_window);lv_obj_remove_state(task_button,LV_STATE_CHECKED);if(action==Action::Close)lv_obj_add_flag(task_button,LV_OBJ_FLAG_HIDDEN);}
    else if(action==Action::Maximize){maximized=!maximized;layout_window();}
    else if(action==Action::Check)check(nullptr);
    else if(action==Action::Production)production_toggle(nullptr);
    else if(action==Action::Manage)terminal::show_management();
    else if(action==Action::ShowDesktop){perform(Action::Minimize);terminal::hide_management();}
}
void dispatch(lv_event_t* event) {perform(static_cast<Action>(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event))));}
void task_click(lv_event_t*) {perform((lv_obj_has_flag(app_window,LV_OBJ_FLAG_HIDDEN)||!lv_obj_has_state(task_button,LV_STATE_CHECKED))?Action::Show:Action::Minimize);}
void drag_window(lv_event_t* event) {
    if(maximized)return;
    lv_point_t point;lv_indev_get_point(lv_indev_active(),&point);
    if(lv_event_get_code(event)==LV_EVENT_PRESSING){window_x=std::clamp(window_x+int(point.x-drag_point.x),0,1280-lv_obj_get_width(app_window));window_y=std::clamp(window_y+int(point.y-drag_point.y),0,690-lv_obj_get_height(app_window));lv_obj_set_pos(app_window,window_x,window_y);}
    drag_point=point;
}
lv_obj_t* menu_item(lv_obj_t* parent,const char* value,int y,Action action,bool with_icon=false) {
    lv_obj_update_layout(parent);
    auto object=button(parent,value,dispatch);lv_obj_set_pos(object,4,y);lv_obj_set_size(object,lv_obj_get_width(parent)-8,30);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xffffff),0);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_NONE,0);lv_obj_set_style_border_width(object,0,0);lv_obj_set_style_radius(object,0,0);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x316ac5),LV_STATE_PRESSED);lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_PRESSED);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x316ac5),LV_STATE_HOVERED);lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_HOVERED);
    xp::skin(object,xp::Skin::Menu);
    if(with_icon)xp::icon(object,action==Action::Manage?xp::Icon::Control:xp::Icon::Computer,16,5,7);
    auto title=lv_obj_get_child(object,0);lv_obj_align(title,LV_ALIGN_LEFT_MID,with_icon?26:18,0);
    lv_obj_remove_event_cb(object,dispatch);lv_obj_add_event_cb(object,dispatch,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(action)));
    lv_group_remove_obj(object);lv_group_add_obj(menu_group,object);
    lv_obj_add_event_cb(object,[](lv_event_t* e){const auto key=lv_event_get_key(e);if(key==LV_KEY_ESC){close_popup();return;}if(key==LV_KEY_DOWN)lv_group_focus_next(menu_group);else if(key==LV_KEY_UP)lv_group_focus_prev(menu_group);},LV_EVENT_KEY,nullptr);
    return object;
}
lv_obj_t* popup(int x,int y,int width,int height) {
    close_popup();menu_group=lv_group_create();popup_layer=panel(lv_layer_top(),0,0,1280,720,0xffffff);lv_obj_set_style_bg_opa(popup_layer,LV_OPA_TRANSP,0);lv_obj_add_flag(popup_layer,LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(popup_layer,[](lv_event_t*){close_popup();},LV_EVENT_CLICKED,nullptr);
    auto menu=panel(popup_layer,x,y,width,height,0xffffff);bevel(menu,0x808080);lv_obj_set_style_radius(menu,0,0);
    lv_obj_set_style_text_font(menu,ui_font,0);
    lv_obj_set_style_shadow_width(menu,8,0);lv_obj_set_style_shadow_opa(menu,LV_OPA_30,0);lv_obj_set_style_shadow_ofs_x(menu,3,0);lv_obj_set_style_shadow_ofs_y(menu,3,0);
    for(auto input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,menu_group);
    return menu;
}
void start_left_icon(lv_obj_t* object,Action action) {xp::icon(object,action==Action::Manage?xp::Icon::Control:xp::Icon::Computer,32,5,2);}
void start_tab_icon(lv_obj_t* object,unsigned tab) {
    const xp::Icon icons[]={xp::Icon::Control,xp::Icon::Document,xp::Icon::Network,xp::Icon::Disk,xp::Icon::Device,xp::Icon::Document,xp::Icon::Records,xp::Icon::Jobs};
    auto image=xp::icon(object,icons[std::min(tab,7u)],32,5,3);lv_image_set_scale(image,192);
}
lv_obj_t* start_left_item(lv_obj_t* parent,const char* text,int y,Action action) {
    auto object=button(parent,text,dispatch);lv_obj_set_pos(object,4,y);lv_obj_set_size(object,181,36);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xffffff),0);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_NONE,0);lv_obj_set_style_border_width(object,0,0);lv_obj_set_style_radius(object,0,0);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x316ac5),LV_STATE_HOVERED);lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_HOVERED);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x316ac5),LV_STATE_PRESSED);lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_PRESSED);
    xp::skin(object,xp::Skin::Menu);start_left_icon(object,action);
    lv_obj_align(lv_obj_get_child(object,0),LV_ALIGN_LEFT_MID,38,0);
    lv_obj_remove_event_cb(object,dispatch);lv_obj_add_event_cb(object,dispatch,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(action)));
    lv_group_remove_obj(object);lv_group_add_obj(menu_group,object);
    lv_obj_add_event_cb(object,[](lv_event_t* e){if(lv_event_get_key(e)==LV_KEY_ESC)close_popup();else if(lv_event_get_key(e)==LV_KEY_DOWN)lv_group_focus_next(menu_group);else if(lv_event_get_key(e)==LV_KEY_UP)lv_group_focus_prev(menu_group);},LV_EVENT_KEY,nullptr);return object;
}
lv_obj_t* start_tab_item(lv_obj_t* parent,const char* text,int y,unsigned tab,bool right) {
    auto object=button(parent,text,[](lv_event_t*){});lv_obj_set_pos(object,4,y);lv_obj_set_size(object,181,36);
    lv_obj_set_style_bg_color(object,lv_color_hex(right?0xd3e5fa:0xffffff),0);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_NONE,0);lv_obj_set_style_border_width(object,0,0);lv_obj_set_style_radius(object,0,0);
    lv_obj_set_style_text_color(object,lv_color_hex(right?0x00136b:0x000000),0);
    lv_obj_set_style_bg_color(object,lv_color_hex(right?0x1b4fa8:0x316ac5),LV_STATE_HOVERED);lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_HOVERED);
    lv_obj_set_style_bg_color(object,lv_color_hex(right?0x1b4fa8:0x316ac5),LV_STATE_PRESSED);lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_PRESSED);
    xp::skin(object,xp::Skin::Menu);start_tab_icon(object,tab);
    lv_obj_align(lv_obj_get_child(object,0),LV_ALIGN_LEFT_MID,38,0);
    lv_obj_add_event_cb(object,[](lv_event_t* event){close_popup();terminal::show_management_tab(unsigned(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event))));},LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(tab)));
    lv_group_remove_obj(object);lv_group_add_obj(menu_group,object);
    lv_obj_add_event_cb(object,[](lv_event_t* e){if(lv_event_get_key(e)==LV_KEY_ESC)close_popup();else if(lv_event_get_key(e)==LV_KEY_DOWN)lv_group_focus_next(menu_group);else if(lv_event_get_key(e)==LV_KEY_UP)lv_group_focus_prev(menu_group);},LV_EVENT_KEY,nullptr);return object;
}
void start_menu(lv_event_t*) {
    if(popup_layer){close_popup();return;}
    auto menu=popup(0,246,380,444);lv_obj_add_state(start_button,LV_STATE_CHECKED);
    auto header=panel(menu,1,1,378,62,0x0062ea);lv_obj_set_style_bg_grad_color(header,lv_color_hex(0x081bcb),0);lv_obj_set_style_bg_grad_dir(header,LV_GRAD_DIR_VER,0);panel(header,0,0,378,2,0x5db3ff);
    auto avatar=lv_image_create(header);lv_image_set_src(avatar,&xp::assets::user);lv_obj_set_pos(avatar,8,7);
    auto name=caption(header,"巡检终端",64,7,300,0xffffff);lv_obj_set_style_text_font(name,menu_title_font,0);
    caption(header,"本地视觉检测",64,31,300,0xd6e5ff);
    auto left=panel(menu,1,63,189,337,0xffffff);
    auto right=panel(menu,190,63,189,337,0xd3e5fa);panel(menu,189,63,1,337,0x95bdee);
    start_left_item(left,"视觉检测",8,Action::Show);start_left_item(left,"系统管理",48,Action::Manage);start_left_item(left,"显示桌面",88,Action::ShowDesktop);
    panel(left,8,128,173,1,0x808080);
    start_tab_item(left,"进程监视",136,1,false);start_tab_item(left,"网络状态",176,2,false);start_tab_item(left,"记录浏览",216,6,false);start_tab_item(left,"设备管理",256,4,false);
    start_tab_item(right,"系统概览",8,0,true);start_tab_item(right,"存储管理",48,3,true);start_tab_item(right,"设备管理",88,4,true);start_tab_item(right,"日志查看",128,5,true);
    panel(right,8,172,173,1,0x9ebfe5);
    auto footer=panel(menu,1,400,378,43,0x0062ea);lv_obj_set_style_bg_grad_color(footer,lv_color_hex(0x081bcb),0);lv_obj_set_style_bg_grad_dir(footer,LV_GRAD_DIR_VER,0);panel(footer,0,0,378,1,0x5db3ff);
    auto shutdown=button(footer,"关闭计算机",[](lv_event_t*){close_popup();terminal::show_power_dialog(false);});
    lv_obj_set_pos(shutdown,232,7);lv_obj_set_size(shutdown,140,28);xp::skin(shutdown,xp::Skin::Menu);lv_obj_set_style_text_color(shutdown,lv_color_white(),0);
    auto power=lv_image_create(shutdown);lv_image_set_src(power,&xp::assets::power);lv_obj_set_pos(power,4,2);lv_obj_align(lv_obj_get_child(shutdown,0),LV_ALIGN_LEFT_MID,34,0);
    lv_group_remove_obj(shutdown);lv_group_add_obj(menu_group,shutdown);lv_obj_add_event_cb(shutdown,[](lv_event_t* e){if(lv_event_get_key(e)==LV_KEY_ESC)close_popup();},LV_EVENT_KEY,nullptr);

}
void file_menu(lv_event_t*) {
    lv_area_t area;lv_obj_get_coords(toolbar,&area);auto menu=popup(area.x1,area.y1-1,186,143);
    menu_item(menu,"调试：手动检查",4,Action::Check);menu_item(menu,production?"停止自动检测":"开始自动检测",36,Action::Production);
    panel(menu,8,70,170,1,0x808080);menu_item(menu,"关闭",75,Action::Close);
}
void view_menu(lv_event_t*) {
    lv_area_t area;lv_obj_get_coords(toolbar,&area);auto menu=popup(area.x1+66,area.y1-1,186,74);
    menu_item(menu,maximized?"还原":"最大化",4,Action::Maximize);menu_item(menu,"最小化",36,Action::Minimize);
}
void update_clock(lv_timer_t*) {
    const auto now=std::time(nullptr);char value[16];std::strftime(value,sizeof(value),"%H:%M",std::localtime(&now));text(clock_label,value);
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
    text(lv_obj_get_child(login_button,0),terminal::is_administrator()?"管理员已登录":"管理员登录");
    if(inspection_busy){lv_obj_add_state(check_button,LV_STATE_DISABLED);lv_obj_add_state(production_button,LV_STATE_DISABLED);}else if(unconfirmed)lv_obj_remove_state(check_button,LV_STATE_DISABLED);
    try {
        json state;std::string frame_data,error,action_error;uint32_t age;
        {std::lock_guard<std::mutex> lock(inspection_mailbox);if(painted_revision==poll_revision && tick()-polled_at<1500)return;painted_revision=poll_revision;state=polled_state;frame_data=polled_frame;error=poll_error;action_error=command_error;age=tick()-polled_at;}
        if(!error.empty() || state.is_null() || age>1500){clear_picture();lv_obj_add_state(check_button,LV_STATE_DISABLED);if(unconfirmed && !inspection_busy)lv_obj_remove_state(check_button,LV_STATE_DISABLED);lv_obj_add_state(production_button,LV_STATE_DISABLED);throw std::runtime_error(error.empty()?"等待检测服务…":error);}
        lv_obj_set_style_bg_color(health_dot,lv_color_hex(0x2bdf50),0);
        paused=state.at("paused");production=state.value("production",false);
        text(lv_obj_get_child(production_button,0),production?"停止自动检测":"开始自动检测");
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
        const std::string selector="产品："+product_text+"    方案："+plan_text+"    模型："+model_text+"    批次："+(run.empty()?"尚未开始":run.substr(0,8)+(production?"（进行中）":"（已停止）"));
        if(plan_text!=selector_cache){selector_cache=plan_text;lv_dropdown_set_text(job_select,selector_cache.c_str());lv_obj_invalidate(job_select);}
        lv_obj_add_state(job_select,LV_STATE_DISABLED);
        text(job_label,selector);
        text(empty_label,!has_model?"未部署模型\n请在平台下发模型":!has_product?"未分配产品\n请在平台分配产品":"等待画面…");
        const bool has_run=state.contains("productionRunId") && state["productionRunId"].is_string() && !state["productionRunId"].get<std::string>().empty();
        const auto& counts=has_run?state.at("runCounts"):state.at("counts");
        const unsigned values[]={state.at(has_run?"runTotal":"total").get<unsigned>(),counts["PASS"].get<unsigned>(),counts["FAIL"].get<unsigned>(),counts["REVIEW"].get<unsigned>()+counts["ERROR"].get<unsigned>(),state["pendingSync"].get<unsigned>()};
        const char* names[]={has_run?"本批次原判":"本机累计原判","合格","不合格","待处理（含错误）","全机待同步"};
        for(unsigned i=0;i<5;++i)text(counters[i],std::string(names[i])+"   "+std::to_string(values[i]));
        std::string requirements=has_product?"当前方案要求":"请在 Web 配置并分配产品方案";
        if(has_product && state["product"].contains("checks"))for(const auto& check:state["product"]["checks"]) {
            requirements+='\n'+check.at("label").get<std::string>()+"："+std::to_string(check.at("min").get<unsigned>())+"–"+std::to_string(check.at("max").get<unsigned>())+" 个";
            if(check.contains("region")){const auto& r=check["region"];requirements+="；中心 X "+std::to_string(int(r["x"].get<double>()*100))+"–"+std::to_string(int((r["x"].get<double>()+r["width"].get<double>())*100))+"%，Y "+std::to_string(int(r["y"].get<double>()*100))+"–"+std::to_string(int((r["y"].get<double>()+r["height"].get<double>())*100))+"%";}
        }
        if(has_product)requirements+="\n\n"+state["product"].value("instructions",std::string());
        if(!state.at("last").is_null()) {
            const auto& last=state.at("last");std::string report="最近已保存单件：第 "+std::to_string(last.at("sequence").get<unsigned>())+" 件 · 机器原判 "+translated(last.at("result"))+"\n人工复核与最终结论请到 Web 检测记录处理";
            const std::string result=last.at("result");text(result_badge,translated(result));
            if(last.contains("reason"))report+='\n'+last.at("reason").get<std::string>();
            lv_obj_set_style_text_color(result_badge,lv_color_hex(result=="PASS"?0x22712b:result=="FAIL"?0xb3261e:0x925b00),0);
            if(last.contains("findings"))for(const auto& finding:last["findings"])report+='\n'+finding.at("label").get<std::string>()+"：确认 "+std::to_string(finding.at("count").get<unsigned>())+"，待确认 "+std::to_string(finding.at("uncertain").get<unsigned>())+"，要求 "+std::to_string(finding.at("min").get<unsigned>())+"–"+std::to_string(finding.at("max").get<unsigned>());
            text(result_label,report+"\n\n"+requirements);
        }else {text(result_label,requirements);text(result_badge,"待检查");lv_obj_set_style_text_color(result_badge,lv_color_black(),0);}
        text(error_label,action_error+(!action_error.empty()?"\n":"")+state.at("error").get<std::string>()+(!state.at("syncError").get<std::string>().empty()?"\n同步失败":""));
        if(frame_data.size()<4){clear_picture();text(fresh_label,"无图像");return;}
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
    }catch(const std::exception& e){clear_picture();lv_obj_set_style_bg_color(health_dot,lv_color_hex(0xd93025),0);text(fresh_label,"画面不可用");text(run_label,"服务连接异常");text(error_label,e.what());}
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
    ui_font=xp::pixel_font(argv[1],12);title_font=xp::pixel_font(argv[1],12,true);
    auto result_font=xp::pixel_font(argv[1],20,true);auto start_font=xp::pixel_font(argv[1],16,true);menu_title_font=start_font;
    auto root=lv_screen_active();lv_obj_set_style_text_font(root,ui_font,0);lv_obj_set_style_text_color(root,lv_color_black(),0);
    lv_obj_set_style_bg_color(root,lv_color_hex(xp::desktop),0);lv_obj_set_style_pad_all(root,0,0);lv_obj_remove_flag(root,LV_OBJ_FLAG_SCROLLABLE);
    auto shortcut=panel(root,16,16,80,76,xp::desktop);lv_obj_add_flag(shortcut,LV_OBJ_FLAG_CLICKABLE);
    xp::icon(shortcut,xp::Icon::Computer,32,24,3);
    auto shortcut_text=caption(shortcut,"视觉检测",0,49,80,0xffffff);lv_obj_set_style_text_align(shortcut_text,LV_TEXT_ALIGN_CENTER,0);
    lv_obj_add_event_cb(shortcut,dispatch,LV_EVENT_DOUBLE_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(Action::Show)));
    auto management_shortcut=panel(root,16,104,80,76,xp::desktop);lv_obj_add_flag(management_shortcut,LV_OBJ_FLAG_CLICKABLE);
    xp::icon(management_shortcut,xp::Icon::Control,32,24,3);
    auto management_caption=caption(management_shortcut,"系统管理",0,49,80,0xffffff);lv_obj_set_style_text_align(management_caption,LV_TEXT_ALIGN_CENTER,0);lv_obj_add_event_cb(management_shortcut,dispatch,LV_EVENT_DOUBLE_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(Action::Manage)));
    app_window=panel(root,20,16,1240,658,xp::face);xp::skin(app_window,xp::Skin::Window);lv_obj_add_flag(app_window,LV_OBJ_FLAG_CLICKABLE);
    titlebar=panel(app_window,0,0,1240,30,0x0053ee);xp::skin(titlebar,xp::Skin::Title);lv_obj_add_flag(titlebar,LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(titlebar,drag_window,LV_EVENT_PRESSED,nullptr);lv_obj_add_event_cb(titlebar,drag_window,LV_EVENT_PRESSING,nullptr);
    lv_obj_add_event_cb(titlebar,dispatch,LV_EVENT_DOUBLE_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(Action::Maximize)));
    xp::icon(titlebar,xp::Icon::Computer,16,6,7);
    auto title_shadow=caption(titlebar,"视觉检测",27,8,600,0x0f1089);lv_obj_set_style_text_font(title_shadow,title_font,0);
    auto title=caption(titlebar,"视觉检测",26,7,600,0xffffff);lv_obj_set_style_text_font(title,title_font,0);
    auto chrome=[&](Action action,xp::Skin skin){auto object=button(app_window,"",dispatch);lv_obj_set_size(object,21,21);xp::skin(object,skin);lv_obj_remove_event_cb(object,dispatch);lv_obj_add_event_cb(object,dispatch,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(action)));lv_group_remove_obj(object);return object;};
    min_button=chrome(Action::Minimize,xp::Skin::Minimize);max_button=chrome(Action::Maximize,xp::Skin::Maximize);close_button=chrome(Action::Close,xp::Skin::Close);
    auto menubar=panel(app_window,3,30,1234,22,xp::face);
    auto file=button(menubar,"文件(F)",file_menu);lv_obj_set_pos(file,0,0);lv_obj_set_size(file,66,23);lv_obj_set_style_bg_opa(file,LV_OPA_TRANSP,0);lv_obj_set_style_border_width(file,0,0);lv_group_remove_obj(file);
    auto view=button(menubar,"查看(V)",view_menu);lv_obj_set_pos(view,66,0);lv_obj_set_size(view,66,23);lv_obj_set_style_bg_opa(view,LV_OPA_TRANSP,0);lv_obj_set_style_border_width(view,0,0);lv_group_remove_obj(view);
    auto tools=button(menubar,"系统",[](lv_event_t*){perform(Action::Manage);});lv_obj_set_pos(tools,132,0);lv_obj_set_size(tools,66,23);lv_obj_set_style_bg_opa(tools,LV_OPA_TRANSP,0);lv_obj_set_style_border_width(tools,0,0);lv_group_remove_obj(tools);
    for(auto item:{file,view,tools}){xp::skin(item,xp::Skin::MenuBar);lv_obj_set_style_bg_opa(item,LV_OPA_COVER,LV_STATE_HOVERED);lv_obj_set_style_bg_color(item,lv_color_hex(0x316ac5),LV_STATE_HOVERED);lv_obj_set_style_text_color(item,lv_color_white(),LV_STATE_HOVERED);}
    toolbar=panel(app_window,3,52,1234,38,xp::face);lv_obj_set_style_border_width(toolbar,1,0);lv_obj_set_style_border_color(toolbar,lv_color_hex(0xd4d0c8),0);
    panel(toolbar,3,7,1,24,0xaca899);panel(toolbar,5,7,1,24,0xffffff);caption(toolbar,"配置",14,9,36);
    job_select=lv_dropdown_create(toolbar);lv_dropdown_set_options(job_select,"");lv_obj_set_pos(job_select,54,4);lv_obj_set_size(job_select,370,23);bevel(job_select);lv_obj_set_style_radius(job_select,0,0);
    lv_obj_set_style_bg_color(job_select,lv_color_white(),0);lv_obj_set_style_text_color(job_select,lv_color_black(),0);lv_obj_set_style_pad_ver(job_select,3,0);
    auto list=lv_dropdown_get_list(job_select);lv_obj_set_style_text_font(list,ui_font,0);lv_obj_set_style_text_color(list,lv_color_black(),0);lv_obj_set_style_bg_color(list,lv_color_white(),0);bevel(list);lv_obj_set_style_radius(list,0,0);
    lv_obj_set_style_bg_color(list,lv_color_hex(0x316ac5),LV_PART_SELECTED);lv_obj_set_style_text_color(list,lv_color_white(),LV_PART_SELECTED);lv_group_add_obj(focus_group,job_select);xp::combo(job_select,ui_font);
    production_button=button(toolbar,"开始自动检测",production_toggle);lv_obj_set_pos(production_button,436,4);lv_obj_set_size(production_button,120,23);
    panel(production_button,6,4,4,12,0x1548ad);panel(production_button,12,4,4,12,0x1548ad);
    lv_obj_align(lv_obj_get_child(production_button,0),LV_ALIGN_LEFT_MID,24,0);
    check_button=button(toolbar,"检查一件",check);lv_obj_set_pos(check_button,562,4);lv_obj_set_size(check_button,96,23);
    auto check_icon=panel(check_button,4,3,16,16,0xffffff);bevel(check_icon,0x7f9db9);
    static lv_point_precise_t check_mark[]={{0,4},{3,7},{9,0}};
    auto check_line=lv_line_create(check_button);lv_obj_set_pos(check_line,7,6);lv_obj_set_size(check_line,10,10);lv_line_set_points(check_line,check_mark,3);lv_obj_set_style_line_color(check_line,lv_color_hex(0x008d00),0);lv_obj_set_style_line_width(check_line,2,0);lv_obj_remove_flag(check_line,LV_OBJ_FLAG_CLICKABLE);
    lv_obj_align(lv_obj_get_child(check_button,0),LV_ALIGN_LEFT_MID,24,0);
    auto manage_jobs=button(toolbar,"系统管理",[](lv_event_t*){terminal::show_management_tab(0);});lv_obj_set_pos(manage_jobs,664,4);lv_obj_set_width(manage_jobs,96);
    login_button=button(toolbar,"管理员登录",[](lv_event_t*){terminal::show_management_tab(8);if(!terminal::is_administrator())terminal::show_login();});lv_obj_set_pos(login_button,770,4);lv_obj_set_width(login_button,124);
    job_label=caption(app_window,"模型：—    产品：—",14,100,1208);lv_label_set_long_mode(job_label,LV_LABEL_LONG_DOT);
    const char* initial[]={"本机累计原判   0","合格   0","不合格   0","待处理（含错误）   0","全机待同步   0"};
    const uint32_t colors[]={0x000000,0x006400,0x9c0000,0x805000,0x000000};
    for(unsigned i=0;i<5;++i){auto cell=panel(app_window,12+int(i)*243,124,239,28,0xece9d8);bevel(cell,0xaca899);lv_obj_set_style_radius(cell,0,0);counters[i]=caption(cell,initial[i],7,3,224,colors[i]);}
    workspace=panel(app_window,12,164,1216,464,0xece9d8);
    preview=panel(workspace,0,0,432,464,0xffffff);bevel(preview,0x7f9db9);lv_obj_set_style_radius(preview,0,0);caption(preview,"图像",8,2,416);
    image.header.magic=LV_IMAGE_HEADER_MAGIC;image.header.cf=LV_COLOR_FORMAT_RGB565;image.header.w=416;image.header.h=416;image.header.stride=416*2;image.data_size=pixels.size();image.data=pixels.data();
    picture=lv_image_create(preview);lv_obj_set_pos(picture,7,24);lv_image_set_src(picture,&image);
    empty_label=label(preview,"未部署模型\n请在平台下发模型并分配产品");lv_obj_set_pos(empty_label,7,200);lv_obj_set_width(empty_label,416);
    lv_obj_set_style_text_align(empty_label,LV_TEXT_ALIGN_CENTER,0);lv_obj_set_style_text_color(empty_label,lv_color_hex(0x9a9a9a),0);
    results=panel(workspace,448,0,768,464,0xffffff);bevel(results,0x7f9db9);lv_obj_set_style_radius(results,0,0);
    auto result_title=panel(results,0,0,766,24,0xece9d8);caption(result_title,"当前方案与单件结果",8,2,400);
    result_badge=caption(results,"—",14,34,738);lv_obj_set_style_text_font(result_badge,result_font,0);
    report=panel(results,10,72,744,362,0xffffff);vertical_scroll(report);result_label=caption(report,"",4,0,720);lv_obj_set_style_text_line_space(result_label,6,0);
    notices=panel(results,10,366,744,84,0xffffff);vertical_scroll(notices);error_label=caption(notices,"",4,0,720,0xb3261e);
    statusbar=panel(app_window,8,632,1224,22,0xece9d8);xp::skin(statusbar,xp::Skin::Status);
    fresh_label=caption(statusbar,"",16,1,790);run_label=caption(statusbar,"",1010,1,190);
    auto grip=panel(statusbar,0,0,14,16,0xece9d8);lv_obj_align(grip,LV_ALIGN_BOTTOM_RIGHT,-2,-2);
    panel(grip,10,2,2,2,0xb8b4a3);panel(grip,7,5,2,2,0xb8b4a3);panel(grip,4,8,2,2,0xb8b4a3);
    panel(grip,9,2,2,2,0xffffff);panel(grip,6,5,2,2,0xffffff);panel(grip,3,8,2,2,0xffffff);
    auto taskbar=panel(root,0,690,1280,30,0x245edb);xp::skin(taskbar,xp::Skin::Taskbar);
    start_button=button(taskbar,"",start_menu);lv_obj_set_pos(start_button,0,0);lv_obj_set_size(start_button,98,30);xp::skin(start_button,xp::Skin::Start);lv_group_remove_obj(start_button);
    auto start_shadow=caption(start_button,"应用",29,8,60,0x245b1b);lv_obj_set_style_text_font(start_shadow,start_font,0);
    auto start_title=caption(start_button,"应用",28,7,60,0xffffff);lv_obj_set_style_text_font(start_title,start_font,0);
    panel(taskbar,100,4,1,22,0x0c3997);
    auto show_desktop=button(taskbar,"",[](lv_event_t*){perform(Action::ShowDesktop);});
    lv_obj_set_pos(show_desktop,104,4);lv_obj_set_size(show_desktop,22,22);lv_group_remove_obj(show_desktop);
    xp::skin(show_desktop,xp::Skin::MenuBar);lv_obj_set_style_bg_opa(show_desktop,LV_OPA_TRANSP,0);lv_obj_set_style_border_width(show_desktop,0,0);lv_obj_set_style_shadow_width(show_desktop,0,0);
    lv_obj_set_style_bg_opa(show_desktop,LV_OPA_30,LV_STATE_HOVERED);lv_obj_set_style_bg_color(show_desktop,lv_color_white(),LV_STATE_HOVERED);
    xp::icon(show_desktop,xp::Icon::Computer,16,3,3);
    panel(taskbar,128,4,1,22,0x0c3997);
    task_button=button(taskbar,"视觉检测",task_click);lv_obj_set_pos(task_button,136,4);lv_obj_set_size(task_button,200,22);lv_group_remove_obj(task_button);lv_obj_set_style_border_color(task_button,lv_color_hex(0x0c3997),0);
    lv_obj_set_style_bg_color(task_button,lv_color_hex(0x3c80f3),0);lv_obj_set_style_bg_grad_color(task_button,lv_color_hex(0x2a65d3),0);lv_obj_set_style_text_color(task_button,lv_color_white(),0);
    lv_obj_set_style_bg_color(task_button,lv_color_hex(0x1951b9),LV_STATE_CHECKED);lv_obj_set_style_bg_grad_color(task_button,lv_color_hex(0x1648a5),LV_STATE_CHECKED);lv_obj_add_state(task_button,LV_STATE_CHECKED);
    lv_obj_set_style_bg_color(task_button,lv_color_hex(0x4a8ff5),LV_STATE_HOVERED);lv_obj_set_style_bg_grad_color(task_button,lv_color_hex(0x3a7be0),LV_STATE_HOVERED);
    lv_obj_set_style_bg_color(task_button,lv_color_hex(0x12408f),LV_STATE_PRESSED);lv_obj_set_style_bg_grad_color(task_button,lv_color_hex(0x0e3578),LV_STATE_PRESSED);
    lv_obj_align(lv_obj_get_child(task_button,0),LV_ALIGN_LEFT_MID,28,0);
    xp::skin(task_button,xp::Skin::Task);xp::icon(task_button,xp::Icon::Computer,16,6,3);
    auto tray=panel(taskbar,1176,0,104,30,0x0e96e9);xp::skin(tray,xp::Skin::Tray);
    auto socket=panel(tray,4,8,12,12,0x0b5fa5);bevel(socket,0x073f7a);health_dot=panel(socket,3,3,6,6,0x2bdf50);
    clock_label=caption(tray,"",20,4,76,0xffffff);lv_obj_set_style_text_align(clock_label,LV_TEXT_ALIGN_CENTER,0);update_clock(nullptr);lv_timer_create(update_clock,1000,nullptr);
    xp::bind_window(app_window,titlebar,task_button,min_button,max_button,close_button,focus_group);
    lv_obj_add_event_cb(app_window,[](lv_event_t*){terminal::blur_management();xp::activate_window(app_window);},LV_EVENT_PRESSED,nullptr);
    terminal::create_management(root,taskbar,ui_font,title_font,task_button,focus_group);
    xp::watch_activation(app_window);xp::activate_window(app_window);
    layout_window();lv_group_focus_obj(job_select);
    lv_evdev_discovery_start(discover,nullptr);
    engine.set_connection_timeout(0,300000);engine.set_read_timeout(0,600000);engine.set_write_timeout(0,600000);
    unconfirmed=!pending.empty();std::thread(inspection_worker).detach();lv_timer_create(refresh,16,nullptr);
    for(;;){lv_timer_handler();std::this_thread::sleep_for(std::chrono::milliseconds(5));}
}
