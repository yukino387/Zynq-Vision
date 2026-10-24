#include "xp_style.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <unordered_map>
#include <vector>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_SYNTHESIS_H

namespace xp { namespace {
struct Window {lv_obj_t *body,*title,*task,*min,*max,*close;lv_group_t* group;};
std::vector<Window> windows;
lv_obj_t* foreground=nullptr;
struct Glyph {std::unique_ptr<lv_draw_buf_t,decltype(&lv_draw_buf_destroy)> buffer{nullptr,lv_draw_buf_destroy};int advance=0,left=0,top=0,width=0,height=0;};
struct Font {
    FT_Library library{};FT_Face face{};lv_font_t font{};bool bold;std::unordered_map<uint32_t,Glyph> glyphs;
    Font(const char* path,unsigned size,bool weight):bold(weight) {
        if(FT_Init_FreeType(&library) || FT_New_Face(library,path,0,&face) || FT_Set_Pixel_Sizes(face,0,size))throw std::runtime_error("Cannot load terminal UI font");
        font.line_height=size+6;font.base_line=5;font.underline_position=-1;font.underline_thickness=1;font.kerning=LV_FONT_KERNING_NONE;font.user_data=this;
        font.get_glyph_dsc=[](const lv_font_t* f,lv_font_glyph_dsc_t* d,uint32_t letter,uint32_t)->bool {
            auto self=static_cast<Font*>(f->user_data);if(letter=='\t')letter=' ';auto it=self->glyphs.find(letter);
            if(it==self->glyphs.end()){
                const auto index=FT_Get_Char_Index(self->face,letter);if(!index)return false;
                if(FT_Load_Glyph(self->face,index,FT_LOAD_NO_BITMAP | FT_LOAD_TARGET_NORMAL))return false;
                if(self->bold)FT_GlyphSlot_Embolden(self->face->glyph);
                if(FT_Render_Glyph(self->face->glyph,FT_RENDER_MODE_NORMAL))return false;
                const auto slot=self->face->glyph;const auto& bitmap=slot->bitmap;Glyph glyph;glyph.advance=slot->advance.x>>6;glyph.left=slot->bitmap_left;glyph.top=slot->bitmap_top;glyph.width=bitmap.width;glyph.height=bitmap.rows;
                if(glyph.width && glyph.height){glyph.buffer.reset(lv_draw_buf_create(glyph.width,glyph.height,LV_COLOR_FORMAT_A8,LV_STRIDE_AUTO));if(!glyph.buffer)return false;
                    for(int y=0;y<glyph.height;++y){auto row=bitmap.buffer+(bitmap.pitch<0?glyph.height-1-y:y)*std::abs(bitmap.pitch);auto dest=glyph.buffer->data+y*glyph.buffer->header.stride;
                        for(int x=0;x<glyph.width;++x)dest[x]=bitmap.pixel_mode==FT_PIXEL_MODE_MONO?((row[x/8]&(0x80>>(x%8)))?255:0):row[x];}}
                it=self->glyphs.emplace(letter,std::move(glyph)).first;
            }
            const auto& g=it->second;d->adv_w=g.advance;d->box_w=g.width;d->box_h=g.height;d->ofs_x=g.left;d->ofs_y=g.top-g.height;d->format=LV_FONT_GLYPH_FORMAT_A8;d->gid.src=&g;return true;
        };
        font.get_glyph_bitmap=[](lv_font_glyph_dsc_t* d,lv_draw_buf_t*)->const void* {return static_cast<const Glyph*>(d->gid.src)->buffer.get();};
    }
    ~Font(){glyphs.clear();if(face)FT_Done_Face(face);if(library)FT_Done_FreeType(library);}
};
std::vector<std::unique_ptr<Font>> fonts;
}
void skin(lv_obj_t* object,Skin kind) {
    const auto x=lv_obj_get_style_x(object,LV_PART_MAIN),y=lv_obj_get_style_y(object,LV_PART_MAIN);
    const auto width=lv_obj_get_style_width(object,LV_PART_MAIN),height=lv_obj_get_style_height(object,LV_PART_MAIN);
    lv_obj_remove_style_all(object);
    lv_obj_set_pos(object,x,y);lv_obj_set_size(object,width,height);
    lv_obj_set_style_bg_opa(object,LV_OPA_COVER,0);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_NONE,0);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xffffff),0);lv_obj_set_style_border_width(object,1,0);lv_obj_set_style_border_color(object,lv_color_hex(0xdce5ef),0);
    lv_obj_set_style_radius(object,7,0);lv_obj_set_style_shadow_width(object,0,0);lv_obj_set_style_outline_width(object,0,0);lv_obj_set_style_pad_all(object,0,0);
    lv_obj_set_style_transform_width(object,0,LV_STATE_PRESSED);lv_obj_set_style_transform_height(object,0,LV_STATE_PRESSED);lv_obj_set_style_anim_duration(object,0,0);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xeef4fc),LV_STATE_HOVERED);lv_obj_set_style_bg_color(object,lv_color_hex(0xdceaff),LV_STATE_PRESSED);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xf0f3f7),LV_STATE_DISABLED);lv_obj_set_style_text_color(object,lv_color_hex(0x9aa9bb),LV_STATE_DISABLED);
    lv_obj_set_style_outline_color(object,lv_color_hex(0x2677eb),LV_STATE_FOCUS_KEY);lv_obj_set_style_outline_width(object,2,LV_STATE_FOCUS_KEY);lv_obj_set_style_outline_pad(object,2,LV_STATE_FOCUS_KEY);
    if(kind==Skin::Window){lv_obj_set_style_radius(object,0,0);lv_obj_set_style_bg_color(object,lv_color_hex(face),0);lv_obj_set_style_border_width(object,0,0);}
    else if(kind==Skin::Title){lv_obj_set_style_radius(object,0,0);lv_obj_set_style_border_width(object,0,0);lv_obj_set_style_bg_color(object,lv_color_hex(0x14283f),0);}
    else if(kind==Skin::Tab){lv_obj_set_style_border_width(object,0,0);lv_obj_set_style_bg_color(object,lv_color_hex(face),0);lv_obj_set_style_bg_color(object,lv_color_hex(0x176bde),LV_STATE_CHECKED);lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_CHECKED);}
}
void active(lv_obj_t* object,bool value){if(value)lv_obj_remove_state(object,LV_STATE_USER_1);else lv_obj_add_state(object,LV_STATE_USER_1);lv_obj_invalidate(object);}
void bind_window(lv_obj_t* body,lv_obj_t* title,lv_obj_t* task,lv_obj_t* minimize,lv_obj_t* maximize,lv_obj_t* close,lv_group_t* group){windows.push_back({body,title,task,minimize,maximize,close,group});}
void deactivate_window(lv_obj_t* body){
    const bool was_foreground=foreground==body;
    for(auto& w:windows)if(w.body==body){for(auto o:{w.body,w.title,w.min,w.max,w.close})active(o,false);lv_obj_remove_state(w.task,LV_STATE_CHECKED);}
    if(was_foreground){foreground=nullptr;for(auto it=windows.rbegin();it!=windows.rend();++it)if(it->body!=body && !lv_obj_has_flag(it->body,LV_OBJ_FLAG_HIDDEN)){activate_window(it->body);break;}}
}
void activate_window(lv_obj_t* body){
    if(foreground==body)return;for(auto& w:windows){const bool selected=w.body==body;for(auto o:{w.body,w.title,w.min,w.max,w.close})active(o,selected);if(selected)lv_obj_add_state(w.task,LV_STATE_CHECKED);else lv_obj_remove_state(w.task,LV_STATE_CHECKED);}
    foreground=body;lv_obj_move_foreground(body);
    for(const auto& window:windows)if(window.body==body)for(auto input=lv_indev_get_next(nullptr);input;input=lv_indev_get_next(input))if(lv_indev_get_type(input)==LV_INDEV_TYPE_KEYPAD)lv_indev_set_group(input,window.group);
}
void watch_activation(lv_obj_t* window){
    // Press notifications bubble to the containing window before a control is released.
    for(uint32_t i=0;i<lv_obj_get_child_count(window);++i){auto child=lv_obj_get_child(window,i);lv_obj_add_flag(child,LV_OBJ_FLAG_EVENT_BUBBLE);watch_activation(child);}
}
lv_obj_t* icon(lv_obj_t* parent,Icon kind,int size,int x,int y){
    using namespace assets;const lv_image_dsc_t* small[]={&computer_16,&control_16,&network_16,&records_16,&device_16,&disk_16,&document_16,&jobs_16};
    const lv_image_dsc_t* large[]={&computer_32,&control_32,&network_32,&records_32,&device_32,&disk_32,&document_32,&jobs_32};
    auto object=lv_image_create(parent);lv_image_set_src(object,size==16?small[int(kind)]:large[int(kind)]);lv_obj_set_pos(object,x,y);lv_obj_remove_flag(object,LV_OBJ_FLAG_CLICKABLE);return object;
}
const lv_font_t* pixel_font(const char* path,unsigned size,bool bold){fonts.emplace_back(new Font(path,size,bold));return &fonts.back()->font;}
void combo(lv_obj_t* object,const lv_font_t* font){
    skin(object,Skin::Combo);lv_dropdown_set_symbol(object,LV_SYMBOL_DOWN);lv_obj_set_style_text_font(object,LV_FONT_DEFAULT,LV_PART_INDICATOR);lv_obj_set_style_text_align(object,LV_TEXT_ALIGN_LEFT,0);lv_obj_set_style_pad_left(object,8,0);lv_obj_set_style_pad_right(object,12,0);lv_obj_set_style_pad_top(object,5,0);lv_obj_set_style_text_font(object,font,0);lv_obj_set_style_text_color(object,lv_color_hex(0x243950),0);
    auto list=lv_dropdown_get_list(object);lv_obj_set_style_text_font(list,font,0);lv_obj_set_style_bg_color(list,lv_color_white(),0);lv_obj_set_style_text_color(list,lv_color_hex(0x243950),0);lv_obj_set_style_border_width(list,1,0);lv_obj_set_style_border_color(list,lv_color_hex(0x7f9db9),0);lv_obj_set_style_radius(list,8,0);lv_obj_set_style_pad_all(list,1,0);lv_obj_set_style_pad_ver(list,3,LV_PART_SELECTED);lv_obj_set_style_bg_color(list,lv_color_hex(selection),LV_PART_SELECTED);lv_obj_set_style_text_color(list,lv_color_white(),LV_PART_SELECTED);
    lv_obj_set_style_bg_color(list,lv_color_hex(selection),LV_PART_SELECTED|LV_STATE_CHECKED);scrollbar(list);
}
void scrollbar(lv_obj_t* object){
    lv_obj_set_style_width(object,4,LV_PART_SCROLLBAR);lv_obj_set_style_radius(object,2,LV_PART_SCROLLBAR);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,LV_PART_SCROLLBAR);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xbac9d9),LV_PART_SCROLLBAR);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_NONE,LV_PART_SCROLLBAR);lv_obj_set_style_border_width(object,0,LV_PART_SCROLLBAR);
}
void table(lv_obj_t* object){
    scrollbar(object);lv_obj_set_style_border_width(object,1,0);lv_obj_set_style_border_color(object,lv_color_hex(0xe0e7ef),0);lv_obj_set_style_radius(object,8,0);
    lv_obj_set_style_border_width(object,1,LV_PART_ITEMS);lv_obj_set_style_border_side(object,LV_BORDER_SIDE_BOTTOM,LV_PART_ITEMS);lv_obj_set_style_border_color(object,lv_color_hex(0xecf0f5),LV_PART_ITEMS);
    lv_obj_set_style_bg_color(object,lv_color_white(),LV_PART_ITEMS);lv_obj_set_style_bg_color(object,lv_color_hex(0xe8f1ff),LV_PART_ITEMS|LV_STATE_PRESSED);lv_obj_set_style_text_color(object,lv_color_hex(0x243950),LV_PART_ITEMS);
    lv_obj_add_flag(object,LV_OBJ_FLAG_SEND_DRAW_TASK_EVENTS);
    lv_obj_add_event_cb(object,[](lv_event_t* e){auto task=static_cast<lv_draw_task_t*>(lv_event_get_param(e));auto base=static_cast<lv_draw_dsc_base_t*>(lv_draw_task_get_draw_dsc(task));if(base->part!=LV_PART_ITEMS)return;
        if(auto fill=lv_draw_task_get_fill_dsc(task)){fill->color=lv_color_hex(base->id1==0?0xeef3f9:base->id1%2?0xffffff:0xf8fafc);fill->grad.dir=LV_GRAD_DIR_NONE;}
        if(auto label=lv_draw_task_get_label_dsc(task))label->color=lv_color_hex(base->id1==0?0x718197:0x243950);
    },LV_EVENT_DRAW_TASK_ADDED,nullptr);
}
}
