#pragma once
#include "lvgl.h"
#include <string>
namespace terminal {
void create_management(lv_obj_t* root,lv_obj_t* taskbar,const lv_font_t* font,const lv_font_t* title_font,lv_obj_t* inspection_task,lv_group_t* inspection_group);
bool is_administrator();
void show_login();
bool take_inspection_focus();
void request_job_activation(const std::string& id);
void show_management();
void show_management_tab(unsigned tab);
void show_power_dialog(bool reboot);
void hide_management();
void blur_management();
lv_group_t* management_input_group();
}
