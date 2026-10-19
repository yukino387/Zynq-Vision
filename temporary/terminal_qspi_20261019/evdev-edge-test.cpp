#include "lvgl.h"
#include <linux/input.h>
#include <unistd.h>
#include <cassert>
#include <cstdio>

int main() {
    lv_init();
    auto display=lv_display_create(1280,720);
    int descriptors[2];
    assert(pipe(descriptors)==0);
    auto input=lv_evdev_create_fd(LV_INDEV_TYPE_POINTER,descriptors[0]);
    assert(input);
    auto move=[&](int dx,int dy,int x,int y) {
        input_event events[3]{};
        events[0].type=EV_REL;events[0].code=REL_X;events[0].value=dx;
        events[1].type=EV_REL;events[1].code=REL_Y;events[1].value=dy;
        events[2].type=EV_SYN;events[2].code=SYN_REPORT;
        assert(write(descriptors[1],events,sizeof(events))==sizeof(events));
        lv_indev_read(input);
        lv_point_t point;lv_indev_get_point(input,&point);
        std::printf("MOVE %d %d -> %d %d expected %d %d\n",dx,dy,point.x,point.y,x,y);
        std::fflush(stdout);
        assert(point.x==x && point.y==y);
    };
    move(-5000,-5000,0,0);
    move(100,100,100,100);
    move(5000,5000,1279,719);
    move(-1,-1,1278,718);
    lv_evdev_delete(input);close(descriptors[1]);lv_display_delete(display);
    std::puts("EVDEV_EDGE_RECOVERY_PASSED");
}
