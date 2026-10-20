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
struct Stop {int at;uint32_t color;};
struct Window {lv_obj_t *body,*title,*task,*min,*max,*close;lv_group_t* group;};
std::vector<Window> windows;
lv_obj_t* foreground=nullptr;
uint32_t mix(uint32_t a,uint32_t b,int t,int span) {
    uint32_t value=0;for(int shift:{0,8,16})value|=uint32_t((int((a>>shift)&255)*(span-t)+int((b>>shift)&255)*t)/span)<<shift;return value;
}
void fill(lv_layer_t* layer,int x,int y,int w,int h,uint32_t color,int radius=0) {
    if(w<=0 || h<=0)return;lv_draw_rect_dsc_t d;lv_draw_rect_dsc_init(&d);d.bg_color=lv_color_hex(color);d.bg_opa=LV_OPA_COVER;d.radius=radius;
    lv_area_t a{x,y,x+w-1,y+h-1};lv_draw_rect(layer,&d,&a);
}
void edge(lv_layer_t* layer,int x,int y,int w,int h,uint32_t top,uint32_t bottom) {
    fill(layer,x,y,w,1,top);fill(layer,x,y,1,h,top);fill(layer,x,y+h-1,w,1,bottom);fill(layer,x+w-1,y,1,h,bottom);
}
void gradient(lv_layer_t* layer,int x,int y,int w,int h,std::initializer_list<Stop> stops,int radius=0) {
    auto first=stops.begin(),last=first;
    for(int row=0;row<h;++row){const int at=h>1?row*1000/(h-1):0;while(last+1!=stops.end() && (last+1)->at<at)++last;
        auto next=last+1==stops.end()?last:last+1;const int span=next->at-last->at;const uint32_t color=span?mix(last->color,next->color,std::clamp(at-last->at,0,span),span):last->color;
        int inset=0;if(radius && row<radius){const float dy=radius-row-.5f;inset=int(std::ceil(radius-std::sqrt(float(radius*radius)-dy*dy)-.5f));}
        fill(layer,x+inset,y+row,w-inset*2,1,color);
    }
}
void image(lv_layer_t* layer,const lv_image_dsc_t& source,int x,int y) {
    lv_draw_image_dsc_t d;lv_draw_image_dsc_init(&d);d.src=&source;lv_area_t a{x,y,x+int(source.header.w)-1,y+int(source.header.h)-1};lv_draw_image(layer,&d,&a);
}
void dotted(lv_layer_t* layer,int x,int y,int w,int h) {
    for(int i=0;i<w;i+=2){fill(layer,x+i,y,1,1,0x000000);fill(layer,x+i,y+h-1,1,1,0x000000);}
    for(int i=0;i<h;i+=2){fill(layer,x,y+i,1,1,0x000000);fill(layer,x+w-1,y+i,1,1,0x000000);}
}
void draw(lv_event_t* event) {
    auto object=lv_event_get_target_obj(event);const auto kind=Skin(reinterpret_cast<uintptr_t>(lv_event_get_user_data(event)));
    auto layer=lv_event_get_layer(event);lv_area_t a;lv_obj_get_coords(object,&a);const int x=a.x1,y=a.y1,w=lv_area_get_width(&a),h=lv_area_get_height(&a);
    const auto state=lv_obj_get_state(object);const bool pressed=state&LV_STATE_PRESSED,hover=state&LV_STATE_HOVERED,checked=state&LV_STATE_CHECKED,disabled=state&LV_STATE_DISABLED,inactive=state&LV_STATE_USER_1;
    if(kind==Skin::Window){
        fill(layer,x,y+7,w,h-7,face);fill(layer,x,y+6,3,h-6,inactive?0x688de0:0x0855dd);fill(layer,x+w-3,y+6,3,h-6,inactive?0x7a9fe6:0x001ea0);
        fill(layer,x,y+h-3,w,1,inactive?0x7a9fe6:0x003bda);fill(layer,x,y+h-2,w,1,inactive?0x688de0:0x001ea0);fill(layer,x,y+h-1,w,1,inactive?0x5b78c2:0x00138c);
        fill(layer,x,y+8,1,h-8,inactive?0x688de0:0x0831d9);fill(layer,x+1,y+7,1,h-9,inactive?0x83a6e8:0x166aee);
    }else if(kind==Skin::Title){
        if(inactive)gradient(layer,x,y,w,h,{{0,0x9bbdf7},{80,0x7aa2e7},{400,0x7a96df},{900,0x7ba2e7},{1000,0x6085c8}},7);
        else gradient(layer,x,y,w,h,{{0,0x0997ff},{80,0x0053ee},{400,0x0050ee},{880,0x0066ff},{930,0x0066ff},{950,0x005bff},{960,0x003dd7},{1000,0x003dd7}},7);
        fill(layer,x+7,y,w-14,1,inactive?0x688de0:0x0831d9);
    }else if(kind==Skin::Minimize || kind==Skin::Maximize || kind==Skin::Restore || kind==Skin::Close){
        using namespace assets;const lv_image_dsc_t* sprite;
        if(kind==Skin::Minimize)sprite=pressed?&minimize_active:hover?&minimize_hover:&minimize;
        else if(kind==Skin::Maximize)sprite=pressed?&maximize_active:hover?&maximize_hover:&maximize;
        else if(kind==Skin::Restore)sprite=pressed?&restore_active:hover?&restore_hover:&restore;
        else sprite=pressed?&close_active:hover?&close_hover:&close;
        image(layer,*sprite,x,y);
        if(inactive){lv_draw_rect_dsc_t d;lv_draw_rect_dsc_init(&d);d.bg_color=lv_color_hex(0x8ba8e6);d.bg_opa=LV_OPA_40;d.radius=3;lv_draw_rect(layer,&d,&a);}
    }else if(kind==Skin::Button){
        fill(layer,x,y,w,h,disabled?0xc9c7ba:0x003c74,3);
        if(disabled)fill(layer,x+1,y+1,w-2,h-2,0xf5f4ea,2);
        else if(pressed)gradient(layer,x+1,y+1,w-2,h-2,{{0,0xcdcac3},{80,0xe3e3db},{940,0xe5e5de},{1000,0xf2f2f1}},2);
        else gradient(layer,x+1,y+1,w-2,h-2,{{0,0xffffff},{860,0xecebe5},{1000,0xd8d0c4}},2);
        if(!disabled && !pressed && (hover || (state&LV_STATE_FOCUSED))){const bool warm=hover;
            edge(layer,x+1,y+1,w-2,h-2,warm?0xfdd889:0x98b8ea,warm?0xe5a01a:0x89ade4);
            edge(layer,x+2,y+2,w-4,h-4,warm?0xfff0cf:0xcee7ff,warm?0xfbc761:0xbcd4f6);
        }
        if(state&LV_STATE_FOCUS_KEY)dotted(layer,x+4,y+4,w-8,h-8);
    }else if(kind==Skin::Taskbar){
        gradient(layer,x,y,w,h,{{0,0x1f2f86},{30,0x3165c4},{60,0x3682e5},{100,0x4490e6},{150,0x2b71e0},{200,0x235bd6},{380,0x2157d6},{540,0x245ddb},{860,0x2562df},{950,0x1d4ec0},{1000,0x1941a5}});
    }else if(kind==Skin::Tray){
        gradient(layer,x,y,w,h,{{0,0x0c59b9},{60,0x139ee9},{100,0x18b5f2},{190,0x1290e8},{630,0x0d8dea},{810,0x0d9ff1},{940,0x1392e2},{1000,0x095bc9}});
        fill(layer,x,y,1,h,0x1042af);fill(layer,x+1,y+2,1,h-2,0x18bbff);
    }else if(kind==Skin::Task){
        const uint32_t color=pressed?0x1e52b7:checked?(hover?0x3576f3:0x1e52b7):(hover?0x53a3ff:0x3c81f3);
        fill(layer,x,y,w,h,color,2);edge(layer,x+1,y+1,w-2,h-2,checked?0x153e8c:0x74a8f9,checked?0x17469e:0x1a53b0);
    }else if(kind==Skin::Start){
        for(int row=0;row<h;++row){int inset=row<4?4-row:row>h-7?(row-h+7)/2:0;uint32_t c=assets::start_profile[std::min(row,29)];if(pressed||checked)c=mix(c,0x123d0b,380,1000);else if(hover)c=mix(c,0xffffff,100,1000);fill(layer,x,y+row,w-inset,1,c);}
        image(layer,assets::start_logo,x+8,y+3);
    }else if(kind==Skin::Menu || kind==Skin::MenuBar){
        if(hover || pressed || checked || (state&LV_STATE_FOCUSED)){fill(layer,x,y,w,h,selection);}
    }else if(kind==Skin::Combo){
        fill(layer,x,y,w,h,disabled?face:0xffffff);edge(layer,x,y,w,h,0x7f9db9,0x7f9db9);
        const int bx=x+w-18;fill(layer,bx,y+1,17,h-2,0xc1d2ee,2);
        gradient(layer,bx+1,y+2,15,h-4,{{0,hover?0xe8f1ffu:0xe1eafeu},{1000,pressed?0xa5bee7u:0xb8cdf3u}});
        edge(layer,bx,y+1,17,h-2,hover?0x799fe0:0xb5c8eb,0x718bb7);
        for(int row=0;row<4;++row)fill(layer,bx+5+row,y+h/2-1+row,7-2*row,1,disabled?0xa1a192:0x4d6185);
    }else if(kind==Skin::Tab){
        fill(layer,x,y,w,h,0x919b9c,3);gradient(layer,x+1,y+1,w-2,h-1,{{0,0xffffff},{1000,checked?0xfcfcfeu:0xece9d8u}},3);
        if(checked){fill(layer,x+2,y,w-4,2,0xffc73c);fill(layer,x+2,y+2,w-4,1,0xffe49c);}
        if(state&LV_STATE_FOCUS_KEY)dotted(layer,x+5,y+5,w-10,h-10);
    }else if(kind==Skin::Status){fill(layer,x,y,w,h,face);fill(layer,x,y,w,1,0xd4d0c8);fill(layer,x,y+1,w,1,0xffffff);}
}
struct Glyph {std::unique_ptr<lv_draw_buf_t,decltype(&lv_draw_buf_destroy)> buffer{nullptr,lv_draw_buf_destroy};int advance=0,left=0,top=0,width=0,height=0;};
struct Font {
    FT_Library library{};FT_Face face{};lv_font_t font{};bool bold;std::unordered_map<uint32_t,Glyph> glyphs;
    Font(const char* path,unsigned size,bool weight):bold(weight) {
        if(FT_Init_FreeType(&library) || FT_New_Face(library,path,0,&face) || FT_Set_Pixel_Sizes(face,0,size))throw std::runtime_error("Cannot load XP UI font");
        font.line_height=size+2;font.base_line=2;font.underline_position=-1;font.underline_thickness=1;font.kerning=LV_FONT_KERNING_NONE;font.user_data=this;
        font.get_glyph_dsc=[](const lv_font_t* f,lv_font_glyph_dsc_t* d,uint32_t letter,uint32_t)->bool {
            auto self=static_cast<Font*>(f->user_data);if(letter=='\t')letter=' ';auto it=self->glyphs.find(letter);
            if(it==self->glyphs.end()){
                const auto index=FT_Get_Char_Index(self->face,letter);if(!index)return false;
                if(FT_Load_Glyph(self->face,index,FT_LOAD_TARGET_MONO))return false;
                if(self->bold)FT_GlyphSlot_Embolden(self->face->glyph);
                if(FT_Render_Glyph(self->face->glyph,FT_RENDER_MODE_MONO))return false;
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
    for(lv_state_t state:{lv_state_t(0),lv_state_t(LV_STATE_HOVERED),lv_state_t(LV_STATE_PRESSED),lv_state_t(LV_STATE_FOCUSED),lv_state_t(LV_STATE_FOCUS_KEY),lv_state_t(LV_STATE_CHECKED),lv_state_t(LV_STATE_DISABLED)}){
        lv_obj_set_style_bg_opa(object,LV_OPA_TRANSP,state);lv_obj_set_style_border_width(object,0,state);lv_obj_set_style_shadow_width(object,0,state);lv_obj_set_style_outline_width(object,0,state);lv_obj_set_style_radius(object,0,state);
    }
    lv_obj_set_style_anim_duration(object,0,0);
    lv_obj_set_style_pad_all(object,0,0);lv_obj_set_style_transform_width(object,0,LV_STATE_PRESSED);lv_obj_set_style_transform_height(object,0,LV_STATE_PRESSED);
    if(kind==Skin::Menu){lv_obj_set_style_text_color(object,lv_color_white(),LV_STATE_FOCUSED);lv_obj_add_event_cb(object,[](lv_event_t* e){lv_group_focus_obj(lv_event_get_target_obj(e));},LV_EVENT_HOVER_OVER,nullptr);}
    lv_obj_remove_event_cb(object,draw);lv_obj_add_event_cb(object,draw,kind==Skin::Combo?LV_EVENT_DRAW_MAIN_BEGIN:LV_EVENT_DRAW_MAIN,reinterpret_cast<void*>(static_cast<uintptr_t>(kind)));
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
    skin(object,Skin::Combo);lv_dropdown_set_symbol(object,nullptr);lv_obj_set_style_text_align(object,LV_TEXT_ALIGN_LEFT,0);lv_obj_set_style_pad_left(object,5,0);lv_obj_set_style_pad_right(object,23,0);lv_obj_set_style_pad_top(object,4,0);lv_obj_set_style_text_font(object,font,0);lv_obj_set_style_text_color(object,lv_color_black(),0);
    auto list=lv_dropdown_get_list(object);lv_obj_set_style_text_font(list,font,0);lv_obj_set_style_bg_color(list,lv_color_white(),0);lv_obj_set_style_text_color(list,lv_color_black(),0);lv_obj_set_style_border_width(list,1,0);lv_obj_set_style_border_color(list,lv_color_hex(0x7f9db9),0);lv_obj_set_style_radius(list,0,0);lv_obj_set_style_pad_all(list,1,0);lv_obj_set_style_pad_ver(list,3,LV_PART_SELECTED);lv_obj_set_style_bg_color(list,lv_color_hex(selection),LV_PART_SELECTED);lv_obj_set_style_text_color(list,lv_color_white(),LV_PART_SELECTED);
    lv_obj_set_style_bg_color(list,lv_color_hex(selection),LV_PART_SELECTED|LV_STATE_CHECKED);scrollbar(list);
}
void scrollbar(lv_obj_t* object){
    lv_obj_set_style_width(object,16,LV_PART_SCROLLBAR);lv_obj_set_style_radius(object,1,LV_PART_SCROLLBAR);lv_obj_set_style_bg_opa(object,LV_OPA_COVER,LV_PART_SCROLLBAR);
    lv_obj_set_style_bg_color(object,lv_color_hex(0xc5d5ff),LV_PART_SCROLLBAR);lv_obj_set_style_bg_grad_color(object,lv_color_hex(0xb6caf7),LV_PART_SCROLLBAR);lv_obj_set_style_bg_grad_dir(object,LV_GRAD_DIR_HOR,LV_PART_SCROLLBAR);
    lv_obj_set_style_border_width(object,1,LV_PART_SCROLLBAR);lv_obj_set_style_border_color(object,lv_color_white(),LV_PART_SCROLLBAR);lv_obj_set_style_pad_right(object,1,LV_PART_SCROLLBAR);
}
void table(lv_obj_t* object){
    scrollbar(object);lv_obj_set_style_border_width(object,1,0);lv_obj_set_style_border_color(object,lv_color_hex(0x7f9db9),0);
    lv_obj_set_style_border_width(object,0,LV_PART_ITEMS);lv_obj_set_style_bg_color(object,lv_color_white(),LV_PART_ITEMS);lv_obj_set_style_bg_color(object,lv_color_hex(selection),LV_PART_ITEMS|LV_STATE_PRESSED);lv_obj_set_style_text_color(object,lv_color_white(),LV_PART_ITEMS|LV_STATE_PRESSED);
    lv_obj_add_flag(object,LV_OBJ_FLAG_SEND_DRAW_TASK_EVENTS);
    lv_obj_add_event_cb(object,[](lv_event_t* e){auto task=static_cast<lv_draw_task_t*>(lv_event_get_param(e));auto base=static_cast<lv_draw_dsc_base_t*>(lv_draw_task_get_draw_dsc(task));if(base->part!=LV_PART_ITEMS || base->id1!=0)return;
        if(auto fill=lv_draw_task_get_fill_dsc(task)){fill->color=lv_color_hex(face);fill->grad.dir=LV_GRAD_DIR_VER;fill->grad.stops_count=2;fill->grad.stops[0].color=lv_color_hex(0xffffff);fill->grad.stops[0].opa=LV_OPA_COVER;fill->grad.stops[0].frac=0;fill->grad.stops[1].color=lv_color_hex(0xe2dfd3);fill->grad.stops[1].opa=LV_OPA_COVER;fill->grad.stops[1].frac=255;}
        if(auto label=lv_draw_task_get_label_dsc(task))label->color=lv_color_black();
    },LV_EVENT_DRAW_TASK_ADDED,nullptr);
}
}
