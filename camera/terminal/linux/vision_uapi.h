#pragma once
#include <linux/ioctl.h>
#include <linux/types.h>
struct vision_dma_info { __u64 address; __u64 bytes; };
#define VISION_DMA_INFO _IOR('V', 1, struct vision_dma_info)
#define VISION_BUFFER_BYTES (16u*1024u*1024u)
#define VISION_MAP_GPIO 0x10000u
#define VISION_MAP_CAPTURE 0x20000u
#define VISION_MAP_CONV 0x30000u
