#pragma once
#include "lvgl.h"
#include "xp_assets.h"

namespace xp {
constexpr uint32_t face=0xece9d8, selection=0x316ac5, desktop=0x004e98;
enum class Skin { Window,Title,Button,Menu,MenuBar,Task,Start,Taskbar,Tray,Combo,Tab,Status,Minimize,Maximize,Restore,Close };
enum class Icon { Computer,Control,Network,Records,Device,Disk,Document,Jobs };
void skin(lv_obj_t* object,Skin kind);
void active(lv_obj_t* window,bool value);
void bind_window(lv_obj_t* window,lv_obj_t* title,lv_obj_t* task,lv_obj_t* minimize,lv_obj_t* maximize,lv_obj_t* close,lv_group_t* group);
void activate_window(lv_obj_t* window);
void deactivate_window(lv_obj_t* window);
void watch_activation(lv_obj_t* window);
lv_obj_t* icon(lv_obj_t* parent,Icon kind,int size,int x,int y);
const lv_font_t* pixel_font(const char* path,unsigned size,bool bold=false);
void combo(lv_obj_t* object,const lv_font_t* font);
void scrollbar(lv_obj_t* object);
void table(lv_obj_t* object);
}
