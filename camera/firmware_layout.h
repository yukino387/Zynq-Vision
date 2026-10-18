#pragma once
#include <stdint.h>
#include <stddef.h>

/* PS 应用 OTA：QSPI 布局、固件记录、应用包和网络协议的唯一事实来源。
 * FSBL、应用和 host 侧打包脚本必须保持这些偏移和常量一致。
 * 所有槽位和记录严格位于 16MiB 可启动窗口内。 */

#define FW_RECORD_MAGIC        0x31524657u  /* "WFR1" */
#define FW_RECORD_FORMAT       1u
#define FW_RECORD_SIZE         256u
#define FW_RECORD_A_OFFSET     0x007FE000u
#define FW_RECORD_B_OFFSET     0x007FF000u
#define FW_SLOT_A_OFFSET       0x00800000u
#define FW_SLOT_B_OFFSET       0x00C00000u
#define FW_SLOT_SIZE           0x00400000u
#define FW_SLOT_NONE           0xFFFFFFFFu
#define FW_SLOT_GOLDEN         2u
#define FW_MAX_ATTEMPTS        3u
#define FW_MAX_VERSION         56u

#define FW_STATE_CONFIRMED     0u
#define FW_STATE_TRIAL         1u
#define FW_STATE_FAILED        2u
#define FW_STATE_IDLE          3u

#define FW_PACKAGE_MAGIC       0x31474B50u  /* "PKG1" */
#define FW_PACKAGE_FORMAT      1u
#define FW_PACKAGE_HEADER_SIZE 128u
#define FW_SEGMENT_SIZE        16u
#define FW_MAX_SEGMENTS        4u
#define FW_APP_ENTRY           0x00100000u
#define FW_APP_LIMIT           0x00200000u
#define FW_PACKAGE_MAX_SIZE    0x00400000u

struct FirmwareRecord {
    uint32_t magic;
    uint32_t format;
    uint32_t seq;
    uint32_t state;
    uint32_t active;
    uint32_t previous;
    uint32_t pending;
    uint32_t attempts;
    uint32_t max_attempts;
    uint32_t flags;
    uint32_t slot_offset[2];
    uint32_t slot_size[2];
    uint32_t image_size[2];
    uint32_t image_crc32[2];
    uint8_t  sha256[2][32];
    char     version[2][FW_MAX_VERSION];
    uint32_t crc32;
    uint32_t reserved;
};

#define FW_RECORD_FLAG_INITIALIZED 0x00000001u

struct FirmwarePackageHeader {
    uint32_t magic;
    uint32_t format;
    uint32_t header_size;   /* 128 + 16 * segment_count */
    uint32_t entry;         /* 必须为 FW_APP_ENTRY */
    uint32_t load_addr;     /* 最小段地址，必须为 FW_APP_ENTRY */
    uint32_t image_size;    /* payload 字节数 */
    uint32_t segment_count; /* 1..FW_MAX_SEGMENTS */
    uint32_t version_len;   /* 1..55 */
    uint32_t payload_crc32;
    uint32_t header_crc32;  /* 覆盖 [0,36) + [40,128) + 段表 */
    uint8_t  sha256[32];    /* payload 的 SHA-256 */
    char     version[FW_MAX_VERSION];
};

struct FirmwareSegment {
    uint32_t paddr;
    uint32_t offset;        /* payload 内偏移，按 paddr 顺序连续 */
    uint32_t size;
    uint32_t flags;
};

/* 网络协议：复用 model 的 20 字节请求头和 1400 字节载荷上限，
 * 使用独立 magic，回复固定 160 字节。 */
#define FW_REQ_MAGIC       0x314D5246u  /* "FRM1" */
#define FW_REPLY_MAGIC     0x31524D46u  /* "FMR1" */
#define FW_REPLY_SIZE      160u
#define FW_ARM_TOKEN       0x41524D31u  /* "ARM1" */

enum {
    FW_OP_INFO = 0,
    FW_OP_BEGIN = 1,
    FW_OP_DATA = 2,
    FW_OP_FINISH = 3,
    FW_OP_COMMIT = 4,
    FW_OP_ROLLBACK = 5,
    FW_OP_ABORT = 6,
    FW_OP_LIST = 7
};

enum {
    FW_RESULT_OK = 0,
    FW_RESULT_INVALID = 1,
    FW_RESULT_BUSY = 2,
    FW_RESULT_STORAGE = 3,
    FW_RESULT_REJECTED = 4,
    FW_RESULT_FULL = 5,
    FW_RESULT_NOT_FOUND = 6,
    FW_RESULT_UNUSABLE = 7,
    FW_RESULT_PROTECTED = 8,
    FW_RESULT_NOT_ARMED = 9,
    FW_RESULT_ROLLED_BACK = 10
};

enum {
    FW_FLAG_SUPPORTED = 1u << 0,
    FW_FLAG_STAGED = 1u << 1,
    FW_FLAG_VERIFIED = 1u << 2,
    FW_FLAG_BUSY = 1u << 3,
    FW_FLAG_TRIAL = 1u << 4,
    FW_FLAG_ROLLBACK_AVAILABLE = 1u << 5,
    FW_FLAG_GOLDEN_ACTIVE = 1u << 6,
    FW_FLAG_REBOOT_PENDING = 1u << 7
};

enum {
    FW_STAGE_IDLE = 0,
    FW_STAGE_RECEIVING = 1,
    FW_STAGE_VERIFYING = 2,
    FW_STAGE_READY = 3,
    FW_STAGE_ERASING = 4,
    FW_STAGE_PROGRAMMING = 5,
    FW_STAGE_VERIFYING_FLASH = 6,
    FW_STAGE_WRITING_RECORD = 7,
    FW_STAGE_REBOOT_PENDING = 8,
    FW_STAGE_DONE = 9
};

struct FirmwareRequestHeader {
    uint32_t magic;
    uint32_t request;
    uint32_t operation;
    uint32_t offset;
    uint32_t size;
};

struct FirmwareReply {
    uint32_t magic;
    uint32_t request;
    uint32_t result;
    uint32_t received;
    uint32_t total;
    uint32_t generation;
    uint32_t flags;
    uint32_t running_slot;
    uint32_t active_slot;
    uint32_t previous_slot;
    uint32_t pending_slot;
    uint32_t attempts;
    uint32_t max_attempts;
    uint32_t detail;
    char     version[FW_MAX_VERSION];
    uint8_t  sha256[32];
    uint32_t slot_a_image_size;
    uint32_t slot_b_image_size;
    uint32_t crc32;         /* 覆盖 [0,152) */
    uint32_t reserved;
};

/* 与 model_store.cpp 相同的反射 CRC-32（多项式 0xEDB88320）。 */
static inline uint32_t fw_crc32(const void* data, uint32_t size) {
    const uint8_t* bytes = (const uint8_t*)data;
    uint32_t value = 0xFFFFFFFFu;
    while (size--) {
        value ^= *bytes++;
        for (unsigned bit = 0; bit < 8; ++bit)
            value = (value >> 1) ^ (0xEDB88320u & (uint32_t)(-(int32_t)(value & 1u)));
    }
    return ~value;
}
