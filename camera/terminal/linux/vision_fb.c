// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/fb.h>
#include <linux/dma-mapping.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/clk.h>
#include <linux/of.h>
#include <linux/mm.h>

#define WIDTH 1280
#define HEIGHT 720
#define STRIDE (WIDTH*2)
#define PAGE_BYTES (HEIGHT*STRIDE)
struct vision_fb { struct device *dev; void __iomem *vdma; void *buffer; dma_addr_t bus; struct fb_info *info; };
static int vision_pan(struct fb_var_screeninfo *var,struct fb_info *info)
{
    struct vision_fb *v=info->par;
    u32 park_status,target;
    if(var->xoffset || (var->yoffset!=0 && var->yoffset!=HEIGHT))return -EINVAL;
    target=var->yoffset/HEIGHT;
    dma_wmb();
    writel((readl(v->vdma+0x28)&~31u)|target,v->vdma+0x28);
    return readl_poll_timeout(v->vdma+0x28,park_status,((park_status>>16)&31)==target,100,100000);
}
static int vision_check_var(struct fb_var_screeninfo *var,struct fb_info *info)
{
    if(var->xres!=WIDTH || var->yres!=HEIGHT || var->xres_virtual!=WIDTH || var->yres_virtual!=2*HEIGHT || var->bits_per_pixel!=16 || var->xoffset || (var->yoffset!=0 && var->yoffset!=HEIGHT))return -EINVAL;
    return 0;
}
static int vision_fb_mmap(struct fb_info *info,struct vm_area_struct *area)
{
    struct vision_fb *v=info->par;
    if(area->vm_flags&VM_EXEC)return -EPERM;
    vm_flags_clear(area,VM_MAYEXEC);
    return dma_mmap_wc(v->dev,area,v->buffer,v->bus,2*PAGE_BYTES);
}
static const struct fb_ops vision_fb_ops={.owner=THIS_MODULE,.fb_check_var=vision_check_var,.fb_pan_display=vision_pan,.fb_mmap=vision_fb_mmap,.fb_fillrect=sys_fillrect,.fb_copyarea=sys_copyarea,.fb_imageblit=sys_imageblit,.fb_read=fb_sys_read,.fb_write=fb_sys_write};
static int vision_fb_probe(struct platform_device *pdev)
{
    struct fb_info *info;
    struct vision_fb *v;
    u32 control;
    int error;
    struct clk *clock;
    clock=devm_clk_get_enabled(&pdev->dev,"axi");if(IS_ERR(clock))return dev_err_probe(&pdev->dev,PTR_ERR(clock),"Cannot enable display AXI clock\n");
    clock=devm_clk_get_enabled(&pdev->dev,"video");if(IS_ERR(clock))return dev_err_probe(&pdev->dev,PTR_ERR(clock),"Cannot enable display pixel source clock\n");
    error=dma_set_mask_and_coherent(&pdev->dev,DMA_BIT_MASK(32));if(error)return error;
    info=framebuffer_alloc(sizeof(*v),&pdev->dev);if(!info)return -ENOMEM;
    v=info->par;v->dev=&pdev->dev;v->info=info;
    v->vdma=devm_platform_ioremap_resource(pdev,0);if(IS_ERR(v->vdma)){error=PTR_ERR(v->vdma);goto fail;}
    v->buffer=dma_alloc_wc(v->dev,2*PAGE_BYTES,&v->bus,GFP_KERNEL);if(!v->buffer){error=-ENOMEM;goto fail;}
    memset(v->buffer,0,2*PAGE_BYTES);
    strscpy(info->fix.id,"vision-720p",sizeof(info->fix.id));info->fix.type=FB_TYPE_PACKED_PIXELS;info->fix.visual=FB_VISUAL_TRUECOLOR;
    info->fix.smem_start=v->bus;info->fix.smem_len=2*PAGE_BYTES;info->fix.line_length=STRIDE;info->fix.ypanstep=HEIGHT;
    info->var=(struct fb_var_screeninfo){.xres=WIDTH,.yres=HEIGHT,.xres_virtual=WIDTH,.yres_virtual=2*HEIGHT,.bits_per_pixel=16,.red={11,5,0},.green={5,6,0},.blue={0,5,0},.pixclock=13468,.left_margin=220,.right_margin=110,.upper_margin=20,.lower_margin=5,.hsync_len=40,.vsync_len=5,.sync=FB_SYNC_HOR_HIGH_ACT|FB_SYNC_VERT_HIGH_ACT,.vmode=FB_VMODE_NONINTERLACED};
    info->screen_base=v->buffer;info->screen_size=2*PAGE_BYTES;info->fbops=&vision_fb_ops;info->flags=0;
    info->pseudo_palette=devm_kcalloc(v->dev,16,sizeof(u32),GFP_KERNEL);if(!info->pseudo_palette){error=-ENOMEM;goto free_dma;}
    writel(4,v->vdma);error=readl_poll_timeout(v->vdma,control,!(control&4),100,100000);if(error)goto free_dma;
    writel(0xffffffff,v->vdma+4);writel(0,v->vdma+0x28);writel(1,v->vdma);
    writel(v->bus,v->vdma+0x5c);writel(v->bus+PAGE_BYTES,v->vdma+0x60);writel(STRIDE,v->vdma+0x58);writel(STRIDE,v->vdma+0x54);writel(HEIGHT,v->vdma+0x50);
    error=register_framebuffer(info);if(error)goto stop_dma;
    platform_set_drvdata(pdev,v);return 0;
stop_dma:writel(4,v->vdma);
free_dma:dma_free_wc(v->dev,2*PAGE_BYTES,v->buffer,v->bus);
fail:framebuffer_release(info);return error;
}
static int vision_fb_remove(struct platform_device *pdev)
{
    struct vision_fb *v=platform_get_drvdata(pdev);
    unregister_framebuffer(v->info);writel(4,v->vdma);dma_free_wc(v->dev,2*PAGE_BYTES,v->buffer,v->bus);framebuffer_release(v->info);return 0;
}
static const struct of_device_id vision_fb_matches[]={{.compatible="cnn,vision-fb-720p-v1"},{}};
MODULE_DEVICE_TABLE(of,vision_fb_matches);
static struct platform_driver vision_fb_driver={.probe=vision_fb_probe,.remove=vision_fb_remove,.driver={.name="vision-fb",.of_match_table=vision_fb_matches,.suppress_bind_attrs=true}};
module_platform_driver(vision_fb_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fixed 720p RGB565 double-buffer VDMA framebuffer for vision terminal");
