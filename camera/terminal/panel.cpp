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
lv_obj_t *job_label,*result_label,*result_badge,*error_label,*fresh_label,*job_select,*picture,*pause_button,*run_label;
lv_obj_t* counters[5];
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
lv_obj_t* panel(lv_obj_t* parent,int x,int y,int width,int height,uint32_t color) {
    auto object=lv_obj_create(parent);lv_obj_remove_style_all(object);lv_obj_set_pos(object,x,y);lv_obj_set_size(object,width,height);
    lv_obj_set_style_bg_color(object,lv_color_hex(color),0);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,0);
    lv_obj_remove_flag(object,LV_OBJ_FLAG_SCROLLABLE);return object;
}
lv_obj_t* caption(lv_obj_t* parent,const char* value,int x,int y,int width,uint32_t color=0x17264a) {
    auto object=label(parent,value);lv_obj_set_pos(object,x,y);lv_obj_set_width(object,width);lv_obj_set_style_text_color(object,lv_color_hex(color),0);return object;
}
void bevel(lv_obj_t* object,uint32_t edge=0x7f9db9) {
    lv_obj_set_style_border_width(object,1,0);lv_obj_set_style_border_color(object,lv_color_hex(edge),0);
    lv_obj_set_style_radius(object,3,0);lv_obj_set_style_shadow_width(object,0,0);
}
void vertical_scroll(lv_obj_t* object) {
    lv_obj_add_flag(object,LV_OBJ_FLAG_SCROLLABLE);lv_obj_set_scroll_dir(object,LV_DIR_VER);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x9cb8df),LV_PART_SCROLLBAR);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,LV_PART_SCROLLBAR);
    lv_obj_set_style_width(object,8,LV_PART_SCROLLBAR);lv_obj_set_style_radius(object,2,LV_PART_SCROLLBAR);
}
lv_obj_t* button(lv_obj_t* parent,const char* value,lv_event_cb_t action) {
    auto object=lv_button_create(parent);lv_obj_set_size(object,148,42);bevel(object,0x003c74);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xffffff),0);lv_obj_set_style_bg_grad_color(object,lv_color_hex(0xe0dfd3),0);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_VER,0);
    lv_obj_set_style_text_color(object,lv_color_hex(0x17264a),0);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xc1d2ee),LV_STATE_PRESSED);lv_obj_set_style_bg_grad_color(object,lv_color_hex(0xe0e9f7),LV_STATE_PRESSED);
    lv_obj_set_style_outline_color(object,lv_color_hex(0xe59700),LV_STATE_FOCUS_KEY);lv_obj_set_style_outline_width(object,2,LV_STATE_FOCUS_KEY);lv_obj_set_style_outline_pad(object,2,LV_STATE_FOCUS_KEY);
    auto title=label(object,value);lv_obj_center(title);lv_obj_add_event_cb(object,action,LV_EVENT_CLICKED,nullptr);lv_group_add_obj(focus_group,object);return object;
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
    else if(type==LV_EVDEV_TYPE_REL){
        auto cursor=lv_obj_create(lv_layer_sys());lv_obj_remove_style_all(cursor);
        lv_obj_set_size(cursor,14,14);lv_obj_set_style_radius(cursor,LV_RADIUS_CIRCLE,0);
        lv_obj_set_style_bg_color(cursor,lv_color_white(),0);lv_obj_set_style_bg_opa(cursor,LV_OPA_COVER,0);
        lv_obj_set_style_border_width(cursor,2,0);lv_obj_set_style_border_color(cursor,lv_color_black(),0);
        lv_indev_set_cursor(input,cursor);
    }
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
        text(run_label,state.at("job").is_null()?"等待选择作业":paused?"检测已暂停":"检测运行中");
        text(job_label,state.at("job").is_null()?"请选择已经下发的作业":state["job"].at("name").get<std::string>()+" · "+state["job"].at("instructions").get<std::string>());
        const unsigned values[]={state.at("total").get<unsigned>(),state["counts"]["PASS"].get<unsigned>(),state["counts"]["FAIL"].get<unsigned>(),state["counts"]["REVIEW"].get<unsigned>(),state["pendingSync"].get<unsigned>()};
        const char* names[]={"本批次已检查","本地符合","本地不符合","待人工复核","待同步"};
        for(unsigned i=0;i<5;++i)text(counters[i],std::string(names[i])+"   "+std::to_string(values[i]));
        if(!state.at("last").is_null()) {
            const auto& last=state.at("last");std::string report="最近检查：第 "+std::to_string(last.at("sequence").get<unsigned>())+" 件 · "+translated(last.at("result"));
            const std::string result=last.at("result");text(result_badge,translated(result));
            lv_obj_set_style_text_color(result_badge,lv_color_hex(result=="PASS"?0x22712b:result=="FAIL"?0xb3261e:0x925b00),0);
            if(last.contains("findings"))for(const auto& finding:last["findings"])report+='\n'+finding.at("label").get<std::string>()+"：确认 "+std::to_string(finding.at("count").get<unsigned>())+"，待确认 "+std::to_string(finding.at("uncertain").get<unsigned>())+"，要求 "+std::to_string(finding.at("min").get<unsigned>())+"–"+std::to_string(finding.at("max").get<unsigned>());
            text(result_label,report);
        }else {text(result_label,"当前作业尚无检查记录\n\n选择已下发的作业后，点击“检查一件”。\n检查结果与记录将在此显示。");text(result_badge,"等待检查");lv_obj_set_style_text_color(result_badge,lv_color_hex(0x316ac5),0);}
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
    }catch(const std::exception& e){text(fresh_label,"画面不可用");text(run_label,"服务连接异常");text(error_label,e.what());}
}
}
int main(int argc,char** argv) {
    if(argc!=2){std::cerr<<"Usage: vision-panel CHINESE_FONT_FILE\n";return 2;}
    {std::ifstream file(pending_file);std::getline(file,pending);if(!pending.empty() && (pending.size()!=36 || pending.find_first_not_of("0123456789abcdef-")!=std::string::npos)){std::cerr<<"Invalid saved panel operation\n";return 1;}}
    lv_init();lv_tick_set_cb(tick);focus_group=lv_group_create();lv_group_set_default(focus_group);
    lv_log_register_print_cb([](lv_log_level_t,const char* message){std::cerr<<message;});
    Framebuffer framebuffer;
    auto font=lv_freetype_font_create(argv[1],LV_FREETYPE_FONT_RENDER_MODE_BITMAP,18,LV_FREETYPE_FONT_STYLE_NORMAL);
    auto title_font=lv_freetype_font_create(argv[1],LV_FREETYPE_FONT_RENDER_MODE_BITMAP,20,LV_FREETYPE_FONT_STYLE_BOLD);
    auto result_font=lv_freetype_font_create(argv[1],LV_FREETYPE_FONT_RENDER_MODE_BITMAP,28,LV_FREETYPE_FONT_STYLE_BOLD);
    if(!font || !title_font || !result_font){std::cerr<<"Cannot load terminal font\n";return 1;}
    font->fallback=title_font->fallback=result_font->fallback=&lv_font_montserrat_14;
    auto root=lv_screen_active();lv_obj_set_style_text_font(root,font,0);lv_obj_set_style_text_color(root,lv_color_hex(0x17264a),0);
    lv_obj_set_style_bg_color(root,lv_color_hex(0x3a6ea5),0);lv_obj_set_style_pad_all(root,0,0);lv_obj_remove_flag(root,LV_OBJ_FLAG_SCROLLABLE);
    auto window=panel(root,12,10,1256,662,0xece9d8);bevel(window,0x003cba);
    auto titlebar=panel(window,0,0,1254,34,0x0865e8);
    lv_obj_set_style_bg_grad_color(titlebar,lv_color_hex(0x0044c4),0);lv_obj_set_style_bg_grad_dir(titlebar,LV_GRAD_DIR_VER,0);
    auto icon=panel(titlebar,10,8,19,19,0xe5f0ff);bevel(icon,0xffffff);panel(icon,3,3,11,4,0x42a44a);panel(icon,3,9,11,5,0x316ac5);
    auto title=caption(titlebar,"CNN 视觉检测终端",38,3,650,0xffffff);lv_obj_set_style_text_font(title,title_font,0);
    caption(titlebar,"独立工作站",1126,5,116,0xe5efff);
    job_label=caption(window,"正在连接本地检测服务…",16,44,1220);lv_label_set_long_mode(job_label,LV_LABEL_LONG_DOT);
    auto controls=panel(window,12,82,1232,44,0xece9d8);
    job_select=lv_dropdown_create(controls);lv_dropdown_set_options(job_select,"正在读取作业…");lv_obj_set_pos(job_select,0,1);lv_obj_set_size(job_select,500,42);bevel(job_select);
    lv_obj_set_style_bg_color(job_select,lv_color_white(),0);lv_obj_set_style_text_color(job_select,lv_color_hex(0x17264a),0);lv_obj_set_style_pad_ver(job_select,7,0);
    lv_obj_set_style_outline_color(job_select,lv_color_hex(0xe59700),LV_STATE_FOCUS_KEY);lv_obj_set_style_outline_width(job_select,2,LV_STATE_FOCUS_KEY);
    auto list=lv_dropdown_get_list(job_select);lv_obj_set_style_text_font(list,font,0);lv_obj_set_style_text_color(list,lv_color_hex(0x17264a),0);lv_obj_set_style_bg_color(list,lv_color_white(),0);bevel(list);
    lv_obj_set_style_bg_color(list,lv_color_hex(0x316ac5),LV_PART_SELECTED);lv_obj_set_style_text_color(list,lv_color_white(),LV_PART_SELECTED);
    lv_group_add_obj(focus_group,job_select);
    lv_obj_set_pos(button(controls,"选择作业",select_job),516,1);lv_obj_set_pos(button(controls,"检查一件",check),680,1);pause_button=button(controls,"暂停检测",pause);lv_obj_set_pos(pause_button,844,1);
    caption(controls,"Tab 切换 · Enter 确认",1010,10,222,0x52647d);
    const char* initial[]={"本批次已检查   0","本地符合   0","本地不符合   0","待人工复核   0","待同步   0"};
    const uint32_t count_colors[]={0x17264a,0x22712b,0xb3261e,0x925b00,0x316ac5};
    for(unsigned i=0;i<5;++i){auto cell=panel(window,12+int(i)*248,136,240,34,0xfaf9f2);bevel(cell,0xc5c3b6);counters[i]=caption(cell,initial[i],10,3,220,count_colors[i]);}
    auto workspace=panel(window,12,180,1232,446,0xece9d8);
    auto tasks=panel(workspace,0,0,182,446,0xd6dff7);bevel(tasks,0x7c9ed9);
    auto task_title=panel(tasks,0,0,180,30,0xf1f5ff);caption(task_title,"检测任务",12,2,154,0x215dc6);
    caption(tasks,"01  选择作业\n\n02  核对实时画面\n\n03  检查并保存结果",12,46,158,0x214f98);
    panel(tasks,12,208,156,1,0xa4b9df);
    caption(tasks,"工作站状态",12,224,158,0x215dc6);run_label=caption(tasks,"连接中…",12,258,158);
    caption(tasks,"操作提示",12,314,158,0x215dc6);caption(tasks,"鼠标点击操作\nTab 切换焦点\nEnter 确认选择",12,348,158);
    auto preview=panel(workspace,194,0,432,446,0xffffff);bevel(preview);
    caption(preview,"摄像头实时画面",8,0,414,0x215dc6);
    image.header.magic=LV_IMAGE_HEADER_MAGIC;image.header.cf=LV_COLOR_FORMAT_RGB565;image.header.w=416;image.header.h=416;image.header.stride=416*2;image.data_size=pixels.size();image.data=pixels.data();
    picture=lv_image_create(preview);lv_obj_set_pos(picture,7,24);lv_image_set_src(picture,&image);
    auto results=panel(workspace,638,0,594,446,0xffffff);bevel(results);
    auto result_title=panel(results,0,0,592,30,0xe3ecfc);caption(result_title,"检查结果与本地记录",12,2,564,0x215dc6);
    result_badge=caption(results,"等待检查",16,42,558,0x316ac5);lv_obj_set_style_text_font(result_badge,result_font,0);
    auto report=panel(results,12,92,566,220,0xffffff);vertical_scroll(report);
    result_label=caption(report,"本次启动尚无检查记录",4,0,542);lv_obj_set_style_text_line_space(result_label,7,0);
    panel(results,12,320,566,1,0xd4d0c8);caption(results,"运行提示",16,328,552,0x52647d);
    auto notices=panel(results,12,358,566,76,0xffffff);vertical_scroll(notices);
    error_label=caption(notices,"",4,0,542,0xb3261e);
    auto status=panel(window,12,634,1232,22,0xe3e0d4);bevel(status,0xb2afa0);fresh_label=caption(status,"等待画面",7,-2,850,0x45546a);caption(status,"本地检测 · Linux",1042,-2,182,0x45546a);
    auto taskbar=panel(root,0,680,1280,40,0x245edb);lv_obj_set_style_bg_grad_color(taskbar,lv_color_hex(0x1142b6),0);lv_obj_set_style_bg_grad_dir(taskbar,LV_GRAD_DIR_VER,0);
    auto station=panel(taskbar,0,0,148,40,0x3c9638);lv_obj_set_style_bg_grad_color(station,lv_color_hex(0x236b20),0);lv_obj_set_style_bg_grad_dir(station,LV_GRAD_DIR_VER,0);lv_obj_set_style_radius(station,10,0);
    auto station_text=caption(station,"检测工作站",20,5,120,0xffffff);lv_obj_set_style_text_font(station_text,title_font,0);
    auto active=panel(taskbar,160,5,326,30,0x1646a1);bevel(active,0x6ba5f4);caption(active,"CNN 视觉检测终端",15,0,296,0xffffff);
    caption(taskbar,"工业视觉 / 独立检测终端",990,7,276,0xffffff);
    lv_evdev_discovery_start(discover,nullptr);
    engine.set_connection_timeout(0,300000);engine.set_read_timeout(0,600000);engine.set_write_timeout(0,600000);
    jobs(nullptr);lv_timer_create(jobs,2000,nullptr);lv_timer_create(refresh,100,nullptr);
    for(;;){lv_timer_handler();std::this_thread::sleep_for(std::chrono::milliseconds(5));}
}
