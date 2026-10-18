// SPDX-License-Identifier: GPL-2.0
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/miscdevice.h>
#include <linux/dma-mapping.h>
#include <linux/fs.h>
#include <linux/mm.h>
#include <linux/uaccess.h>
#include <linux/clk.h>
#include <linux/of.h>
#include "vision_uapi.h"

struct vision_device {
    struct miscdevice misc;
    struct device *dev;
    void *buffer;
    dma_addr_t bus;
    struct resource *registers[3];
    atomic_t opened;
};
static int vision_open(struct inode *inode, struct file *file)
{
    struct vision_device *v=container_of(file->private_data,struct vision_device,misc);
    if(atomic_cmpxchg(&v->opened,0,1)) return -EBUSY;
    file->private_data=v;
    return 0;
}
static int vision_release(struct inode *inode, struct file *file)
{
    struct vision_device *v=file->private_data;
    atomic_set(&v->opened,0);
    return 0;
}
static long vision_ioctl(struct file *file,unsigned int command,unsigned long argument)
{
    struct vision_device *v=file->private_data;
    struct vision_dma_info info={.address=v->bus,.bytes=VISION_BUFFER_BYTES};
    if(command!=VISION_DMA_INFO) return -ENOTTY;
    return copy_to_user((void __user *)argument,&info,sizeof(info))?-EFAULT:0;
}
static int vision_mmap(struct file *file,struct vm_area_struct *area)
{
    struct vision_device *v=file->private_data;
    unsigned long offset=area->vm_pgoff<<PAGE_SHIFT,size=area->vm_end-area->vm_start;
    int index;
    if(area->vm_flags&VM_EXEC) return -EPERM;
    vm_flags_clear(area,VM_MAYEXEC);
    if(!offset) {
        if(size!=VISION_BUFFER_BYTES) return -EINVAL;
        return dma_mmap_coherent(v->dev,area,v->buffer,v->bus,VISION_BUFFER_BYTES);
    }
    if(offset==VISION_MAP_GPIO) index=0;
    else if(offset==VISION_MAP_CAPTURE) index=1;
    else if(offset==VISION_MAP_CONV) index=2;
    else return -EINVAL;
    if(size>resource_size(v->registers[index])) return -EINVAL;
    area->vm_page_prot=pgprot_noncached(area->vm_page_prot);
    area->vm_pgoff=0;
    return vm_iomap_memory(area,v->registers[index]->start,resource_size(v->registers[index]));
}
static const struct file_operations vision_operations={
    .owner=THIS_MODULE,.open=vision_open,.release=vision_release,
    .unlocked_ioctl=vision_ioctl,.compat_ioctl=vision_ioctl,.mmap=vision_mmap,.llseek=no_llseek,
};
static int vision_probe(struct platform_device *pdev)
{
    static const char *names[]={"gpio","capture","conv"};
    struct vision_device *v;
    int i,error;
    struct clk *clock;
    v=devm_kzalloc(&pdev->dev,sizeof(*v),GFP_KERNEL);
    if(!v)return -ENOMEM;
    v->dev=&pdev->dev;
    clock=devm_clk_get_enabled(v->dev,NULL);if(IS_ERR(clock))return dev_err_probe(v->dev,PTR_ERR(clock),"Cannot enable accelerator clock\n");
    error=dma_set_mask_and_coherent(v->dev,DMA_BIT_MASK(32));if(error)return error;
    for(i=0;i<3;++i) {
        v->registers[i]=platform_get_resource_byname(pdev,IORESOURCE_MEM,names[i]);
        if(!v->registers[i])return -EINVAL;
        if(!devm_request_mem_region(v->dev,v->registers[i]->start,resource_size(v->registers[i]),"vision-accel"))return -EBUSY;
    }
    v->buffer=dma_alloc_coherent(v->dev,VISION_BUFFER_BYTES,&v->bus,GFP_KERNEL);
    if(!v->buffer)return -ENOMEM;
    v->misc=(struct miscdevice){.minor=MISC_DYNAMIC_MINOR,.name="vision-accel",.fops=&vision_operations,.mode=0600,.parent=v->dev};
    error=misc_register(&v->misc);
    if(error){dma_free_coherent(v->dev,VISION_BUFFER_BYTES,v->buffer,v->bus);return error;}
    platform_set_drvdata(pdev,v);
    return 0;
}
static int vision_remove(struct platform_device *pdev)
{
    struct vision_device *v=platform_get_drvdata(pdev);
    // This appliance driver stays loaded until shutdown; do not unbind live DMA.
    if(atomic_read(&v->opened))return -EBUSY;
    misc_deregister(&v->misc);
    dma_free_coherent(v->dev,VISION_BUFFER_BYTES,v->buffer,v->bus);
    return 0;
}
static const struct of_device_id vision_matches[]={{.compatible="cnn,vision-accel-v1"},{}};
MODULE_DEVICE_TABLE(of,vision_matches);
static struct platform_driver vision_driver={.probe=vision_probe,.remove=vision_remove,.driver={.name="vision-accel",.of_match_table=vision_matches,.suppress_bind_attrs=true}};
module_platform_driver(vision_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Exclusive DMA memory and register mapping for CNN vision terminal");
