#pragma once
#include <cstdint>
#include "model.h"
struct ModelHeader {
    uint32_t magic, format, weight_size, metadata_size, generation, committed;
    char version[64];
    uint8_t sha256[32];
    uint32_t crc32, reserved;
};
static_assert(sizeof(ModelHeader)==128,"Model header size");
struct ModelReply {
    uint32_t magic, request, result, received, total, generation, flags;
    char version[64];
    uint8_t sha256[32];
};
static_assert(sizeof(ModelReply)==124,"Model reply size");
// SD 模型库：槽位 0:/M00.BIN .. 0:/M15.BIN，上传中 0:/TMP.BIN，当前/上一版指针 0:/ACTIVE.BIN。
// 回包 flags 的低 8 位是固定状态位，高位按操作解释：
//   bit0 mounted、bit1 有可用模型、bit2 已校验待提交、bit3 可用且不在自检中、bit4 忙
//   bits8-15 sd_result(FRESULT)、bits16-23 last_error
//   op0：received=当前槽号(0xffffffff 表示无)，total=库容量
//   op7：received=槽号，total=库内条目数，bit5=该条目是当前版本，bit6=该条目是上一版
extern "C" { extern int8_t weights[]; extern int32_t metadata[]; extern const int32_t commands[]; }
void model_store_init();
bool model_available();
bool model_test_pending();
void model_service();
void model_complete_test(bool passed);
ModelReply model_request(uint32_t request,uint32_t operation,uint32_t offset,const uint8_t* data,uint32_t size);
