#include "camera_input.h"
#include "../hardware/camera/ov5640_registers.h"
#include "sleep.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "xil_printf.h"
#include "xiltimer.h"

static constexpr UINTPTR GPIO = 0x41200000;
static constexpr UINTPTR DMA = 0x40400000;
static uint32_t control = 3;
static void pin(unsigned mask, bool high)
{
    control = high ? control | mask : control & ~mask;
    Xil_Out32(GPIO, control);
    usleep(5);
}
static void start()
{
    pin(2, true);
    pin(1, true);
    pin(2, false);
    pin(1, false);
}
static void stop()
{
    pin(2, false);
    pin(1, true);
    pin(2, true);
}
static bool write_byte(uint8_t value)
{
    for (unsigned i = 0; i < 8; ++i)
    {
        pin(2, (value & 0x80) != 0);
        pin(1, true);
        pin(1, false);
        value <<= 1;
    }
    pin(2, true);
    pin(1, true);
    const bool ack = !(Xil_In32(GPIO + 8) & 1);
    pin(1, false);
    return ack;
}
static uint8_t read_byte()
{
    uint8_t value = 0;
    pin(2, true);
    for (unsigned i = 0; i < 8; ++i)
    {
        pin(1, true);
        value = static_cast<uint8_t>((value << 1) | (Xil_In32(GPIO + 8) & 1));
        pin(1, false);
    }
    pin(1, true);
    pin(1, false); // NACK: release SDA on the ninth clock.
    return value;
}
static bool write_register(uint16_t address, uint8_t value)
{
    start();
    const bool ok = write_byte(0x78) && write_byte(address >> 8) && write_byte(address & 255) &&
                    write_byte(value);
    stop();
    return ok;
}
static bool read_register(uint16_t address, uint8_t &value)
{
    start();
    bool ok = write_byte(0x78) && write_byte(address >> 8) && write_byte(address & 255);
    stop();
    if (!ok)
        return false;
    start();
    ok = write_byte(0x79);
    if (ok)
        value = read_byte();
    stop();
    return ok;
}

bool camera_init()
{
    Xil_Out32(GPIO + 4, 0);   // Channel 1: five control outputs.
    Xil_Out32(GPIO + 12, 15); // Channel 2: four status inputs.
    Xil_Out32(GPIO, control);
    usleep(20000);
    pin(8, false);
    usleep(5000);
    pin(4, true);
    usleep(20000);
    uint8_t high = 0, low = 0;
    if (!read_register(0x300a, high) || !read_register(0x300b, low) || high != 0x56 || low != 0x40)
    {
        xil_printf("OV5640 ID failed: %02x%02x\r\n", high, low);
        return false;
    }
    if (!write_register(0x3103, 0x11) || !write_register(0x3008, 0x82))
        return false;
    usleep(10000);
    for (const auto &reg : camera_registers)
    {
        if (!write_register(reg.address, reg.value))
        {
            xil_printf("OV5640 register failed: %04x\r\n", reg.address);
            return false;
        }
    }
    const struct
    {
        uint16_t address;
        uint8_t value;
    } output[] = {{0x3035, 0x11}, {0x3824, 0x04}, {0x3a00, 0x38},
                  {0x3a02, 0x00}, {0x3a03, 0x48}, {0x3a14, 0x00}, {0x3a15, 0x48},
                  {0x4300, 0x61}, {0x501f, 0x01}, {0x4740, 0x21}, {0x3808, 0x01},
                  {0x3809, 0xa0}, {0x380a, 0x01}, {0x380b, 0xa0}, {0x3008, 0x02}};
    for (const auto &reg : output)
    {
        uint8_t value = 0;
        if (!write_register(reg.address, reg.value) || !read_register(reg.address, value) ||
            value != reg.value)
            return false;
    }
    usleep(300000);
    xil_printf("OV5640 5640: RGB565 416x416\r\n");
    return true;
}

bool camera_begin(uint16_t *pixels)
{
    pin(16, false);
    Xil_Out32(DMA + 0x30, 4);
    XTime start_time, now;
    XTime_GetTime(&start_time);
    while (Xil_In32(DMA + 0x30) & 4)
    {
        XTime_GetTime(&now);
        if (now - start_time > COUNTS_PER_SECOND)
            return false;
    }
    Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(pixels), CAMERA_BYTES);
    Xil_Out32(DMA + 0x34, 0x7000);
    Xil_Out32(DMA + 0x30, 1);
    Xil_Out32(DMA + 0x48, reinterpret_cast<UINTPTR>(pixels));
    Xil_Out32(DMA + 0x58, CAMERA_BYTES);
    pin(16, true);
    return true;
}

bool camera_ready()
{
    return (Xil_In32(DMA + 0x34) & 0x1770) || (Xil_In32(GPIO + 8) & 2);
}

bool camera_finish(uint16_t *pixels)
{
    XTime start_time, now;
    XTime_GetTime(&start_time);
    for (;;)
    {
        const uint32_t dma_status = Xil_In32(DMA + 0x34);
        const uint32_t camera_status = Xil_In32(GPIO + 8);
        if ((dma_status & 0x770) || (camera_status & 2))
        {
            xil_printf("Capture error: DMA=%08x camera=%x\r\n", dma_status, camera_status);
            pin(16, false);
            Xil_Out32(DMA + 0x30, 4);
            return false;
        }
        if (dma_status & 0x1000)
            break;
        XTime_GetTime(&now);
        if (now - start_time > COUNTS_PER_SECOND * 2)
        {
            xil_printf("Capture timeout: DMA=%08x camera=%x\r\n", dma_status, camera_status);
            pin(16, false);
            Xil_Out32(DMA + 0x30, 4);
            return false;
        }
    }
    pin(16, false);
    Xil_DCacheInvalidateRange(reinterpret_cast<INTPTR>(pixels), CAMERA_BYTES);
    return Xil_In32(DMA + 0x58) == CAMERA_BYTES;
}

bool camera_capture(uint16_t *pixels)
{
    return camera_begin(pixels) && camera_finish(pixels);
}

bool camera_set_brightness(int level)
{
    if (level < -4 || level > 4)
        return false;
    uint8_t effect, sign;
    if (!read_register(0x5580, effect) || !read_register(0x5588, sign))
        return false;
    return write_register(0x5580, effect | 4) &&
           write_register(0x5587, (level < 0 ? -level : level) * 16) &&
           write_register(0x5588, level < 0 ? sign | 8 : sign & ~8);
}

void camera_to_input(const uint16_t *pixels, data_t *input)
{
    for (unsigned y = 0; y < 256; ++y)
    {
        for (unsigned x = 0; x < 256; ++x)
        {
            const unsigned i = y * 256 + x;
            const unsigned source_y = (2 * y + 1) * 416 / 512;
            const unsigned source_x = (2 * x + 1) * 416 / 512;
            const unsigned pixel = pixels[source_y * 416 + source_x];
            const unsigned r5 = pixel >> 11, g6 = (pixel >> 5) & 63, b5 = pixel & 31;
            const unsigned r = (r5 << 3) | (r5 >> 2);
            const unsigned g = (g6 << 2) | (g6 >> 4);
            const unsigned b = (b5 << 3) | (b5 >> 2);
            input[i] = (r << 1) + ((r + 64) >> 7);
            input[256 * 256 + i] = (g << 1) + ((g + 64) >> 7);
            input[2 * 256 * 256 + i] = (b << 1) + ((b + 64) >> 7);
        }
    }
}
