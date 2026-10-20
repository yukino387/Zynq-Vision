#include "management.h"
#include "xp_style.h"
#include "httplib.h"
#include "nlohmann/json.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <thread>
#include <vector>

using json=nlohmann::json;
namespace terminal { namespace {
lv_obj_t *window,*header,*tabs,*footer,*footer_panel,*task,*main_task,*minimize,*maximize,*close_button;
lv_obj_t *cpu_text,*memory_text,*machine_text,*health_text,*cpu_chart,*memory_chart,*cpu_bar,*memory_bar;
lv_chart_series_t *cpu_series,*memory_series;
lv_obj_t *process_table,*network_table,*network_text,*storage_table,*disk_select,*destination_select;
lv_obj_t *device_table,*log_scroll,*log_text,*history_table,*history_detail,*history_count,*history_filter,*job_table,*job_select,*package_select;
lv_obj_t *mount_action,*unmount_action,*export_records,*export_diagnostics,*verify_job,*import_job;
lv_obj_t *platform_text,*online_devices,*online_jobs,*online_table,*online_description,*bind_online_button,*fetch_job_button,*apply_job_button;
lv_obj_t *activate_job_button,*job_description,*account_text,*account_button,*chart_status,*history_next,*history_previous,*connection_select,*connect_action;
lv_obj_t *login_server=nullptr,*login_username=nullptr,*login_password=nullptr,*login_error=nullptr,*login_submit=nullptr;
lv_obj_t* modal=nullptr;
std::atomic<bool> administrator{false},command_busy{false};
bool login_pending=false,chart_paused=false,return_to_inspection=false;
std::string return_job,imported_job;
json session_info,job_rows;
double chart_sample=-1;
unsigned last_operation=0;
void login_dialog();
lv_group_t *group,*main_group;
lv_group_t* dialog_group=nullptr;
const lv_font_t *font,*heading_font;
std::atomic<bool> shown{false};
std::atomic<unsigned> selected_tab{0},history_page{0},filter_index{0};
std::mutex mailbox;
json received_system,received_page,queued_action,history_rows,received_auth;
std::string received_error;
unsigned revision=0,displayed_revision=0;
bool full=false;
int normal_x=42,normal_y=30;
lv_point_t last_drag{};
std::vector<std::string> disk_ids,destination_ids,job_ids,package_ids,connection_ids,online_device_ids,online_job_ids;
const char* filters[]={"","PASS","FAIL","REVIEW","ERROR"};

std::string number(double value,unsigned precision=1) {std::ostringstream out;out<<std::fixed<<std::setprecision(precision)<<value;return out.str();}
std::string value(const json& data,const char* key,const char* suffix="") {return data.contains(key) && data.at(key).is_number()?number(data.at(key).get<double>())+suffix:"—";}
std::string bytes(double size) {const char* units[]={"B","KiB","MiB","GiB"};unsigned unit=0;while(size>=1024 && unit<3){size/=1024;++unit;}return number(size,unit?1:0)+" "+units[unit];}
std::string decision(const std::string& result) {return result=="PASS"?"合格":result=="FAIL"?"不合格":result=="REVIEW"?"待复核":"错误";}
void text(lv_obj_t* object,const std::string& content) {lv_label_set_text(object,content.c_str());}
void enabled(lv_obj_t* object,bool state) {if(state)lv_obj_remove_state(object,LV_STATE_DISABLED);else lv_obj_add_state(object,LV_STATE_DISABLED);}
lv_obj_t* box(lv_obj_t* parent,int x,int y,int width,int height,uint32_t color=0xece9d8) {
    auto object=lv_obj_create(parent);lv_obj_remove_style_all(object);lv_obj_set_pos(object,x,y);lv_obj_set_size(object,width,height);
    lv_obj_set_style_bg_color(object,lv_color_hex(color),0);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,0);lv_obj_remove_flag(object,LV_OBJ_FLAG_SCROLLABLE);return object;
}
lv_obj_t* glyph(lv_obj_t* parent,int x,int y,int width,int height,uint32_t color=0xece9d8) {
    auto object=box(parent,x,y,width,height,color);lv_obj_remove_flag(object,LV_OBJ_FLAG_CLICKABLE);return object;
}
lv_obj_t* label(lv_obj_t* parent,const char* content,int x,int y,int width) {
    auto object=lv_label_create(parent);lv_obj_set_style_text_font(object,font,0);lv_obj_set_pos(object,x,y);lv_obj_set_width(object,width);lv_label_set_long_mode(object,LV_LABEL_LONG_WRAP);text(object,content);return object;
}
lv_obj_t* button(lv_obj_t* parent,const char* content,int x,int y,int width,lv_event_cb_t callback,void* data=nullptr) {
    auto object=lv_button_create(parent);lv_obj_set_pos(object,x,y);lv_obj_set_size(object,width,23);xp::skin(object,xp::Skin::Button);
    lv_obj_set_style_text_color(object,lv_color_black(),0);lv_obj_set_style_text_font(object,font,0);lv_obj_set_style_text_color(object,lv_color_hex(0xa1a192),LV_STATE_DISABLED);
    auto title=lv_label_create(object);text(title,content);lv_obj_center(title);lv_obj_add_event_cb(object,callback,LV_EVENT_CLICKED,data);return object;
}
void keyboard(lv_group_t* target) {for(auto input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,target);}
void layout() {
    const int width=full?1280:1196,height=full?690:644;
    lv_obj_set_pos(window,full?0:normal_x,full?0:normal_y);lv_obj_set_size(window,width,height);lv_obj_set_width(header,width);
    lv_obj_set_pos(minimize,width-72,5);lv_obj_set_pos(maximize,width-49,5);lv_obj_set_pos(close_button,width-26,5);xp::skin(maximize,full?xp::Skin::Restore:xp::Skin::Maximize);
    lv_obj_set_size(tabs,width-16,height-78);lv_obj_set_pos(footer_panel,12,height-34);lv_obj_set_size(footer_panel,width-24,26);
    lv_obj_set_pos(footer,6,4);lv_obj_set_width(footer,width-380);lv_obj_set_pos(account_text,width-366,6);lv_obj_set_pos(account_button,width-134,2);
}
void hide(bool closed) {shown=false;xp::deactivate_window(window);lv_obj_add_flag(window,LV_OBJ_FLAG_HIDDEN);lv_obj_remove_state(task,LV_STATE_CHECKED);if(closed)lv_obj_add_flag(task,LV_OBJ_FLAG_HIDDEN);keyboard(main_group);}
void close_modal() {if(login_pending)return;if(modal){lv_obj_delete(modal);modal=nullptr;login_server=login_username=login_password=login_error=login_submit=nullptr;keyboard(lv_obj_has_state(task,LV_STATE_CHECKED)?group:main_group);lv_group_delete(dialog_group);dialog_group=nullptr;}}
void queue(const std::string& name,json payload=json::object()) {
    if(name!="sync" && !administrator){login_dialog();return;}
    {std::lock_guard<std::mutex> lock(mailbox);if(command_busy || !queued_action.is_null()){text(footer,"操作正在提交");return;}queued_action={{"action",name},{"payload",payload}};command_busy=true;if(name=="activate" || name=="online_apply")return_job=payload.at("id");}
    text(footer,"正在提交…");
}
void power_dialog(bool reboot) {
    if(!administrator){login_dialog();return;}
    close_modal();dialog_group=lv_group_create();lv_group_set_default(dialog_group);modal=box(lv_layer_top(),0,0,1280,720,0x000000);lv_obj_set_style_bg_opa(modal,LV_OPA_30,0);lv_obj_set_style_text_font(modal,font,0);
    auto dialog=box(modal,430,260,420,160);xp::skin(dialog,xp::Skin::Window);
    auto title=box(dialog,0,0,420,30,0x0054e3);xp::skin(title,xp::Skin::Title);auto caption=label(title,"系统",10,7,300);lv_obj_set_style_text_color(caption,lv_color_white(),0);
    label(dialog,reboot?"确实要重新启动巡检终端吗？":"确实要关闭巡检终端吗？",26,55,370);
    button(dialog,reboot?"重新启动":"关机",190,112,96,[](lv_event_t* e){const bool restart=reinterpret_cast<uintptr_t>(lv_event_get_user_data(e))==1;close_modal();queue(restart?"reboot":"poweroff",{{"confirmed",true}});},reinterpret_cast<void*>(reboot?1:2));
    auto cancel=button(dialog,"取消",300,112,88,[](lv_event_t*){close_modal();});lv_group_set_default(main_group);keyboard(dialog_group);lv_group_focus_obj(cancel);lv_obj_add_event_cb(cancel,[](lv_event_t* e){if(lv_event_get_key(e)==LV_KEY_ESC)close_modal();},LV_EVENT_KEY,nullptr);
}
void confirm_power(lv_event_t* event) {power_dialog(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event))==1);}
void export_action(lv_event_t* event) {
    const unsigned index=lv_dropdown_get_selected(destination_select);if(index>=destination_ids.size()){text(footer,"未选择 U 盘目录");return;}
    queue(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event))?"diagnostics":"export",{{"path",destination_ids[index]}});
}
lv_obj_t* dropdown(lv_obj_t* parent,int x,int y,int width) {
    auto object=lv_dropdown_create(parent);lv_obj_set_pos(object,x,y);lv_obj_set_size(object,width,23);lv_dropdown_set_options(object,"");xp::combo(object,font);return object;
}
void options(lv_obj_t* object,const std::vector<std::string>& names,const std::vector<std::string>& ids,std::vector<std::string>& cache) {
    std::string content;for(const auto& name:names){if(!content.empty())content+='\n';content+=name;}
    if(content!=lv_dropdown_get_options(object) || ids!=cache){const unsigned previous=lv_dropdown_get_selected(object);const std::string selected=previous<cache.size()?cache[previous]:"";cache=ids;lv_dropdown_set_options(object,content.c_str());const auto found=std::find(cache.begin(),cache.end(),selected);if(found!=cache.end())lv_dropdown_set_selected(object,found-cache.begin());}
}
lv_obj_t* table(lv_obj_t* parent,int x,int y,int height,const std::vector<int>& widths) {
    auto object=lv_table_create(parent);lv_obj_set_pos(object,x,y);lv_obj_set_size(object,1148,height);lv_obj_set_style_radius(object,0,0);lv_obj_set_style_border_color(object,lv_color_hex(0x7f9db9),0);
    lv_obj_set_style_text_font(object,font,LV_PART_ITEMS);lv_obj_set_style_pad_ver(object,5,LV_PART_ITEMS);lv_obj_set_style_pad_hor(object,8,LV_PART_ITEMS);lv_obj_set_style_bg_color(object,lv_color_white(),LV_PART_ITEMS);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x9cb8df),LV_PART_SCROLLBAR);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,LV_PART_SCROLLBAR);lv_obj_set_style_width(object,8,LV_PART_SCROLLBAR);lv_obj_set_style_radius(object,2,LV_PART_SCROLLBAR);
    xp::table(object);lv_table_set_column_count(object,widths.size());for(unsigned i=0;i<widths.size();++i)lv_table_set_column_width(object,i,widths[i]);return object;
}
void rows(lv_obj_t* object,const std::vector<std::vector<std::string>>& values) {
    if(lv_table_get_row_count(object)!=values.size())lv_table_set_row_count(object,values.size());
    for(unsigned r=0;r<values.size();++r)for(unsigned c=0;c<values[r].size();++c)if(values[r][c]!=lv_table_get_cell_value(object,r,c))lv_table_set_cell_value(object,r,c,values[r][c].c_str());
}
void login_dialog() {
    if(command_busy)return;
    close_modal();dialog_group=lv_group_create();lv_group_set_default(dialog_group);
    modal=box(lv_layer_top(),0,0,1280,720,0x000000);lv_obj_set_style_bg_opa(modal,LV_OPA_30,0);
    auto dialog=box(modal,390,185,500,350);xp::skin(dialog,xp::Skin::Window);
    auto title=box(dialog,0,0,500,30,0x0054e3);xp::skin(title,xp::Skin::Title);
    auto caption=label(title,"登录到 CNN Studio",10,7,470);lv_obj_set_style_text_color(caption,lv_color_white(),0);
    label(dialog,"使用平台管理员账号管理终端。",26,49,448);
    auto field=[&](int y,int limit,bool secret){auto object=lv_textarea_create(dialog);lv_obj_set_pos(object,112,y);lv_obj_set_size(object,356,26);lv_obj_set_style_text_font(object,font,0);lv_obj_set_style_pad_all(object,4,0);lv_obj_set_style_radius(object,0,0);lv_obj_set_style_border_width(object,1,0);lv_obj_set_style_border_color(object,lv_color_hex(0x7f9db9),0);lv_textarea_set_one_line(object,true);lv_textarea_set_max_length(object,limit);lv_textarea_set_password_mode(object,secret);lv_textarea_set_password_show_time(object,0);lv_textarea_set_text(object,"");return object;};
    label(dialog,"平台地址：",26,91,80);login_server=field(84,200,false);lv_textarea_set_text(login_server,session_info.value("server",std::string()).c_str());lv_textarea_set_placeholder_text(login_server,"http://平台 IP:端口");if(session_info.value("configured",false))enabled(login_server,false);
    label(dialog,"用户名：",26,135,80);login_username=field(128,80,false);
    label(dialog,"密  码：",26,175,80);login_password=field(168,200,true);
    auto show=lv_checkbox_create(dialog);lv_obj_set_pos(show,112,207);lv_obj_set_style_text_font(show,font,0);lv_checkbox_set_text(show,"显示密码");lv_obj_set_style_radius(show,1,LV_PART_INDICATOR);lv_obj_set_style_size(show,13,13,LV_PART_INDICATOR);lv_obj_set_style_border_width(show,1,LV_PART_INDICATOR);lv_obj_set_style_border_color(show,lv_color_hex(0x1c5180),LV_PART_INDICATOR);lv_obj_set_style_bg_color(show,lv_color_white(),LV_PART_INDICATOR);lv_obj_set_style_bg_color(show,lv_color_white(),LV_PART_INDICATOR|LV_STATE_CHECKED);lv_obj_set_style_text_color(show,lv_color_hex(0x228125),LV_PART_INDICATOR|LV_STATE_CHECKED);lv_obj_add_event_cb(show,[](lv_event_t* e){if(login_password)lv_textarea_set_password_mode(login_password,!lv_obj_has_state(lv_event_get_target_obj(e),LV_STATE_CHECKED));},LV_EVENT_VALUE_CHANGED,nullptr);
    login_error=label(dialog,"账号与密码在平台维护，板端不保存密码。",26,249,448);lv_obj_set_style_text_color(login_error,lv_color_hex(0x555555),0);
    login_submit=button(dialog,"登录",270,306,94,[](lv_event_t*){
        const std::string username=lv_textarea_get_text(login_username),password=lv_textarea_get_text(login_password);
        if(username.empty() || password.empty()){text(login_error,"请输入平台账号和密码");return;}
        {std::lock_guard<std::mutex> lock(mailbox);if(command_busy)return;queued_action={{"auth","/auth/login"},{"payload",{{"server",lv_textarea_get_text(login_server)},{"username",username},{"password",password}}}};command_busy=true;}
        lv_textarea_set_text(login_password,"");login_pending=true;enabled(login_submit,false);text(login_error,"正在验证平台账号…");
    });
    lv_obj_add_event_cb(login_username,[](lv_event_t*){lv_group_focus_obj(login_password);},LV_EVENT_READY,nullptr);
    lv_obj_add_event_cb(login_password,[](lv_event_t*){if(!login_pending)lv_obj_send_event(login_submit,LV_EVENT_CLICKED,nullptr);},LV_EVENT_READY,nullptr);
    button(dialog,"取消",376,306,92,[](lv_event_t*){close_modal();});
    lv_obj_add_event_cb(modal,[](lv_event_t* e){if(lv_event_get_key(e)==LV_KEY_ESC)close_modal();},LV_EVENT_KEY,nullptr);
    for(auto object:{login_server,login_username,login_password,show,login_submit})lv_obj_add_flag(object,LV_OBJ_FLAG_EVENT_BUBBLE);
    auto cancel=lv_obj_get_child(dialog,lv_obj_get_child_count(dialog)-1);lv_obj_add_flag(cancel,LV_OBJ_FLAG_EVENT_BUBBLE);lv_obj_add_flag(dialog,LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_group_set_default(main_group);keyboard(dialog_group);lv_group_focus_obj(session_info.value("configured",false)?login_username:login_server);
}
void worker() {
    httplib::Client client("http://127.0.0.1:8878");client.set_connection_timeout(0,500000);client.set_read_timeout(20,0);client.set_write_timeout(3,0);
    std::string token;
    for(;;){
        json command;{std::lock_guard<std::mutex> lock(mailbox);command=std::move(queued_action);queued_action=nullptr;}
        try {
            std::string error;json system,page,auth;
            client.set_bearer_token_auth(token);
            if(!command.is_null()){
                const bool authentication=command.contains("auth");
                auto reply=client.Post(authentication?command.at("auth").get<std::string>():"/action",authentication?command.at("payload").dump():command.dump(),"application/json");
                if(!reply)throw std::runtime_error("系统管理服务不可用，请核对操作结果");
                auth=authentication?json::parse(reply->body):json();
                if(reply->status!=(authentication?200:202))error=json::parse(reply->body).value("error","操作失败");
                if(authentication && reply->status==200){token=auth.value("token",std::string());auth.erase("token");client.set_bearer_token_auth(token);auth["success"]=true;}
            }
            const auto reply=client.Get("/system");if(!reply || reply->status!=200)throw std::runtime_error("系统管理服务不可用");system=json::parse(reply->body);
            if(shown){
                const auto tab=selected_tab.load();std::string path;
                if(tab==3)path="/storage";else if(tab==4)path="/devices";else if(tab==5)path="/logs";else if(tab==6)path="/records?page="+std::to_string(history_page.load())+"&result="+filters[filter_index.load()];else if(tab==7)path="/jobs";else if(tab==8)path="/platform";
                if(!path.empty()){const auto detail=client.Get(path);if(!detail || detail->status!=200)error=detail?json::parse(detail->body).value("error","读取失败"):"系统管理服务不可用";else page=json::parse(detail->body);}
                system["tab"]=tab;
            }
            {std::lock_guard<std::mutex> lock(mailbox);received_system=std::move(system);received_page=std::move(page);received_auth=std::move(auth);received_error=error;if(!command.is_null())command_busy=false;++revision;}
        }catch(const std::exception& e){command_busy=false;std::lock_guard<std::mutex> lock(mailbox);received_error=e.what();received_system=nullptr;received_page=nullptr;received_auth=nullptr;++revision;}
        for(unsigned i=0;i<10;++i){std::this_thread::sleep_for(std::chrono::milliseconds(100));std::lock_guard<std::mutex> lock(mailbox);if(!queued_action.is_null())break;}
    }
}
void render(lv_timer_t*) {
    json system,page,auth;std::string error;
    {std::lock_guard<std::mutex> lock(mailbox);if(displayed_revision==revision)return;displayed_revision=revision;system=received_system;page=received_page;auth=received_auth;error=received_error;}
    try {
        session_info=system.is_object()?system.value("session",json::object()):json::object();administrator=session_info.value("role",std::string())=="admin";
        text(account_text,administrator?session_info.value("username",std::string())+" · 管理员":"操作员 · 仅执行已启用作业");
        text(lv_obj_get_child(account_button,0),administrator?"注销":"管理员登录");
        for(auto object:{mount_action,unmount_action,export_records,export_diagnostics,verify_job,import_job,activate_job_button,connect_action,bind_online_button,fetch_job_button,apply_job_button})enabled(object,false);
        if(login_pending && !command_busy){login_pending=false;if(login_error){if(auth.is_object() && auth.value("success",false) && administrator)close_modal();else{text(login_error,error.empty()?session_info.value("message",std::string("登录失败")):error);lv_obj_set_style_text_color(login_error,lv_color_hex(0xb3261e),0);enabled(login_submit,true);lv_group_focus_obj(login_password);}}}
        if(!error.empty()){text(footer,error);lv_obj_set_style_text_color(footer,lv_color_hex(0xb3261e),0);return;}if(system.is_null())return;
        const auto operation=system.value("operation",json::object());
        if(!operation.value("busy",false) && operation.value("id",0u)!=last_operation){last_operation=operation.value("id",0u);if(operation.value("error",std::string()).empty()){if(operation.value("action",std::string())=="import" || operation.value("action",std::string())=="fetch_job"){imported_job=operation.value("jobId",std::string());if(operation.value("action",std::string())=="fetch_job")show_management_tab(7);}if((operation.value("action",std::string())=="activate" || operation.value("action",std::string())=="online_apply") && !return_job.empty() && return_job==operation.value("jobId",std::string())){return_job.clear();return_to_inspection=true;hide(false);}}}
        if(!shown)return;
        const auto& op=system.at("operation");const std::string operation_error=op.value("error",std::string()),operation_result=op.value("result",std::string());
        text(footer,op.value("busy",false)?operation_result.empty()?"正在执行…":operation_result:!operation_error.empty()?operation_error:operation_result);
        if(operation_error.empty() && operation_result.empty() && !op.value("busy",false))text(footer,"就绪");
        lv_obj_set_style_text_color(footer,lv_color_hex(!operation_error.empty()?0xb3261e:op.value("busy",false)?0x000080:!operation_result.empty()?0x22712b:0x000000),0);
        if(!session_info.value("message",std::string()).empty() && !op.value("busy",false)){text(footer,session_info.at("message"));lv_obj_set_style_text_color(footer,lv_color_hex(0x925b00),0);}
        const auto link=system.value("platform",json::object());
        text(platform_text,"平台："+session_info.value("server",std::string("未设置"))+"    设备："+link.value("deviceId",std::string())+"\n"+(link.value("online",false)?"已连接 · 状态与记录自动同步":"离线 · 已启用作业可继续检测")+"    "+link.value("error",std::string())+"\n最近状态回执："+(link.contains("lastSuccess") && link["lastSuccess"].is_string()?link["lastSuccess"].get<std::string>():"尚未收到"));
        if(!system.contains("cpus"))return;
        const auto memory=system.at("memory");const double total=memory.value("MemTotal",0.0),available=memory.value("MemAvailable",0.0);const double used=total-available;
        const auto& cpus=system.at("cpus");const double cpu=!cpus.empty() && cpus[0]["percent"].is_number()?cpus[0]["percent"].get<double>():-1;
        text(cpu_text,"CPU   "+(cpu<0?"—":number(cpu)+" %"));text(memory_text,"内存   "+bytes(used)+" / "+bytes(total)+(total>0?"   ("+number(used/total*100)+" %)":""));
        if(cpu>=0)lv_bar_set_value(cpu_bar,int(cpu),LV_ANIM_OFF);
        if(total>0)lv_bar_set_value(memory_bar,int(100*used/total),LV_ANIM_OFF);
        const auto& history=system.value("history",json::object());
        const double sample=system.value("sampleTime",0.0);
        if(!chart_paused && sample!=chart_sample){
            chart_sample=sample;
            const auto update=[&](const char* key,lv_obj_t* chart,lv_chart_series_t* series){
                lv_chart_set_all_values(chart,series,LV_CHART_POINT_NONE);
                if(!history.contains(key) || !history[key].is_array())return;
                const auto& values=history[key];const size_t count=std::min<size_t>(60,values.size());
                for(size_t i=0;i<count;++i){const auto& value=values[values.size()-count+i];if(value.is_number())lv_chart_set_series_value_by_id(chart,series,60-count+i,int32_t(std::lround(std::clamp(value.get<double>(),0.0,100.0))));}
                lv_chart_refresh(chart);
            };
            update("cpu",cpu_chart,cpu_series);update("memory",memory_chart,memory_series);
        }
        text(chart_status,chart_paused?"图表已暂停 · 后台持续采样":system.contains("samplingError")?"采样异常 · 空白为缺失数据":"每秒采样 · 空白为缺失数据");
        const unsigned uptime=system.value("uptime",0.0);std::string cpu_detail;
        for(size_t i=1;i<cpus.size();++i)cpu_detail+=cpus[i].at("name").get<std::string>()+"  "+value(cpus[i],"percent"," %")+"    ";
        text(machine_text,cpu_detail+"\n运行时间  "+std::to_string(uptime/86400)+" 天 "+std::to_string(uptime/3600%24)+":"+(uptime/60%60<10?"0":"")+std::to_string(uptime/60%60)+"    温度  "+value(system,"temperatureC"," °C")+"    进程  "+std::to_string(system.at("processCount").get<unsigned>())+"\n内核  "+system.at("kernel").get<std::string>()+"    CPU  "+(system.at("frequencyMHz").empty()?"—":number(system["frequencyMHz"][0].get<double>(),0)+" MHz"));
        const auto& inspection=system.at("inspection");std::string services;
        for(const auto* name:{"vision-engine","vision-panel","vision-manager"}){const bool running=!system["services"][name].empty();services+=std::string(running?"#22712b ":"#b3261e ")+name+(running?" 运行#":" 停止#")+"    ";}
        std::string detection_error=inspection.value("error",std::string());std::replace(detection_error.begin(),detection_error.end(),'#','*');
        const std::string detection=inspection.value("online",false)?(detection_error.empty()?"#22712b 在线#":"#925b00 异常#  "+detection_error):"#b3261e 离线#";
        text(health_text,services+"\n检测帧率  "+value(system,"inferenceFps"," FPS")+"    最近耗时  "+(inspection.contains("diagnostics")?value(inspection["diagnostics"],"lastCaptureMs"," ms"):"—")+"\n检测服务  "+detection+"    待同步  "+(inspection.contains("pendingSync")?std::to_string(inspection.at("pendingSync").get<unsigned>()):"—"));
        const unsigned tab=system.value("tab",0u);if(tab!=selected_tab.load())return;
        if(tab==1){std::vector<std::vector<std::string>> data={{"PID","进程","CPU %","内存","状态"}};for(const auto& p:system["processes"])data.push_back({std::to_string(p["pid"].get<unsigned>()),p["name"],value(p,"cpu"),bytes(p["memory"].get<double>()),p["state"]});rows(process_table,data);}
        else if(tab==2){std::vector<std::vector<std::string>> data={{"接口","IPv4","链路","Mbps","接收 / 秒","发送 / 秒","接收总量","发送总量","错误"}};for(const auto& p:system["network"])data.push_back({p["name"],p["address"],p["carrier"].get<bool>()?"已连接":"断开",p["speedMbps"],p["rxRate"].is_number()?bytes(p["rxRate"].get<double>()):"—",p["txRate"].is_number()?bytes(p["txRate"].get<double>()):"—",bytes(p["received"].get<double>()),bytes(p["sent"].get<double>()),std::to_string(p["rxErrors"].get<unsigned>()+p["txErrors"].get<unsigned>())});rows(network_table,data);std::string addresses;for(const auto& p:system["network"])addresses+=p["name"].get<std::string>()+"    "+p["address"].get<std::string>()+"    "+p["netmask"].get<std::string>()+"\n";text(network_text,addresses);}
        else if(tab==3 && !page.is_null()){
            std::vector<std::vector<std::string>> data={{"设备","挂载点","格式","总容量","已用","可用"}};for(const auto& p:page["mounts"])data.push_back({p["device"],p["path"],p["type"],bytes(p["total"].get<double>()),bytes(p["used"].get<double>()),bytes(p["available"].get<double>())});rows(storage_table,data);
            std::vector<std::string> names,ids,destinations;for(const auto& p:page["usb"]){ids.push_back(p["device"]);names.push_back(p["device"].get<std::string>()+"   "+bytes(p["bytes"].get<double>())+"   "+p["mounted"].get<std::string>());if(!p["mounted"].get<std::string>().empty())destinations.push_back(p["mounted"]);}options(disk_select,names,ids,disk_ids);options(destination_select,destinations,destinations,destination_ids);
            enabled(mount_action,administrator && !op.value("busy",false) && !disk_ids.empty());enabled(unmount_action,administrator && !op.value("busy",false) && !destination_ids.empty());enabled(export_records,administrator && !op.value("busy",false) && !destination_ids.empty());enabled(export_diagnostics,administrator && !op.value("busy",false) && !destination_ids.empty());
        }else if(tab==4 && !page.is_null()){
            std::vector<std::vector<std::string>> data={{"类别","接口","状态 / 名称"}};
            for(const auto* name:{"vision_accel","vision_fb"})data.push_back({"驱动",name,page["drivers"][name].get<bool>()?"已加载":"未加载"});
            data.push_back({"HDMI","fb0",page["framebuffer"].value("name","")+"   "+page["framebuffer"].value("visibleSize","")+"   "+page["framebuffer"].value("bitsPerPixel","")+" bpp"});
            if(page.contains("camera")){const auto& camera=page["camera"];data.push_back({"摄像头","OV5640",!camera.value("error",std::string()).empty()?camera.at("error").get<std::string>():camera.value("initialized",false)?camera.value("fresh",false)?"采集中":"已初始化":"未初始化"});}
            for(const auto& p:page["mmc"])data.push_back({"SD",p["name"],p["cid"]});
            for(const auto& p:page["usb"])data.push_back({"USB",p["port"],p["name"].get<std::string>()+"  "+p["vendor"].get<std::string>()+":"+p["productId"].get<std::string>()+"  "+p["speedMbps"].get<std::string>()+" Mbps"});
            for(const auto& p:page["inputs"])data.push_back({"输入接口",p["node"],p["name"]});rows(device_table,data);
        }else if(tab==5 && !page.is_null()){
            const bool follow=lv_obj_get_scroll_bottom(log_scroll)<=2;
            text(log_text,page.at("text"));lv_obj_update_layout(log_scroll);
            if(follow)lv_obj_scroll_to_y(log_scroll,lv_obj_get_scroll_y(log_scroll)+std::max(0,lv_obj_get_scroll_bottom(log_scroll)),LV_ANIM_OFF);
        }
        else if(tab==6 && !page.is_null()){
            const unsigned total=page.value("total",0u),last_page=total?(total-1)/20:0;enabled(history_previous,history_page>0);enabled(history_next,history_page<last_page);if(history_page>last_page){history_page=last_page;return;}
            history_rows=page["items"];std::vector<std::vector<std::string>> data={{"序号","生产批次 / 单件","机器原判","帧号","证据同步","产品方案 / 模型"}};
            for(const auto& p:history_rows)data.push_back({p.contains("sequence")?std::to_string(p["sequence"].get<unsigned>()):"—",p.value("productionRunId",std::string("单件检查")),decision(p.value("result","ERROR")),p.contains("frameId")?std::to_string(p["frameId"].get<unsigned>()):"—",p.value("synced",false)?"已同步":"待同步",p.value("planName",std::string())+" / V"+std::to_string(p.value("planVersion",0))+" · "+p.value("modelVersion",std::string())});rows(history_table,data);text(history_count,"第 "+std::to_string(history_page+1)+" 页    共 "+std::to_string(page["total"].get<unsigned>())+" 条");
        }else if(tab==7 && !page.is_null()){
            job_rows=page["items"];std::vector<std::vector<std::string>> data={{"状态 / 作业编号","名称","模型版本","大小"}};std::vector<std::string> names,ids,pnames,pids;
            for(const auto& p:page["items"]){data.push_back({(p.value("active",false)?"[当前] ":!p.value("ready",false)?"[不可用] ":"[待启用] ")+p.at("id").get<std::string>(),p["name"],p.value("model",p.value("error","")),bytes(p.value("bytes",0.0))});names.push_back(p["name"]);ids.push_back(p["id"]);}rows(job_table,data);options(job_select,names,ids,job_ids);
            for(const auto& p:page["packages"]){pnames.push_back(p["name"]);pids.push_back(p["path"]);}options(package_select,pnames,pids,package_ids);
            if(!imported_job.empty()){const auto found=std::find(job_ids.begin(),job_ids.end(),imported_job);if(found!=job_ids.end()){lv_dropdown_set_selected(job_select,found-job_ids.begin());imported_job.clear();}}
            const unsigned chosen=lv_dropdown_get_selected(job_select);const bool ready=chosen<job_rows.size() && job_rows[chosen].value("ready",false);
            const bool allowed=administrator && !op.value("busy",false) && !command_busy;
            std::vector<std::string> cnames,cids;for(const auto& item:page.value("connections",json::array())){cnames.push_back(item["name"]);cids.push_back(item["path"]);}options(connection_select,cnames,cids,connection_ids);enabled(connect_action,allowed && !connection_ids.empty());
            enabled(verify_job,allowed && !job_ids.empty());enabled(import_job,allowed && !package_ids.empty());enabled(activate_job_button,allowed && ready);
            std::string description=chosen<job_rows.size()?"要求："+job_rows[chosen].value("instructions",std::string())+"    "+job_rows[chosen].value("error",std::string()):"模型和产品由平台下发；开始/停止自动检测与检查一件请在检测台操作。";
            text(job_description,description+(!administrator?"\n请使用平台管理员账号登录后管理作业。":""));
        }
        if(tab==8 && !page.is_null()){
            std::vector<std::string> dnames,dids,jnames,jids;std::vector<std::vector<std::string>> data={{"作业编号","名称","模型版本","目标件数"}};
            for(const auto& item:page["devices"]){dids.push_back(item["id"]);dnames.push_back(item["name"].get<std::string>()+"  ["+item["serialNumber"].get<std::string>()+"]");}options(online_devices,dnames,dids,online_device_ids);
            const std::string bound=page.value("deviceId",std::string());const auto found=std::find(dids.begin(),dids.end(),bound);if(found!=dids.end())lv_dropdown_set_selected(online_devices,found-dids.begin());
            if(!bound.empty())enabled(online_devices,false);else enabled(online_devices,administrator);
            for(const auto& item:page["jobs"]){jids.push_back(item["id"]);jnames.push_back(item["name"]);data.push_back({item["id"],item["name"],item["model"],std::to_string(item["target"].get<unsigned>())});}rows(online_table,data);options(online_jobs,jnames,jids,online_job_ids);
            const bool allowed=administrator && !op.value("busy",false) && !command_busy;
            enabled(bind_online_button,allowed && !dids.empty());enabled(fetch_job_button,allowed && !jids.empty());enabled(apply_job_button,allowed && !jids.empty());
            const auto selected=lv_dropdown_get_selected(online_jobs);text(online_description,selected<page["jobs"].size()?"作业要求："+page["jobs"][selected].value("instructions",std::string()):administrator?"暂无待处理作业；模型和产品请在设备配置中下发。":"请使用平台管理员账号登录并绑定设备。");
        }

    }catch(const std::exception& e){text(footer,std::string("数据读取失败：")+e.what());}
}
} // namespace

bool is_administrator(){return administrator;}
void show_login(){login_dialog();}
bool take_inspection_focus(){const bool requested=return_to_inspection;return_to_inspection=false;return requested;}
void show_management() {shown=true;lv_obj_remove_flag(window,LV_OBJ_FLAG_HIDDEN);xp::activate_window(window);lv_obj_remove_flag(task,LV_OBJ_FLAG_HIDDEN);lv_obj_add_state(task,LV_STATE_CHECKED);lv_obj_remove_state(main_task,LV_STATE_CHECKED);keyboard(group);lv_group_focus_obj(lv_tabview_get_tab_button(tabs,selected_tab));}
void show_management_tab(unsigned tab) {selected_tab=tab;show_management();lv_tabview_set_active(tabs,tab,LV_ANIM_OFF);}
void request_job_activation(const std::string& id){if(!administrator){show_management_tab(7);login_dialog();return;}show_management_tab(7);queue("activate",{{"id",id}});}
void show_power_dialog(bool reboot) {power_dialog(reboot);}
void hide_management() {hide(false);}
void blur_management() {xp::deactivate_window(window);lv_obj_remove_state(task,LV_STATE_CHECKED);keyboard(main_group);}
lv_group_t* management_input_group() {return dialog_group?dialog_group:lv_obj_has_state(task,LV_STATE_CHECKED)?group:nullptr;}

void create_management(lv_obj_t* root,lv_obj_t* taskbar,const lv_font_t* ui_font,const lv_font_t* title_font,lv_obj_t* inspection_task,lv_group_t* inspection_group) {
    font=ui_font;heading_font=title_font;main_task=inspection_task;main_group=inspection_group;group=lv_group_create();lv_group_set_default(group);
    window=box(root,42,30,1196,644);lv_obj_set_style_text_font(window,font,0);lv_obj_set_style_text_color(window,lv_color_black(),0);xp::skin(window,xp::Skin::Window);
    header=box(window,0,0,1196,30,0x0053ee);xp::skin(header,xp::Skin::Title);xp::icon(header,xp::Icon::Control,16,6,7);
    auto heading_shadow=label(header,"系统管理",27,8,700);lv_obj_set_style_text_font(heading_shadow,heading_font,0);lv_obj_set_style_text_color(heading_shadow,lv_color_hex(0x0f1089),0);
    auto heading=label(header,"系统管理",26,7,700);lv_obj_set_style_text_font(heading,heading_font,0);lv_obj_set_style_text_color(heading,lv_color_white(),0);
    lv_obj_add_event_cb(header,[](lv_event_t*){full=!full;layout();},LV_EVENT_DOUBLE_CLICKED,nullptr);
    lv_obj_add_event_cb(header,[](lv_event_t* event){if(full)return;lv_point_t point;lv_indev_get_point(lv_indev_active(),&point);if(lv_event_get_code(event)==LV_EVENT_PRESSING){normal_x=std::clamp(normal_x+int(point.x-last_drag.x),0,1280-lv_obj_get_width(window));normal_y=std::clamp(normal_y+int(point.y-last_drag.y),0,690-lv_obj_get_height(window));layout();}last_drag=point;},LV_EVENT_PRESSED,nullptr);
    lv_obj_add_event_cb(header,[](lv_event_t* event){if(full)return;lv_point_t point;lv_indev_get_point(lv_indev_active(),&point);normal_x=std::clamp(normal_x+int(point.x-last_drag.x),0,1280-lv_obj_get_width(window));normal_y=std::clamp(normal_y+int(point.y-last_drag.y),0,690-lv_obj_get_height(window));last_drag=point;layout();},LV_EVENT_PRESSING,nullptr);
    minimize=button(window,"",1114,6,21,[](lv_event_t*){hide(false);});maximize=button(window,"",1138,6,21,[](lv_event_t*){full=!full;layout();});close_button=button(window,"",1162,6,21,[](lv_event_t*){hide(true);});
    for(auto object:{minimize,maximize,close_button}){lv_obj_set_height(object,21);lv_group_remove_obj(object);}
    xp::skin(minimize,xp::Skin::Minimize);xp::skin(maximize,xp::Skin::Maximize);xp::skin(close_button,xp::Skin::Close);
    tabs=lv_tabview_create(window);lv_obj_set_pos(tabs,8,38);lv_obj_set_size(tabs,1180,552);lv_tabview_set_tab_bar_size(tabs,26);lv_obj_set_style_bg_color(tabs,lv_color_hex(0xece9d8),0);
    lv_obj_add_event_cb(tabs,[](lv_event_t*){selected_tab=lv_tabview_get_tab_active(tabs);},LV_EVENT_VALUE_CHANGED,nullptr);
    const char* names[]={"概览","进程","网络","存储","设备","日志","记录","运行","平台"};lv_obj_t* pages[9];
    for(unsigned i=0;i<9;++i){pages[i]=lv_tabview_add_tab(tabs,names[i]);lv_obj_set_style_text_font(pages[i],font,0);lv_obj_set_style_pad_all(pages[i],0,0);lv_obj_set_style_bg_color(pages[i],lv_color_hex(0xece9d8),0);lv_obj_remove_flag(pages[i],LV_OBJ_FLAG_SCROLLABLE);auto tab=lv_tabview_get_tab_button(tabs,i);lv_obj_set_style_text_font(tab,font,0);lv_obj_set_style_text_color(tab,lv_color_black(),0);lv_obj_set_style_bg_color(tab,lv_color_hex(0xece9d8),0);lv_obj_set_style_bg_color(tab,lv_color_white(),LV_STATE_CHECKED);lv_obj_set_style_bg_opa(tab,LV_OPA_COVER,0);lv_obj_set_style_border_width(tab,1,0);lv_obj_set_style_border_width(tab,1,LV_STATE_CHECKED);lv_obj_set_style_border_side(tab,LV_BORDER_SIDE_FULL,0);lv_obj_set_style_border_side(tab,LV_BORDER_SIDE_FULL,LV_STATE_CHECKED);lv_obj_set_style_border_color(tab,lv_color_hex(0xaca899),0);lv_obj_set_style_border_color(tab,lv_color_hex(0xaca899),LV_STATE_CHECKED);lv_obj_set_style_text_color(tab,lv_color_black(),LV_STATE_CHECKED);lv_obj_set_style_radius(tab,3,0);xp::skin(tab,xp::Skin::Tab);lv_obj_set_flex_grow(tab,0);lv_obj_set_size(tab,76,26);}
    auto tab_bar=lv_tabview_get_tab_bar(tabs);lv_obj_set_style_pad_all(tab_bar,0,0);lv_obj_set_style_pad_column(tab_bar,1,0);lv_obj_set_style_bg_color(tab_bar,lv_color_hex(xp::face),0);
    auto content=lv_tabview_get_content(tabs);lv_obj_set_style_border_width(content,1,0);lv_obj_set_style_border_color(content,lv_color_hex(0x919b9c),0);
    cpu_text=label(pages[0],"CPU   —",18,16,540);memory_text=label(pages[0],"内存   —",592,16,540);lv_obj_set_style_text_font(cpu_text,heading_font,0);lv_obj_set_style_text_font(memory_text,heading_font,0);
    cpu_bar=lv_bar_create(pages[0]);memory_bar=lv_bar_create(pages[0]);lv_obj_set_pos(cpu_bar,18,48);lv_obj_set_pos(memory_bar,592,48);for(auto bar:{cpu_bar,memory_bar}){lv_obj_set_size(bar,540,12);lv_obj_set_style_radius(bar,0,0);lv_obj_set_style_radius(bar,0,LV_PART_INDICATOR);lv_obj_set_style_bg_color(bar,lv_color_hex(0x38a243),LV_PART_INDICATOR);}
    machine_text=label(pages[0],"",18,78,1114);lv_obj_set_style_text_line_space(machine_text,5,0);
    cpu_chart=lv_chart_create(pages[0]);memory_chart=lv_chart_create(pages[0]);lv_obj_set_pos(cpu_chart,48,177);lv_obj_set_pos(memory_chart,622,177);
    for(auto chart:{cpu_chart,memory_chart}){lv_obj_set_size(chart,510,172);lv_chart_set_div_line_count(chart,5,7);lv_obj_set_style_pad_all(chart,0,0);lv_chart_set_point_count(chart,60);lv_chart_set_axis_range(chart,LV_CHART_AXIS_PRIMARY_Y,0,100);lv_obj_set_style_bg_color(chart,lv_color_hex(0x0b180d),0);lv_obj_set_style_line_color(chart,lv_color_hex(0x244328),LV_PART_MAIN);lv_obj_set_style_radius(chart,0,0);lv_obj_set_style_size(chart,0,0,LV_PART_INDICATOR);}
    cpu_series=lv_chart_add_series(cpu_chart,lv_color_hex(0x2bdf50),LV_CHART_AXIS_PRIMARY_Y);memory_series=lv_chart_add_series(memory_chart,lv_color_hex(0xe4d52c),LV_CHART_AXIS_PRIMARY_Y);lv_chart_set_all_values(cpu_chart,cpu_series,LV_CHART_POINT_NONE);lv_chart_set_all_values(memory_chart,memory_series,LV_CHART_POINT_NONE);
    auto cpu_caption=label(pages[0],"CPU 使用率 · 最近 60 秒",48,155,350);lv_obj_set_style_text_color(cpu_caption,lv_color_hex(0x006400),0);
    auto memory_caption=label(pages[0],"内存使用率 · 最近 60 秒",622,155,350);lv_obj_set_style_text_color(memory_caption,lv_color_hex(0x706200),0);
    for(int x:{18,592}){label(pages[0],"100%",x,177,30);label(pages[0],"50%",x,254,30);label(pages[0],"0%",x,334,30);label(pages[0],"-60 秒",x+30,354,80);label(pages[0],"-30 秒",x+264,354,80);auto now=label(pages[0],"现在",x+510,354,40);lv_obj_set_style_text_align(now,LV_TEXT_ALIGN_RIGHT,0);}
    button(pages[0],"暂停图表",18,474,100,[](lv_event_t* e){chart_paused=!chart_paused;text(lv_obj_get_child(lv_event_get_target_obj(e),0),chart_paused?"继续图表":"暂停图表");});
    chart_status=label(pages[0],"每秒采样",256,480,600);
    health_text=label(pages[0],"",18,385,1114);lv_obj_set_style_text_line_space(health_text,7,0);lv_label_set_recolor(health_text,true);
    button(pages[0],"同步记录",132,474,100,[](lv_event_t*){queue("sync");});button(pages[0],"重新启动",912,474,100,confirm_power,reinterpret_cast<void*>(1));button(pages[0],"关机",1028,474,100,confirm_power,reinterpret_cast<void*>(2));
    process_table=table(pages[1],16,14,480,{100,450,150,230,180});
    network_table=table(pages[2],16,14,260,{80,154,90,80,130,130,140,140,104});network_text=label(pages[2],"",18,300,1114);
    storage_table=table(pages[3],16,14,240,{210,320,100,160,160,160});
    label(pages[3],"U 盘",18,282,60);disk_select=dropdown(pages[3],92,276,660);
    mount_action=button(pages[3],"挂载",774,276,90,[](lv_event_t*){const auto i=lv_dropdown_get_selected(disk_select);if(i>=disk_ids.size()){text(footer,"未选择 USB 分区");return;}queue("mount",{{"device",disk_ids[i]}});});
    unmount_action=button(pages[3],"卸载",880,276,90,[](lv_event_t*){const auto i=lv_dropdown_get_selected(destination_select);if(i>=destination_ids.size()){text(footer,"未选择 U 盘目录");return;}queue("unmount",{{"path",destination_ids[i]}});});
    label(pages[3],"目录",18,340,60);destination_select=dropdown(pages[3],92,334,660);export_records=button(pages[3],"导出记录",774,334,110,export_action);export_diagnostics=button(pages[3],"导出诊断",902,334,110,export_action,reinterpret_cast<void*>(1));
    device_table=table(pages[4],16,14,480,{140,300,700});
    log_scroll=box(pages[5],16,14,1148,480,0xffffff);lv_obj_add_flag(log_scroll,LV_OBJ_FLAG_SCROLLABLE);lv_obj_add_flag(log_scroll,LV_OBJ_FLAG_CLICKABLE);lv_obj_set_scroll_dir(log_scroll,LV_DIR_VER);
    lv_obj_set_style_bg_color(log_scroll,lv_color_hex(0x9cb8df),LV_PART_SCROLLBAR);lv_obj_set_style_bg_opa(log_scroll,LV_OPA_COVER,LV_PART_SCROLLBAR);lv_obj_set_style_width(log_scroll,8,LV_PART_SCROLLBAR);lv_obj_set_style_radius(log_scroll,2,LV_PART_SCROLLBAR);xp::scrollbar(log_scroll);
    log_text=label(log_scroll,"",8,6,1110);
    history_filter=dropdown(pages[6],16,10,170);lv_dropdown_set_options(history_filter,"全部\n合格\n不合格\n待复核\n错误");lv_obj_add_event_cb(history_filter,[](lv_event_t*){filter_index=lv_dropdown_get_selected(history_filter);history_page=0;},LV_EVENT_VALUE_CHANGED,nullptr);
    history_previous=button(pages[6],"上一页",208,10,88,[](lv_event_t*){if(history_page>0)--history_page;});history_next=button(pages[6],"下一页",312,10,88,[](lv_event_t*){++history_page;});history_count=label(pages[6],"",430,16,700);
    history_table=table(pages[6],16,52,300,{90,260,100,100,100,490});history_detail=label(pages[6],"",18,372,1114);lv_obj_set_style_text_line_space(history_detail,5,0);
    lv_obj_add_event_cb(history_table,[](lv_event_t*){uint32_t row,col;lv_table_get_selected_cell(history_table,&row,&col);if(!row || row>history_rows.size())return;const auto& item=history_rows[row-1];std::string content="本机记录："+item.value("file","")+"\nWeb 记录："+item.value("inspectionId",std::string("待同步"))+"    平台核验："+(item.contains("platformResult")?decision(item["platformResult"]):"待同步")+"\n机器原判保留；证据同步不代表已人工复核，请到 Web 检测记录处理。";for(const auto& finding:item.value("findings",json::array()))content+="\n"+finding.at("label").get<std::string>()+"  "+std::to_string(finding.at("count").get<unsigned>())+" / "+std::to_string(finding.at("min").get<unsigned>())+"–"+std::to_string(finding.at("max").get<unsigned>());text(history_detail,content);},LV_EVENT_VALUE_CHANGED,nullptr);
    job_table=table(pages[7],16,14,240,{280,380,330,150});job_select=dropdown(pages[7],16,276,700);verify_job=button(pages[7],"模型由平台下发",732,276,110,[](lv_event_t*){const auto i=lv_dropdown_get_selected(job_select);if(i>=job_ids.size()){text(footer,"未选择作业");return;}queue("verify",{{"id",job_ids[i]}});});
    activate_job_button=button(pages[7],"请在检测台操作",858,276,280,[](lv_event_t*){const auto i=lv_dropdown_get_selected(job_select);if(i<job_ids.size())queue("activate",{{"id",job_ids[i]}});});
    job_description=label(pages[7],"",18,423,1114);lv_obj_set_style_text_line_space(job_description,6,0);
    button(pages[7],"平台连接",18,474,140,[](lv_event_t*){show_management_tab(8);if(!administrator)login_dialog();});label(pages[7],"模型和产品由平台下发；检测记录自动同步。",180,480,900);
    package_select=dropdown(pages[7],16,332,830);import_job=button(pages[7],"导入作业",866,332,110,[](lv_event_t*){const auto i=lv_dropdown_get_selected(package_select);if(i>=package_ids.size()){text(footer,"未选择作业包");return;}queue("import",{{"package",package_ids[i]}});});
    connection_select=dropdown(pages[7],16,378,830);connect_action=button(pages[7],"连接平台",866,378,110,[](lv_event_t*){const auto i=lv_dropdown_get_selected(connection_select);if(i<connection_ids.size())queue("connect",{{"path",connection_ids[i]}});});
    label(pages[7],"模型与产品由平台下发",16,312,300);label(pages[7],"平台下载的 connection.json",16,358,400);
    platform_text=label(pages[8],"请登录平台管理员账号",18,12,1114);lv_obj_set_style_text_line_space(platform_text,5,0);
    online_devices=dropdown(pages[8],16,86,820);bind_online_button=button(pages[8],"绑定 / 更新本机凭据",858,86,280,[](lv_event_t*){const auto selected=lv_dropdown_get_selected(online_devices);if(selected<online_device_ids.size())queue("bind_online",{{"deviceId",online_device_ids[selected]}});});
    label(pages[8],"按机身编号选择本机；更新绑定将刷新该设备的同步凭据。",18,120,1114);
    online_table=table(pages[8],16,150,200,{280,370,300,190});online_jobs=dropdown(pages[8],16,370,700);
    fetch_job_button=button(pages[8],"下载作业",732,370,110,[](lv_event_t*){const auto selected=lv_dropdown_get_selected(online_jobs);if(selected<online_job_ids.size())queue("fetch_job",{{"id",online_job_ids[selected]}});});
    apply_job_button=button(pages[8],"领取并启用 → 检测",858,370,280,[](lv_event_t*){const auto selected=lv_dropdown_get_selected(online_jobs);if(selected<online_job_ids.size())queue("online_apply",{{"id",online_job_ids[selected]}});});
    lv_obj_add_event_cb(online_table,[](lv_event_t*){uint32_t row,col;lv_table_get_selected_cell(online_table,&row,&col);if(row && row<=online_job_ids.size())lv_dropdown_set_selected(online_jobs,row-1);},LV_EVENT_VALUE_CHANGED,nullptr);
    auto detail_scroll=box(pages[8],16,410,1120,45);lv_obj_add_flag(detail_scroll,LV_OBJ_FLAG_SCROLLABLE);lv_obj_set_scroll_dir(detail_scroll,LV_DIR_VER);xp::scrollbar(detail_scroll);online_description=label(detail_scroll,"",2,2,1090);
    button(pages[8],"运行状态",18,474,100,[](lv_event_t*){show_management_tab(7);});button(pages[8],"平台登录",132,474,100,[](lv_event_t*){if(!administrator)login_dialog();});button(pages[8],"同步记录",246,474,100,[](lv_event_t*){queue("sync");});
    for(auto object:{job_table,job_select,verify_job,activate_job_button,package_select,import_job,online_table,online_jobs,fetch_job_button,apply_job_button})lv_obj_add_flag(object,LV_OBJ_FLAG_HIDDEN);
    for(auto control:{mount_action,unmount_action,export_records,export_diagnostics,verify_job,import_job,activate_job_button,connect_action,bind_online_button,fetch_job_button,apply_job_button})enabled(control,false);
    footer_panel=box(window,12,596,1172,26,0xece9d8);lv_obj_set_style_border_width(footer_panel,1,0);lv_obj_set_style_border_side(footer_panel,LV_BORDER_SIDE_TOP,0);lv_obj_set_style_border_color(footer_panel,lv_color_hex(0xc7c5b2),0);
    footer=label(footer_panel,"",6,4,1150);lv_label_set_long_mode(footer,LV_LABEL_LONG_DOT);
    account_text=label(footer_panel,"操作员",830,6,220);lv_label_set_long_mode(account_text,LV_LABEL_LONG_DOT);
    account_button=button(footer_panel,"管理员登录",1038,2,110,[](lv_event_t*){if(administrator){std::lock_guard<std::mutex> lock(mailbox);if(command_busy)return;queued_action={{"auth","/auth/logout"},{"payload",json::object()}};command_busy=true;administrator=false;}else login_dialog();});
    task=button(taskbar,"系统管理",344,4,200,[](lv_event_t*){if(lv_obj_has_state(task,LV_STATE_CHECKED) && shown)hide(false);else show_management();});lv_obj_set_height(task,22);lv_group_remove_obj(task);xp::skin(task,xp::Skin::Task);lv_obj_set_style_text_color(task,lv_color_white(),0);
    lv_obj_align(lv_obj_get_child(task,0),LV_ALIGN_LEFT_MID,28,0);xp::icon(task,xp::Icon::Control,16,6,3);
    xp::bind_window(window,header,task,minimize,maximize,close_button,group);
    xp::watch_activation(window);lv_obj_add_event_cb(window,[](lv_event_t*){keyboard(group);xp::activate_window(window);},LV_EVENT_PRESSED,nullptr);
    lv_obj_add_flag(task,LV_OBJ_FLAG_HIDDEN);lv_obj_add_flag(window,LV_OBJ_FLAG_HIDDEN);layout();lv_group_set_default(main_group);lv_timer_create(render,100,nullptr);std::thread(worker).detach();
}
} // namespace terminal
