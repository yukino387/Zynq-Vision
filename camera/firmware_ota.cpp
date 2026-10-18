#include "firmware_ota.h"
#include "firmware_qspi.h"
#include "int8/sha256.h"
#include "xscuwdt.h"
#include "xparameters.h"
#include "xil_io.h"
#include "xiltimer.h"
#include "sleep.h"
#include "udp_output.h"
#include <cstddef>
#include <cstring>

#if defined(__has_include)
#if __has_include("firmware_version.h")
#include "firmware_version.h"
#endif
#endif
#ifndef FIRMWARE_VERSION
#define FIRMWARE_VERSION "dev"
#endif

/* PS 应用 OTA：网络接收、SHA/CRC 校验、非活动槽写入、记录提交和软复位。
 * UDP 回调只做 DDR 拷贝；QSPI 擦写只在 firmware_service() 的主循环中执行。 */

static struct FirmwareRecord record;
static uint8_t fw_stage[FW_SLOT_SIZE] __attribute__((aligned(64)));
static uint32_t received, total;
static uint32_t stage;
static uint32_t rollback_target;
static bool qspi_ok, writing, verified, busy_guard, trial;
static volatile bool verify_requested, commit_requested, rollback_requested;
static bool reboot_pending;
static XTime reboot_at;
static uint32_t running_slot = FW_SLOT_GOLDEN;
static struct FirmwarePackageHeader package;
static bool package_valid;
static XScuWdt watchdog;
static bool watchdog_ok;

static uint32_t crc_update(uint32_t value, const void* data, uint32_t size) {
    const uint8_t* bytes = static_cast<const uint8_t*>(data);
    while (size--) {
        value ^= *bytes++;
        for (unsigned bit = 0; bit < 8; ++bit)
            value = (value >> 1) ^
                    (0xEDB88320u & uint32_t(-int32_t(value & 1u)));
    }
    return value;
}

static void copy_text(char* destination, const char* source) {
    std::memset(destination, 0, FW_MAX_VERSION);
    std::memcpy(destination, source, std::strlen(source) < FW_MAX_VERSION
                                         ? std::strlen(source)
                                         : FW_MAX_VERSION);
}

static void watchdog_start() {
    XScuWdt_Config* config = XScuWdt_LookupConfig(XPAR_XSCUWDT_0_BASEADDR);
    if (!config) return;
    if (XScuWdt_CfgInitialize(&watchdog, config, config->BaseAddr) != XST_SUCCESS)
        return;
    XScuWdt_LoadWdt(&watchdog, (XPAR_CPU_CORE_CLOCK_FREQ_HZ / 2u) * 10u);
    XScuWdt_Start(&watchdog);
    watchdog_ok = true;
}

void firmware_watchdog_kick() {
    if (watchdog_ok) XScuWdt_RestartWdt(&watchdog);
}

static bool record_valid(const FirmwareRecord* value) {
    return value->magic == FW_RECORD_MAGIC &&
           value->format == FW_RECORD_FORMAT &&
           value->crc32 ==
               fw_crc32(value, offsetof(struct FirmwareRecord, crc32));
}

static bool record_read_copy(uint32_t offset, FirmwareRecord* out) {
    std::memset(out, 0, sizeof(*out));
    return firmware_qspi_read(offset, out, FW_RECORD_SIZE) &&
           record_valid(out);
}

static bool record_write(FirmwareRecord* value) {
    FirmwareRecord copies[2];
    bool valid[2];
    valid[0] = record_read_copy(FW_RECORD_A_OFFSET, &copies[0]);
    valid[1] = record_read_copy(FW_RECORD_B_OFFSET, &copies[1]);
    uint32_t target = !valid[0] ? 0 : !valid[1] ? 1
                     : (copies[0].seq <= copies[1].seq ? 0 : 1);
    uint32_t seq = 0;
    if (valid[0] && copies[0].seq > seq) seq = copies[0].seq;
    if (valid[1] && copies[1].seq > seq) seq = copies[1].seq;
    value->magic = FW_RECORD_MAGIC;
    value->format = FW_RECORD_FORMAT;
    value->seq = seq + 1;
    value->reserved = 0;
    value->crc32 = fw_crc32(value, offsetof(struct FirmwareRecord, crc32));
    const uint32_t offset =
        target == 0 ? FW_RECORD_A_OFFSET : FW_RECORD_B_OFFSET;
    if (!firmware_qspi_erase_4k(offset)) return false;
    if (!firmware_qspi_program(offset, value, FW_RECORD_SIZE)) return false;
    return firmware_qspi_verify(offset, value, FW_RECORD_SIZE);
}

static uint32_t running_slot_from_record() {
    if (record.active == 0 || record.active == 1) {
        if (std::strncmp(record.version[record.active], FIRMWARE_VERSION,
                         FW_MAX_VERSION) == 0)
            return record.active;
    }
    return FW_SLOT_GOLDEN;
}

void firmware_init() {
    watchdog_start();
    qspi_ok = firmware_qspi_init();
    std::memset(&record, 0, sizeof(record));
    std::memset(&package, 0, sizeof(package));
    received = total = 0;
    stage = FW_STAGE_IDLE;
    writing = verified = busy_guard = trial = false;
    verify_requested = commit_requested = rollback_requested = false;
    reboot_pending = false;
    package_valid = false;
    if (!qspi_ok) {
        running_slot = FW_SLOT_GOLDEN;
        return;
    }

    FirmwareRecord a, b;
    const bool va = record_read_copy(FW_RECORD_A_OFFSET, &a);
    const bool vb = record_read_copy(FW_RECORD_B_OFFSET, &b);
    if (!va && !vb) {
        record.state = FW_STATE_CONFIRMED;
        record.active = FW_SLOT_GOLDEN;
        record.previous = FW_SLOT_NONE;
        record.pending = FW_SLOT_NONE;
        record.max_attempts = FW_MAX_ATTEMPTS;
        record.flags = FW_RECORD_FLAG_INITIALIZED;
        record_write(&record);
    } else {
        record = (va && (!vb || a.seq >= b.seq)) ? a : b;
    }
    if (record.max_attempts == 0) record.max_attempts = FW_MAX_ATTEMPTS;

    if (record.pending != FW_SLOT_NONE) {
        if (record.pending <= 1 &&
            std::strncmp(record.version[record.pending], FIRMWARE_VERSION,
                         FW_MAX_VERSION) == 0) {
            trial = true;
            running_slot = record.pending;
        } else {
            record.pending = FW_SLOT_NONE;
            record.state = FW_STATE_FAILED;
            record_write(&record);
        }
    }
    if (!trial) running_slot = running_slot_from_record();
    stage = FW_STAGE_IDLE;
}

static bool verify_package() {
    if (total < FW_PACKAGE_HEADER_SIZE + FW_SEGMENT_SIZE ||
        total > FW_SLOT_SIZE)
        return false;
    package = *reinterpret_cast<FirmwarePackageHeader*>(fw_stage);
    const uint32_t count = package.segment_count;
    if (count < 1 || count > FW_MAX_SEGMENTS) return false;
    const uint32_t header_size =
        FW_PACKAGE_HEADER_SIZE + count * FW_SEGMENT_SIZE;
    if (package.magic != FW_PACKAGE_MAGIC ||
        package.format != FW_PACKAGE_FORMAT ||
        package.header_size != header_size ||
        package.entry != FW_APP_ENTRY ||
        package.load_addr != FW_APP_ENTRY ||
        package.image_size == 0 ||
        package.image_size > FW_PACKAGE_MAX_SIZE ||
        header_size + package.image_size != total ||
        package.version_len < 1 ||
        package.version_len >= FW_MAX_VERSION ||
        package.version[package.version_len] != 0)
        return false;

    uint32_t crc = 0xFFFFFFFFu;
    crc = crc_update(crc, fw_stage, 36);
    crc = crc_update(crc, fw_stage + 40, 88);
    crc = crc_update(crc, fw_stage + FW_PACKAGE_HEADER_SIZE,
                     count * FW_SEGMENT_SIZE);
    if (~crc != package.header_crc32) return false;

    FirmwareSegment* segments =
        reinterpret_cast<FirmwareSegment*>(fw_stage + FW_PACKAGE_HEADER_SIZE);
    uint32_t payload_offset = 0, previous_end = 0;
    for (uint32_t i = 0; i < count; ++i) {
        const FirmwareSegment* segment = &segments[i];
        if (segment->size == 0 || segment->offset != payload_offset)
            return false;
        if (segment->paddr < FW_APP_ENTRY ||
            segment->paddr >= FW_APP_LIMIT ||
            segment->size > FW_APP_LIMIT - segment->paddr)
            return false;
        if (i && segment->paddr < previous_end) return false;
        previous_end = segment->paddr + segment->size;
        payload_offset += segment->size;
        if (payload_offset > package.image_size) return false;
    }
    if (payload_offset != package.image_size) return false;

    const uint8_t* payload = fw_stage + header_size;
    if (fw_crc32(payload, package.image_size) != package.payload_crc32)
        return false;
    Sha256 sha;
    sha.update(payload, package.image_size);
    uint8_t digest[32];
    sha.finish(digest);
    if (std::memcmp(digest, package.sha256, 32) != 0) return false;
    package_valid = true;
    return true;
}

static bool write_slot() {
    if (!package_valid) return false;
    const uint32_t target_slot = record.active == 0 ? 1 : 0;
    const uint32_t target_offset =
        target_slot == 0 ? FW_SLOT_A_OFFSET : FW_SLOT_B_OFFSET;
    const uint32_t erase_size = (total + 0xFFFFu) & ~0xFFFFu;
    if (erase_size > FW_SLOT_SIZE) return false;

    for (uint32_t offset = 0; offset < erase_size; offset += 0x10000u) {
        firmware_watchdog_kick();
        if (!firmware_qspi_erase_64k(target_offset + offset)) return false;
    }
    if (!firmware_qspi_program(target_offset, fw_stage, total)) return false;
    if (!firmware_qspi_verify(target_offset, fw_stage, total)) return false;

    FirmwareRecord next = record;
    next.pending = target_slot;
    next.active = record.active;
    next.previous = record.active;
    next.state = FW_STATE_TRIAL;
    next.attempts = 0;
    next.max_attempts = FW_MAX_ATTEMPTS;
    next.slot_offset[target_slot] = target_offset;
    next.slot_size[target_slot] = FW_SLOT_SIZE;
    /* The record stores the payload size, matching the package header; the
     * filesystem slot also contains the 128B header and segment table. */
    next.image_size[target_slot] = package.image_size;
    next.image_crc32[target_slot] = package.payload_crc32;
    std::memcpy(next.sha256[target_slot], package.sha256, 32);
    std::memcpy(next.version[target_slot], package.version, FW_MAX_VERSION);
    if (!record_write(&next)) return false;
    record = next;
    return true;
}

static bool write_rollback() {
    /* 0 = previous slot (or golden when none), 2 = golden explicitly. */
    uint32_t target = rollback_target;
    if (target == 0)
        target = (record.previous == 0 || record.previous == 1)
                     ? record.previous
                     : FW_SLOT_GOLDEN;
    if (target > 1) target = FW_SLOT_GOLDEN;
    if (target <= 1 && record.version[target][0] == 0) return false;
    FirmwareRecord next = record;
    next.active = target;
    next.previous = record.active;
    next.pending = FW_SLOT_NONE;
    next.state = FW_STATE_CONFIRMED;
    next.attempts = 0;
    if (!record_write(&next)) return false;
    record = next;
    running_slot = target;
    return true;
}

static void reset_board() {
    Xil_Out32(0xF8000008, 0xDF0D); /* SLCR unlock */
    Xil_Out32(0xF8000200, 1);      /* PSS_RST_CTRL */
    for (;;) {
    }
}

void firmware_service() {
    firmware_watchdog_kick();
    if (verify_requested) {
        verify_requested = false;
        busy_guard = true;
        stage = FW_STAGE_VERIFYING;
        verified = verify_package();
        stage = verified ? FW_STAGE_READY : FW_STAGE_IDLE;
        busy_guard = false;
    }
    if (commit_requested) {
        commit_requested = false;
        if (verified) {
            busy_guard = true;
            stage = FW_STAGE_ERASING;
            if (write_slot()) {
                stage = FW_STAGE_REBOOT_PENDING;
                reboot_pending = true;
                XTime_GetTime(&reboot_at);
                reboot_at += COUNTS_PER_SECOND;
            } else {
                stage = FW_STAGE_IDLE;
                verified = false;
                package_valid = false;
            }
            busy_guard = false;
        }
    }
    if (rollback_requested) {
        rollback_requested = false;
        busy_guard = true;
        if (write_rollback()) {
            stage = FW_STAGE_REBOOT_PENDING;
            reboot_pending = true;
            XTime_GetTime(&reboot_at);
            reboot_at += COUNTS_PER_SECOND;
        } else {
            stage = FW_STAGE_IDLE;
        }
        busy_guard = false;
    }
    if (reboot_pending) {
        XTime now;
        XTime_GetTime(&now);
        if (now >= reboot_at) reset_board();
    }
}

bool firmware_busy() {
    return writing || busy_guard || verify_requested || commit_requested ||
           rollback_requested || reboot_pending || trial;
}

bool firmware_trial_pending() { return trial; }

void firmware_confirm_ok() {
    if (!trial) return;
    FirmwareRecord next = record;
    next.active = record.pending;
    next.pending = FW_SLOT_NONE;
    next.state = FW_STATE_CONFIRMED;
    next.attempts = 0;
    if (record_write(&next)) record = next;
    running_slot = record.active;
    trial = false;
}

void firmware_confirm_fail() {
    if (!trial) return;
    FirmwareRecord next = record;
    next.pending = FW_SLOT_NONE;
    next.state = FW_STATE_FAILED;
    if (record_write(&next)) record = next;
    trial = false;
    reboot_pending = true;
    XTime_GetTime(&reboot_at);
    reboot_at += COUNTS_PER_SECOND;
}

const char* firmware_version() { return FIRMWARE_VERSION; }
uint32_t firmware_running_slot() { return running_slot; }

static FirmwareReply make_reply(uint32_t request) {
    FirmwareReply reply{};
    reply.magic = FW_REPLY_MAGIC;
    reply.request = request;
    reply.result = FW_RESULT_OK;
    reply.received = received;
    reply.total = total;
    reply.generation = record.seq;
    reply.running_slot = running_slot;
    reply.active_slot = record.active;
    reply.previous_slot = record.previous;
    reply.pending_slot = record.pending;
    reply.attempts = record.attempts;
    reply.max_attempts = record.max_attempts;
    reply.detail = stage;
    copy_text(reply.version, FIRMWARE_VERSION);
    if (running_slot < 2)
        std::memcpy(reply.sha256, record.sha256[running_slot], 32);
    reply.slot_a_image_size = record.image_size[0];
    reply.slot_b_image_size = record.image_size[1];
    if (qspi_ok) reply.flags |= FW_FLAG_SUPPORTED;
    if (writing) reply.flags |= FW_FLAG_STAGED;
    if (verified) reply.flags |= FW_FLAG_VERIFIED;
    if (firmware_busy()) reply.flags |= FW_FLAG_BUSY;
    if (trial) reply.flags |= FW_FLAG_TRIAL;
    if (record.previous == 0 || record.previous == 1 ||
        record.active == 0 || record.active == 1)
        reply.flags |= FW_FLAG_ROLLBACK_AVAILABLE;
    if (record.active == FW_SLOT_GOLDEN) reply.flags |= FW_FLAG_GOLDEN_ACTIVE;
    if (reboot_pending) reply.flags |= FW_FLAG_REBOOT_PENDING;
    reply.flags |= (stage & 0xFFu) << 8;
    reply.crc32 = fw_crc32(&reply, offsetof(FirmwareReply, crc32));
    return reply;
}

FirmwareReply firmware_request(uint32_t request, uint32_t operation,
                               uint32_t offset, const uint8_t* data,
                               uint32_t size) {
    uint32_t result = FW_RESULT_OK;
    switch (operation) {
    case FW_OP_INFO:
        result = qspi_ok ? FW_RESULT_OK : FW_RESULT_UNUSABLE;
        break;
    case FW_OP_BEGIN:
        if (!qspi_ok)
            result = FW_RESULT_UNUSABLE;
        else if (offset != FW_ARM_TOKEN)
            result = FW_RESULT_NOT_ARMED;
        else if (size == 0 || size > FW_SLOT_SIZE)
            result = FW_RESULT_INVALID;
        else if (firmware_busy())
            result = FW_RESULT_BUSY;
        else {
            udp_pause();
            received = 0;
            total = size;
            writing = true;
            verified = false;
            package_valid = false;
            verify_requested = commit_requested = rollback_requested = false;
            stage = FW_STAGE_RECEIVING;
        }
        break;
    case FW_OP_DATA:
        if (!writing || size == 0 || size > 1400 || offset > received ||
            offset + size > total)
            result = FW_RESULT_INVALID;
        else {
            std::memcpy(fw_stage + offset, data, size);
            if (offset + size > received) received = offset + size;
        }
        break;
    case FW_OP_FINISH:
        if (!writing || received != total)
            result = FW_RESULT_INVALID;
        else {
            writing = false;
            verify_requested = true;
            stage = FW_STAGE_VERIFYING;
        }
        break;
    case FW_OP_COMMIT:
        if (!verified)
            result = FW_RESULT_INVALID;
        else {
            commit_requested = true;
            stage = FW_STAGE_READY;
        }
        break;
    case FW_OP_ROLLBACK:
        if (offset != 0 && offset != FW_SLOT_GOLDEN)
            result = FW_RESULT_INVALID;
        else if (offset == 0 && record.previous != 0 &&
                 record.previous != 1)
            result = FW_RESULT_NOT_FOUND;
        else {
            rollback_target = offset;
            rollback_requested = true;
            stage = FW_STAGE_READY;
        }
        break;
    case FW_OP_ABORT:
        writing = false;
        verified = false;
        received = total = 0;
        package_valid = false;
        verify_requested = commit_requested = rollback_requested = false;
        stage = FW_STAGE_IDLE;
        break;
    case FW_OP_LIST:
        if (offset > 2)
            result = FW_RESULT_INVALID;
        else {
            received = offset;
            total = offset < 2 ? record.image_size[offset] : 0;
            if (offset < 2 && record.version[offset][0])
                result = FW_RESULT_OK;
            else if (offset == FW_SLOT_GOLDEN)
                result = FW_RESULT_OK;
            else
                result = FW_RESULT_NOT_FOUND;
        }
        break;
    default:
        result = FW_RESULT_INVALID;
        break;
    }
    FirmwareReply reply = make_reply(request);
    reply.result = result;
    if (operation == FW_OP_LIST && offset < 2) {
        std::memcpy(reply.version, record.version[offset], FW_MAX_VERSION);
        std::memcpy(reply.sha256, record.sha256[offset], 32);
        reply.flags = (reply.flags & ~0xFF00u) | ((stage & 0xFFu) << 8);
        reply.flags |= 1u << 18;
        if (offset == record.active) reply.flags |= 1u << 16;
        if (offset == record.previous) reply.flags |= 1u << 17;
    }
    reply.received = received;
    reply.total = total;
    reply.crc32 = fw_crc32(&reply, offsetof(FirmwareReply, crc32));
    return reply;
}
