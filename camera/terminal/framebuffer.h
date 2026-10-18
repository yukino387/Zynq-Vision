#pragma once
#include "lvgl.h"
#include <vector>
#include <stdexcept>
#include <cstring>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <linux/fb.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

class Framebuffer {
    int fd=-1;
    uint8_t* memory=nullptr;
    fb_fix_screeninfo fixed{};
    fb_var_screeninfo variable{};
    unsigned front=0;
    std::vector<uint8_t> draw_a,draw_b;
    std::vector<lv_area_t> dirty;
    static void flush(lv_display_t* display,const lv_area_t* area,uint8_t* pixels) {
        auto self=static_cast<Framebuffer*>(lv_display_get_user_data(display));
        const unsigned back=1-self->front,width=area->x2-area->x1+1;
        const size_t page=self->fixed.line_length*720;
        for(int y=area->y1;y<=area->y2;++y)std::memcpy(self->memory+back*page+y*self->fixed.line_length+area->x1*4,pixels+(y-area->y1)*width*4,width*4);
        self->dirty.push_back(*area);
        if(lv_display_flush_is_last(display)) {
            self->variable.yoffset=back*720;
            if(ioctl(self->fd,FBIOPAN_DISPLAY,&self->variable)){std::perror("HDMI page flip failed");std::exit(1);}
            for(const auto& rect:self->dirty)for(int y=rect.y1;y<=rect.y2;++y) {
                const size_t offset=y*self->fixed.line_length+rect.x1*4;
                std::memcpy(self->memory+self->front*page+offset,self->memory+back*page+offset,(rect.x2-rect.x1+1)*4);
            }
            self->front=back;self->dirty.clear();
        }
        lv_display_flush_ready(display);
    }
public:
    Framebuffer() {
        fd=open("/dev/fb0",O_RDWR|O_CLOEXEC);
        if(fd<0 || ioctl(fd,FBIOGET_FSCREENINFO,&fixed) || ioctl(fd,FBIOGET_VSCREENINFO,&variable))throw std::runtime_error("Cannot open HDMI framebuffer");
        if(variable.xres!=1280 || variable.yres!=720 || variable.yres_virtual<1440 || variable.bits_per_pixel!=32 || variable.red.offset!=16 || variable.green.offset!=8 || variable.blue.offset!=0 || fixed.smem_len<fixed.line_length*1440)throw std::runtime_error("HDMI framebuffer must support 720p XRGB8888 page flips");
        memory=static_cast<uint8_t*>(mmap(nullptr,fixed.smem_len,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));if(memory==MAP_FAILED)throw std::runtime_error("Cannot map HDMI framebuffer");
        front=variable.yoffset/720;draw_a.resize(1280*40*4);draw_b.resize(draw_a.size());
        auto display=lv_display_create(1280,720);lv_display_set_color_format(display,LV_COLOR_FORMAT_XRGB8888);lv_display_set_user_data(display,this);lv_display_set_flush_cb(display,flush);lv_display_set_buffers(display,draw_a.data(),draw_b.data(),draw_a.size(),LV_DISPLAY_RENDER_MODE_PARTIAL);
    }
    ~Framebuffer(){if(memory && memory!=MAP_FAILED)munmap(memory,fixed.smem_len);if(fd>=0)close(fd);}
};
