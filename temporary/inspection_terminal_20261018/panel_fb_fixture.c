#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
static int framebuffer=-1;
int fixture_open(const char *path,int flags,...) {
    static int (*original)(const char*,int,...);
    if(!original)original=dlsym(RTLD_NEXT,"open");
    mode_t mode=0;
    if(flags&O_CREAT){va_list args;va_start(args,flags);mode=va_arg(args,int);va_end(args);}
    if(strcmp(path,"/dev/fb0")==0){framebuffer=original("/workspace/temporary/inspection_terminal_20261018/panel-fb.bin",O_RDWR|O_CREAT,0600);ftruncate(framebuffer,1280*720*4*2);return framebuffer;}
    return original(path,flags,mode);
}
__asm__(".globl open\n.set open,fixture_open\n.globl open64\n.set open64,fixture_open");
int fixture_ioctl(int fd,unsigned long command,...) {
    static int (*original)(int,unsigned long,...);
    if(!original)original=dlsym(RTLD_NEXT,"ioctl");
    va_list args;va_start(args,command);void *arg=va_arg(args,void*);va_end(args);
    if(fd!=framebuffer)return original(fd,command,arg);
    if(command==FBIOGET_FSCREENINFO){struct fb_fix_screeninfo *v=arg;memset(v,0,sizeof(*v));v->smem_len=1280*720*4*2;v->line_length=1280*4;return 0;}
    if(command==FBIOGET_VSCREENINFO){struct fb_var_screeninfo *v=arg;memset(v,0,sizeof(*v));v->xres=1280;v->yres=720;v->xres_virtual=1280;v->yres_virtual=1440;v->bits_per_pixel=32;v->red.offset=16;v->green.offset=8;return 0;}
    if(command==FBIOPAN_DISPLAY)return 0;
    return -1;
}
__asm__(".globl ioctl\n.set ioctl,fixture_ioctl\n.globl __ioctl_time64\n.set __ioctl_time64,fixture_ioctl");
