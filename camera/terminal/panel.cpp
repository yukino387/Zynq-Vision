#include "lvgl.h"
#include "nlohmann/json.hpp"
#include "httplib.h"
#include "framebuffer.h"
#include <algorithm>
#include <chrono>
#include <ctime>
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
lv_obj_t *app_window,*titlebar,*toolbar,*workspace,*preview,*results,*report,*notices,*statusbar,*task_button,*start_button,*clock_label,*popup_layer=nullptr,*mouse_cursor=nullptr;
lv_obj_t *min_button,*max_button,*close_button,*max_icon,*restore_icon;
lv_font_t *ui_font,*title_font;
bool maximized=false;
int window_x=20,window_y=16;
lv_point_t drag_point;
enum class Action { Show,Minimize,Maximize,Close,Select,Check,Pause };
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
    lv_obj_set_style_width(object,8,LV_PART_SCROLLBAR);lv_obj_set_style_radius(object,2,LV_PART_SCROLLBAR);
}
lv_obj_t* button(lv_obj_t* parent,const char* value,lv_event_cb_t action) {
    auto object=lv_button_create(parent);lv_obj_set_size(object,88,28);bevel(object,0x003c74);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xffffff),0);lv_obj_set_style_bg_grad_color(object,lv_color_hex(0xe0dfd3),0);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_VER,0);
    lv_obj_set_style_text_color(object,lv_color_black(),0);lv_obj_set_style_pad_all(object,0,0);
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
void close_popup() {if(popup_layer){lv_obj_delete(popup_layer);popup_layer=nullptr;}}
void layout_window() {
    const int width=maximized?1280:1240,height=maximized?690:658;
    lv_obj_set_pos(app_window,maximized?0:window_x,maximized?0:window_y);lv_obj_set_size(app_window,width,height);
    lv_obj_set_width(titlebar,width-8);lv_obj_set_width(toolbar,width-16);
    lv_obj_set_pos(min_button,width-82,6);lv_obj_set_pos(max_button,width-58,6);lv_obj_set_pos(close_button,width-34,6);
    lv_obj_set_width(job_label,width-32);
    const int cell=(width-24)/5;
    for(unsigned i=0;i<5;++i){auto parent=lv_obj_get_parent(counters[i]);lv_obj_set_pos(parent,12+int(i)*cell,124);lv_obj_set_width(parent,cell-4);lv_obj_set_width(counters[i],cell-18);}
    lv_obj_set_size(workspace,width-24,height-194);lv_obj_set_height(preview,height-194);
    lv_obj_set_size(results,width-472,height-194);lv_obj_set_width(lv_obj_get_child(results,0),width-474);
    lv_obj_set_width(result_badge,width-500);lv_obj_set_size(report,width-496,height-380);lv_obj_set_width(result_label,width-520);
    lv_obj_set_pos(notices,10,height-292);lv_obj_set_size(notices,width-496,84);lv_obj_set_width(error_label,width-520);
    lv_obj_set_pos(statusbar,8,height-26);lv_obj_set_width(statusbar,width-16);lv_obj_set_pos(run_label,width-230,1);
    lv_obj_set_pos(max_icon,maximized?7:5,maximized?3:5);lv_obj_set_size(max_icon,maximized?9:11,maximized?9:10);lv_obj_set_style_border_width(max_icon,2,0);
    lv_obj_set_style_border_color(max_icon,lv_color_white(),0);
    if(maximized)lv_obj_remove_flag(restore_icon,LV_OBJ_FLAG_HIDDEN);else lv_obj_add_flag(restore_icon,LV_OBJ_FLAG_HIDDEN);
}
void perform(Action action) {
    close_popup();
    if(action==Action::Show || action==Action::Minimize || action==Action::Close || action==Action::Maximize)lv_dropdown_close(job_select);
    if(action==Action::Show){lv_obj_remove_flag(app_window,LV_OBJ_FLAG_HIDDEN);lv_obj_remove_flag(task_button,LV_OBJ_FLAG_HIDDEN);lv_obj_add_state(task_button,LV_STATE_CHECKED);lv_group_focus_obj(job_select);}
    else if(action==Action::Minimize || action==Action::Close){lv_obj_add_flag(app_window,LV_OBJ_FLAG_HIDDEN);lv_obj_remove_state(task_button,LV_STATE_CHECKED);if(action==Action::Close)lv_obj_add_flag(task_button,LV_OBJ_FLAG_HIDDEN);}
    else if(action==Action::Maximize){maximized=!maximized;layout_window();}
    else if(action==Action::Select)select_job(nullptr);
    else if(action==Action::Check)check(nullptr);
    else if(action==Action::Pause)pause(nullptr);
}
void dispatch(lv_event_t* event) {perform(static_cast<Action>(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event))));}
void task_click(lv_event_t*) {perform(lv_obj_has_flag(app_window,LV_OBJ_FLAG_HIDDEN)?Action::Show:Action::Minimize);}
void drag_window(lv_event_t* event) {
    if(maximized)return;
    lv_point_t point;lv_indev_get_point(lv_indev_active(),&point);
    if(lv_event_get_code(event)==LV_EVENT_PRESSING){window_x=std::clamp(window_x+int(point.x-drag_point.x),-1160,1200);window_y=std::clamp(window_y+int(point.y-drag_point.y),0,660);lv_obj_set_pos(app_window,window_x,window_y);}
    drag_point=point;
}
lv_obj_t* menu_item(lv_obj_t* parent,const char* value,int y,Action action) {
    lv_obj_update_layout(parent);
    auto object=button(parent,value,dispatch);lv_obj_set_pos(object,4,y);lv_obj_set_size(object,lv_obj_get_width(parent)-8,30);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xffffff),0);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_NONE,0);lv_obj_set_style_border_width(object,0,0);lv_obj_set_style_radius(object,0,0);
    lv_obj_set_style_bg_color(object,lv_color_hex(0x316ac5),LV_STATE_PRESSED);lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_PRESSED);
    auto title=lv_obj_get_child(object,0);lv_obj_align(title,LV_ALIGN_LEFT_MID,18,0);
    lv_obj_remove_event_cb(object,dispatch);lv_obj_add_event_cb(object,dispatch,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(action)));
    lv_group_remove_obj(object);return object;
}
lv_obj_t* popup(int x,int y,int width,int height) {
    close_popup();popup_layer=panel(lv_layer_top(),0,0,1280,720,0xffffff);lv_obj_set_style_bg_opa(popup_layer,LV_OPA_TRANSP,0);lv_obj_add_flag(popup_layer,LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(popup_layer,[](lv_event_t*){close_popup();},LV_EVENT_CLICKED,nullptr);
    auto menu=panel(popup_layer,x,y,width,height,0xffffff);bevel(menu,0x7f9db9);lv_obj_set_style_radius(menu,0,0);
    lv_obj_set_style_text_font(menu,ui_font,0);
    lv_obj_set_style_shadow_width(menu,8,0);lv_obj_set_style_shadow_opa(menu,LV_OPA_30,0);lv_obj_set_style_shadow_ofs_x(menu,3,0);lv_obj_set_style_shadow_ofs_y(menu,3,0);
    return menu;
}
void start_menu(lv_event_t*) {
    if(popup_layer){close_popup();return;}
    auto menu=popup(0,534,252,156);
    auto header=panel(menu,1,1,250,35,0x245edb);auto title=caption(header,"开始",14,5,220,0xffffff);lv_obj_set_style_text_font(title,title_font,0);
    menu_item(menu,"视觉检测",43,Action::Show);panel(menu,8,81,236,1,0xd4d0c8);menu_item(menu,"显示桌面",91,Action::Minimize);
}
void file_menu(lv_event_t*) {
    lv_area_t area;lv_obj_get_coords(toolbar,&area);auto menu=popup(area.x1,area.y1-1,186,143);
    menu_item(menu,"选择作业",4,Action::Select);menu_item(menu,"检查一件",36,Action::Check);menu_item(menu,paused?"继续检测":"暂停检测",68,Action::Pause);
    panel(menu,8,102,170,1,0xd4d0c8);menu_item(menu,"关闭",107,Action::Close);
}
void view_menu(lv_event_t*) {
    lv_area_t area;lv_obj_get_coords(toolbar,&area);auto menu=popup(area.x1+66,area.y1-1,186,74);
    menu_item(menu,maximized?"还原":"最大化",4,Action::Maximize);menu_item(menu,"最小化",36,Action::Minimize);
}
void update_clock(lv_timer_t*) {
    const auto now=std::time(nullptr);char value[16];std::strftime(value,sizeof(value),"%H:%M",std::localtime(&now));text(clock_label,value);
}
void discover(lv_indev_t* input,lv_evdev_type_t type,void*) {
    if(type==LV_EVDEV_TYPE_KEY)lv_indev_set_group(input,focus_group);
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
void jobs(lv_timer_t*) {
    try {
        const auto list=get("/jobs");std::string options;std::vector<std::string> ids;
        for(const auto& job:list){if(!options.empty())options+='\n';options+=job.at("name").get<std::string>();ids.push_back(job.at("id"));}
        if(!jobs_loaded || options!=options_cache || ids!=job_ids){jobs_loaded=true;options_cache=options;job_ids=std::move(ids);lv_dropdown_set_options(job_select,options.empty()?"":options.c_str());}
    }catch(const std::exception&){ }
}
void refresh(lv_timer_t*) {
    try {
        const auto state=get("/state");
        paused=state.at("paused");text(lv_obj_get_child(pause_button,0),paused?"继续检测":"暂停检测");
        text(run_label,state.at("job").is_null()?"就绪":paused?"已暂停":"运行中");
        text(job_label,state.at("job").is_null()?"作业：—":"作业："+state["job"].at("name").get<std::string>());
        const unsigned values[]={state.at("total").get<unsigned>(),state["counts"]["PASS"].get<unsigned>(),state["counts"]["FAIL"].get<unsigned>(),state["counts"]["REVIEW"].get<unsigned>(),state["pendingSync"].get<unsigned>()};
        const char* names[]={"已检查","合格","不合格","待复核","待同步"};
        for(unsigned i=0;i<5;++i)text(counters[i],std::string(names[i])+"   "+std::to_string(values[i]));
        if(!state.at("last").is_null()) {
            const auto& last=state.at("last");std::string report="最近检查：第 "+std::to_string(last.at("sequence").get<unsigned>())+" 件 · "+translated(last.at("result"));
            const std::string result=last.at("result");text(result_badge,translated(result));
            lv_obj_set_style_text_color(result_badge,lv_color_hex(result=="PASS"?0x22712b:result=="FAIL"?0xb3261e:0x925b00),0);
            if(last.contains("findings"))for(const auto& finding:last["findings"])report+='\n'+finding.at("label").get<std::string>()+"：确认 "+std::to_string(finding.at("count").get<unsigned>())+"，待确认 "+std::to_string(finding.at("uncertain").get<unsigned>())+"，要求 "+std::to_string(finding.at("min").get<unsigned>())+"–"+std::to_string(finding.at("max").get<unsigned>());
            text(result_label,report);
        }else {text(result_label,"");text(result_badge,"—");lv_obj_set_style_text_color(result_badge,lv_color_black(),0);}
        text(error_label,state.at("error").get<std::string>()+(!state.at("syncError").get<std::string>().empty()?"\n同步失败":""));
        const auto response=engine.Get("/frame");
        if(!response || response->status!=200 || response->body.size()<4){clear_picture();text(fresh_label,"无图像");return;}
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
    ui_font=lv_freetype_font_create(argv[1],LV_FREETYPE_FONT_RENDER_MODE_BITMAP,14,LV_FREETYPE_FONT_STYLE_NORMAL);
    title_font=lv_freetype_font_create(argv[1],LV_FREETYPE_FONT_RENDER_MODE_BITMAP,16,LV_FREETYPE_FONT_STYLE_BOLD);
    auto result_font=lv_freetype_font_create(argv[1],LV_FREETYPE_FONT_RENDER_MODE_BITMAP,22,LV_FREETYPE_FONT_STYLE_BOLD);
    auto start_font=lv_freetype_font_create(argv[1],LV_FREETYPE_FONT_RENDER_MODE_BITMAP,18,static_cast<lv_freetype_font_style_t>(LV_FREETYPE_FONT_STYLE_BOLD|LV_FREETYPE_FONT_STYLE_ITALIC));
    if(!ui_font || !title_font || !result_font || !start_font){std::cerr<<"Cannot load terminal font\n";return 1;}
    ui_font->fallback=title_font->fallback=result_font->fallback=start_font->fallback=&lv_font_montserrat_14;
    auto root=lv_screen_active();lv_obj_set_style_text_font(root,ui_font,0);lv_obj_set_style_text_color(root,lv_color_black(),0);
    lv_obj_set_style_bg_color(root,lv_color_hex(0x3a6ea5),0);lv_obj_set_style_pad_all(root,0,0);lv_obj_remove_flag(root,LV_OBJ_FLAG_SCROLLABLE);
    auto shortcut=panel(root,16,16,80,76,0x3a6ea5);lv_obj_add_flag(shortcut,LV_OBJ_FLAG_CLICKABLE);
    auto monitor=panel(shortcut,22,3,36,30,0xd4d0c8);bevel(monitor,0x414141);panel(monitor,3,3,28,20,0x1548ad);panel(monitor,8,7,18,12,0x68c3f0);panel(shortcut,36,34,8,5,0xd4d0c8);panel(shortcut,28,39,24,3,0xd4d0c8);
    auto shortcut_text=caption(shortcut,"视觉检测",0,49,80,0xffffff);lv_obj_set_style_text_align(shortcut_text,LV_TEXT_ALIGN_CENTER,0);
    lv_obj_add_event_cb(shortcut,dispatch,LV_EVENT_DOUBLE_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(Action::Show)));
    app_window=panel(root,20,16,1240,658,0xece9d8);bevel(app_window,0x00138c);lv_obj_set_style_border_width(app_window,3,0);lv_obj_set_style_radius(app_window,7,0);
    titlebar=panel(app_window,4,4,1232,28,0x0058e8);lv_obj_set_style_bg_grad_color(titlebar,lv_color_hex(0x003bb8),0);lv_obj_set_style_bg_grad_dir(titlebar,LV_GRAD_DIR_VER,0);
    panel(titlebar,1,0,1230,2,0x3897ff);lv_obj_add_flag(titlebar,LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(titlebar,drag_window,LV_EVENT_PRESSED,nullptr);lv_obj_add_event_cb(titlebar,drag_window,LV_EVENT_PRESSING,nullptr);
    lv_obj_add_event_cb(titlebar,dispatch,LV_EVENT_DOUBLE_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(Action::Maximize)));
    auto icon=panel(titlebar,5,5,17,17,0xd4d0c8);bevel(icon,0xffffff);panel(icon,2,2,11,8,0x72c8ef);panel(icon,4,12,7,2,0xffffff);
    auto title=caption(titlebar,"视觉检测",28,1,600,0xffffff);lv_obj_set_style_text_font(title,title_font,0);lv_obj_remove_flag(title,LV_OBJ_FLAG_CLICKABLE);
    auto chrome=[&](Action action,uint32_t top,uint32_t bottom){
        auto object=button(app_window,"",dispatch);lv_obj_set_size(object,22,22);lv_obj_set_style_radius(object,3,0);lv_obj_set_style_border_color(object,lv_color_hex(0xffffff),0);
        lv_obj_set_style_bg_color(object,lv_color_hex(top),0);lv_obj_set_style_bg_grad_color(object,lv_color_hex(bottom),0);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_VER,0);
        lv_obj_remove_event_cb(object,dispatch);lv_obj_add_event_cb(object,dispatch,LV_EVENT_CLICKED,reinterpret_cast<void*>(static_cast<uintptr_t>(action)));lv_group_remove_obj(object);return object;
    };
    min_button=chrome(Action::Minimize,0x70a5ff,0x0750ce);panel(min_button,5,14,10,3,0xffffff);
    max_button=chrome(Action::Maximize,0x70a5ff,0x0750ce);max_icon=panel(max_button,5,5,11,10,0x2168df);bevel(max_icon,0xffffff);lv_obj_set_style_radius(max_icon,0,0);panel(max_icon,0,0,9,1,0xffffff);
    restore_icon=panel(max_button,4,7,9,9,0x2168df);bevel(restore_icon,0xffffff);lv_obj_set_style_border_width(restore_icon,2,0);lv_obj_set_style_radius(restore_icon,0,0);
    close_button=chrome(Action::Close,0xefac94,0xcf3815);text(lv_obj_get_child(close_button,0),LV_SYMBOL_CLOSE);lv_obj_set_style_text_color(close_button,lv_color_white(),0);
    auto menubar=panel(app_window,8,34,1224,24,0xece9d8);
    auto file=button(menubar,"文件(F)",file_menu);lv_obj_set_pos(file,0,0);lv_obj_set_size(file,66,23);lv_obj_set_style_bg_opa(file,LV_OPA_TRANSP,0);lv_obj_set_style_border_width(file,0,0);lv_group_remove_obj(file);
    auto view=button(menubar,"查看(V)",view_menu);lv_obj_set_pos(view,66,0);lv_obj_set_size(view,66,23);lv_obj_set_style_bg_opa(view,LV_OPA_TRANSP,0);lv_obj_set_style_border_width(view,0,0);lv_group_remove_obj(view);
    toolbar=panel(app_window,8,58,1224,38,0xece9d8);lv_obj_set_style_border_width(toolbar,1,0);lv_obj_set_style_border_color(toolbar,lv_color_hex(0xd4d0c8),0);
    panel(toolbar,3,7,1,24,0xaca899);panel(toolbar,5,7,1,24,0xffffff);caption(toolbar,"作业",14,9,36);
    job_select=lv_dropdown_create(toolbar);lv_dropdown_set_options(job_select,"");lv_obj_set_pos(job_select,54,4);lv_obj_set_size(job_select,370,28);bevel(job_select);lv_obj_set_style_radius(job_select,0,0);
    lv_obj_set_style_bg_color(job_select,lv_color_white(),0);lv_obj_set_style_text_color(job_select,lv_color_black(),0);lv_obj_set_style_pad_ver(job_select,3,0);
    auto list=lv_dropdown_get_list(job_select);lv_obj_set_style_text_font(list,ui_font,0);lv_obj_set_style_text_color(list,lv_color_black(),0);lv_obj_set_style_bg_color(list,lv_color_white(),0);bevel(list);lv_obj_set_style_radius(list,0,0);
    lv_obj_set_style_bg_color(list,lv_color_hex(0x316ac5),LV_PART_SELECTED);lv_obj_set_style_text_color(list,lv_color_white(),LV_PART_SELECTED);lv_group_add_obj(focus_group,job_select);
    lv_obj_set_pos(button(toolbar,"选择作业",select_job),436,4);lv_obj_set_pos(button(toolbar,"检查一件",check),534,4);pause_button=button(toolbar,"暂停检测",pause);lv_obj_set_pos(pause_button,632,4);
    job_label=caption(app_window,"作业：—",14,100,1208);lv_label_set_long_mode(job_label,LV_LABEL_LONG_DOT);
    const char* initial[]={"已检查   0","合格   0","不合格   0","待复核   0","待同步   0"};
    const uint32_t colors[]={0x000000,0x006400,0x9c0000,0x805000,0x000000};
    for(unsigned i=0;i<5;++i){auto cell=panel(app_window,12+int(i)*243,124,239,28,0xece9d8);bevel(cell,0xaca899);lv_obj_set_style_radius(cell,0,0);counters[i]=caption(cell,initial[i],7,3,224,colors[i]);}
    workspace=panel(app_window,12,164,1216,464,0xece9d8);
    preview=panel(workspace,0,0,432,464,0xffffff);bevel(preview,0x7f9db9);lv_obj_set_style_radius(preview,0,0);caption(preview,"图像",8,2,416);
    image.header.magic=LV_IMAGE_HEADER_MAGIC;image.header.cf=LV_COLOR_FORMAT_RGB565;image.header.w=416;image.header.h=416;image.header.stride=416*2;image.data_size=pixels.size();image.data=pixels.data();
    picture=lv_image_create(preview);lv_obj_set_pos(picture,7,24);lv_image_set_src(picture,&image);
    results=panel(workspace,448,0,768,464,0xffffff);bevel(results,0x7f9db9);lv_obj_set_style_radius(results,0,0);
    auto result_title=panel(results,0,0,766,24,0xece9d8);caption(result_title,"检测结果",8,2,400);
    result_badge=caption(results,"—",14,34,738);lv_obj_set_style_text_font(result_badge,result_font,0);
    report=panel(results,10,72,744,362,0xffffff);vertical_scroll(report);result_label=caption(report,"",4,0,720);lv_obj_set_style_text_line_space(result_label,6,0);
    notices=panel(results,10,366,744,84,0xffffff);vertical_scroll(notices);error_label=caption(notices,"",4,0,720,0xb3261e);
    statusbar=panel(app_window,8,632,1224,22,0xece9d8);bevel(statusbar,0xaca899);lv_obj_set_style_radius(statusbar,0,0);
    fresh_label=caption(statusbar,"",6,1,800);run_label=caption(statusbar,"",1010,1,190);
    auto taskbar=panel(root,0,690,1280,30,0x245edb);lv_obj_set_style_bg_grad_color(taskbar,lv_color_hex(0x1744b0),0);lv_obj_set_style_bg_grad_dir(taskbar,LV_GRAD_DIR_VER,0);panel(taskbar,0,0,1280,2,0x4993ed);
    start_button=button(taskbar,"",start_menu);lv_obj_set_pos(start_button,-2,0);lv_obj_set_size(start_button,100,30);lv_obj_set_style_radius(start_button,9,0);lv_obj_set_style_border_width(start_button,0,0);
    lv_obj_set_style_bg_color(start_button,lv_color_hex(0x60b04d),0);lv_obj_set_style_bg_grad_color(start_button,lv_color_hex(0x247329),0);lv_group_remove_obj(start_button);
    const uint32_t flag_colors[]={0xf25022,0x7fba00,0x00a4ef,0xffb900};
    for(unsigned i=0;i<4;++i)panel(start_button,15+int(i%2)*9,7+int(i/2)*9,8,8,flag_colors[i]);
    auto start_title=caption(start_button,"开始",40,1,54,0xffffff);lv_obj_set_style_text_font(start_title,start_font,0);
    task_button=button(taskbar,"视觉检测",task_click);lv_obj_set_pos(task_button,112,3);lv_obj_set_size(task_button,200,25);lv_group_remove_obj(task_button);lv_obj_set_style_border_color(task_button,lv_color_hex(0x0c3997),0);
    lv_obj_set_style_bg_color(task_button,lv_color_hex(0x3c80f3),0);lv_obj_set_style_bg_grad_color(task_button,lv_color_hex(0x2a65d3),0);lv_obj_set_style_text_color(task_button,lv_color_white(),0);
    lv_obj_set_style_bg_color(task_button,lv_color_hex(0x1951b9),LV_STATE_CHECKED);lv_obj_set_style_bg_grad_color(task_button,lv_color_hex(0x1648a5),LV_STATE_CHECKED);lv_obj_add_state(task_button,LV_STATE_CHECKED);
    lv_obj_align(lv_obj_get_child(task_button,0),LV_ALIGN_LEFT_MID,12,0);
    auto tray=panel(taskbar,1176,1,104,29,0x0e96e9);lv_obj_set_style_border_width(tray,1,0);lv_obj_set_style_border_color(tray,lv_color_hex(0x19a6f7),0);
    clock_label=caption(tray,"",12,4,80,0xffffff);lv_obj_set_style_text_align(clock_label,LV_TEXT_ALIGN_CENTER,0);update_clock(nullptr);lv_timer_create(update_clock,1000,nullptr);
    layout_window();lv_group_focus_obj(job_select);
    lv_evdev_discovery_start(discover,nullptr);
    engine.set_connection_timeout(0,300000);engine.set_read_timeout(0,600000);engine.set_write_timeout(0,600000);
    jobs(nullptr);lv_timer_create(jobs,2000,nullptr);lv_timer_create(refresh,100,nullptr);
    for(;;){lv_timer_handler();std::this_thread::sleep_for(std::chrono::milliseconds(5));}
}
