#include "firmware_qspi.h"
#include "xqspips.h"
#include "xparameters.h"
#include "xil_cache.h"
#include "xiltimer.h"
#include <cstring>

/* 应用侧 W25Q256 轮询驱动：只使用 16MiB 低 bank。
 * 与 camera/qspi_program.cpp 相同的 JEDEC/EAR/QE 处理，但不关闭全局 D-cache。 */

static XQspiPs qspi;
static uint8_t tx[4104] __attribute__((aligned(4)));
static uint8_t rx[4104] __attribute__((aligned(4)));

static bool transfer(unsigned count, bool receive = true) {
    return XQspiPs_PolledTransfer(&qspi, tx, receive ? rx : nullptr, count) ==
           XST_SUCCESS;
}

static bool idle(unsigned seconds) {
    XTime begin, now;
    XTime_GetTime(&begin);
    do {
        tx[0] = 0x05;
        tx[1] = 0;
        if (!transfer(2)) return false;
        if (!(rx[1] & 1)) return true;
        XTime_GetTime(&now);
    } while ((now - begin) < (XTime)seconds * COUNTS_PER_SECOND);
    return false;
}

static bool enable_write() {
    tx[0] = 0x06;
    if (!transfer(1, false)) return false;
    tx[0] = 0x05;
    tx[1] = 0;
    return transfer(2) && (rx[1] & 2);
}

static void address(uint8_t command, uint32_t offset) {
    tx[0] = command;
    tx[1] = uint8_t(offset >> 16);
    tx[2] = uint8_t(offset >> 8);
    tx[3] = uint8_t(offset);
}

bool firmware_qspi_init() {
    XQspiPs_Config* config = XQspiPs_LookupConfig(XPAR_XQSPIPS_0_BASEADDR);
    if (!config) return false;
    if (XQspiPs_CfgInitialize(&qspi, config, config->BaseAddress) != XST_SUCCESS)
        return false;
    XQspiPs_SetOptions(&qspi, XQSPIPS_MANUAL_START_OPTION |
                                  XQSPIPS_FORCE_SSELECT_OPTION |
                                  XQSPIPS_HOLD_B_DRIVE_OPTION);
    XQspiPs_SetClkPrescaler(&qspi, XQSPIPS_CLK_PRESCALE_8);
    XQspiPs_SetSlaveSelect(&qspi);

    tx[0] = 0x9F;
    tx[1] = tx[2] = tx[3] = 0;
    if (!transfer(4)) return false;
    const uint32_t jedec =
        (uint32_t(rx[1]) << 16) | (uint32_t(rx[2]) << 8) | rx[3];
    if (jedec != 0xEF4019) return false;

    /* W25Q256FV 可能在 4-byte 模式后保留 EAR=1；强制回到 BootROM 低 bank。 */
    tx[0] = 0xE9;
    if (!transfer(1, false)) return false;
    if (!enable_write()) return false;
    tx[0] = 0xC5;
    tx[1] = 0;
    if (!transfer(2, false) || !idle(1)) return false;
    tx[0] = 0x04;
    if (!transfer(1, false)) return false;
    tx[0] = 0xC8;
    tx[1] = 0;
    return transfer(2) && rx[1] == 0;
}

bool firmware_qspi_read(uint32_t offset, void* destination, uint32_t size) {
    uint8_t* out = static_cast<uint8_t*>(destination);
    while (size) {
        uint32_t count = size < 4096 ? size : 4096;
        address(0x03, offset);
        std::memset(tx + 4, 0, count);
        if (!transfer(count + 4)) return false;
        std::memcpy(out, rx + 4, count);
        offset += count;
        out += count;
        size -= count;
    }
    return true;
}

bool firmware_qspi_erase_4k(uint32_t offset) {
    if (!enable_write()) return false;
    address(0x20, offset);
    return transfer(4, false) && idle(2);
}

bool firmware_qspi_erase_64k(uint32_t offset) {
    if (!enable_write()) return false;
    address(0xD8, offset);
    return transfer(4, false) && idle(5);
}

bool firmware_qspi_program(uint32_t offset, const void* source, uint32_t size) {
    const uint8_t* data = static_cast<const uint8_t*>(source);
    Xil_DCacheFlushRange((INTPTR)source, size);
    while (size) {
        uint32_t count = size < 256 ? size : 256;
        if (!enable_write()) return false;
        address(0x02, offset);
        std::memcpy(tx + 4, data, count);
        if (!transfer(count + 4, false) || !idle(1)) return false;
        offset += count;
        data += count;
        size -= count;
    }
    return true;
}

bool firmware_qspi_verify(uint32_t offset, const void* source, uint32_t size) {
    const uint8_t* expected = static_cast<const uint8_t*>(source);
    while (size) {
        uint32_t count = size < 4096 ? size : 4096;
        address(0x03, offset);
        std::memset(tx + 4, 0, count);
        if (!transfer(count + 4)) return false;
        if (std::memcmp(rx + 4, expected, count) != 0) return false;
        offset += count;
        expected += count;
        size -= count;
    }
    return true;
}
