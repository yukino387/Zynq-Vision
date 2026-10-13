#pragma once
#include "std_conv.h"
#include "maxpool.h"
#include "upsample.h"
void conv(const uint64_t*,const uint64_t*,const uint64_t*,const uint64_t*,const uint64_t*,const uint64_t*,const uint64_t*,const uint64_t*,
          int32_t*,uint64_t*,uint64_t*,uint64_t*,uint64_t*,int,int,int,int,int,int);
