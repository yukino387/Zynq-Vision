
#include <stdint.h>
#include <string.h>

#include "xil_cache.h"
#include "xil_io.h"
#include "xil_printf.h"
#include "xil_types.h"

/*
 * Zynq-7020 CNN 加速器硬件测试
 *
 * 测试目标：
 *   1. ARM 在 DDR 中准备输入、权重和输出缓冲区
 *   2. ARM 通过 AXI4-Lite 配置 HLS Conv IP
 *   3. FPGA 通过 AXI HP 接口读取 DDR 数据
 *   4. FPGA 执行一次真实的 3x3 卷积
 *   5. FPGA 将计算结果写回 DDR
 *   6. ARM 对所有输出元素进行校验
 *
 * 数据格式：16 位有符号 Q6.9 定点数
 *   512 表示 1.0
 *     0 表示 0.0
 *
 * 预期结果：全部输出元素均为 512
 */

/* =========================================================
 * 1. 硬件配置
 * ========================================================= */

/*
 * Conv IP 的 AXI4-Lite 基地址
 *
 * 这是之前已经成功读取到 CTRL = 0x4 的地址。
 * 如果 Vivado Address Editor 中地址发生变化，必须同步修改。
 */
#define CONV_BASE 0x43C00000U

/* 输入特征图：32 个通道，208x208 */
#define CH_IN 32
#define INPUT_H 208
#define INPUT_W 208

/* 输出特征图：64 个通道，104x104 */
#define CH_OUT 64
#define OUTPUT_H 104
#define OUTPUT_W 104

/* 3x3 卷积，步长为 2 */
#define KERNEL_SIZE 3
#define STRIDE 2

/* Q6.9 格式中的 1.0 */
#define FIXED_ONE 512

/*
 * 轮询次数上限，用来避免 FPGA 无响应时无限等待。
 *
 * 注意：这是轮询次数，不是精确的时间。
 * 后续可以通过 ARM 全局定时器测量实际计算延迟。
 */
#define MAX_POLL_COUNT 100000000U

/* 各数组元素数量 */
#define INPUT_COUNT (CH_IN * INPUT_H * INPUT_W)
#define WEIGHT_COUNT (CH_OUT * CH_IN * KERNEL_SIZE * KERNEL_SIZE)
#define OUTPUT_COUNT (CH_OUT * OUTPUT_H * OUTPUT_W)

/* =========================================================
 * 2. Conv IP 寄存器偏移
 *
 * 根据原作者提供的 xconv_hw.h 定义。
 * ========================================================= */

#define REG_AP_CTRL 0x00

#define REG_IN1 0x10
#define REG_IN2 0x18
#define REG_IN3 0x20
#define REG_IN4 0x28

#define REG_W1 0x30
#define REG_W2 0x38
#define REG_W3 0x40
#define REG_W4 0x48

#define REG_BIAS 0x50

#define REG_OUT1 0x58
#define REG_OUT2 0x60
#define REG_OUT3 0x68
#define REG_OUT4 0x70

#define REG_CH_IN 0x78
#define REG_CH_OUT 0x80
#define REG_FSIZE 0x88
#define REG_STRIDE 0x90
#define REG_KERNEL 0x98
#define REG_ACT 0xA0

/* =========================================================
 * 3. DDR 数据缓冲区
 *
 * 使用 static：
 *   避免将大型数组放到 ARM 栈上。
 *
 * 使用 aligned(64)：
 *   保证缓冲区具有足够的 Cache 行对齐。
 *
 * 注意：
 *   这些数组必须由链接脚本分配到 PS DDR，
 *   不能被放到 OCM 或其他较小的内存区域。
 * ========================================================= */

/* 输入特征图：CHW 格式 */
static int16_t input[INPUT_COUNT] __attribute__((aligned(64)));

/* 卷积权重：OIHW 格式 */
static int16_t weights[WEIGHT_COUNT] __attribute__((aligned(64)));

/* 每个输出通道对应一个偏置 */
static int16_t bias[CH_OUT] __attribute__((aligned(64)));

/* 卷积输出特征图：CHW 格式 */
static int16_t output[OUTPUT_COUNT] __attribute__((aligned(64)));

/* =========================================================
 * 4. AXI4-Lite 寄存器操作
 * ========================================================= */

/* 向 Conv IP 的指定寄存器写入 32 位数据 */
static void conv_write(uint32_t offset, uint32_t value)
{
    Xil_Out32(CONV_BASE + offset, value);
}

/* 从 Conv IP 的指定寄存器读取 32 位数据 */
static uint32_t conv_read(uint32_t offset)
{
    return Xil_In32(CONV_BASE + offset);
}

/* =========================================================
 * 5. 初始化测试数据
 * ========================================================= */

static void prepare_test_data(void)
{
    xil_printf("Preparing test data...\r\n");

    /*
     * 输入特征图所有元素设置为 1.0。
     *
     * Q6.9 中：
     *   1.0 * 512 = 512
     */
    for (int i = 0; i < INPUT_COUNT; i++)
    {
        input[i] = FIXED_ONE;
    }

    /* 所有卷积权重初始为 0 */
    memset(weights, 0, sizeof(weights));

    /* 所有偏置为 0 */
    memset(bias, 0, sizeof(bias));

    /*
     * 把输出缓冲区填成非零的特殊值。
     *
     * 这样即使 FPGA 没有正确写回 DDR，
     * 我们也更容易发现问题。
     */
    memset(output, 0xA5, sizeof(output));

    /*
     * 对每一个输出通道：
     *
     * 只让输入第 0 通道对应的 3x3 卷积核
     * 中心位置的权重等于 1.0。
     *
     * 其余所有权重都是 0。
     *
     * 这样卷积的理论结果就是：
     *
     * output = input[0] * 1.0 = 1.0
     *
     * 由于使用卷积核中心位置，
     * 边界上的输出也应当是 1.0。
     *
     * 权重排列方式：
     *   [输出通道][输入通道][3][3]
     */
    for (int oc = 0; oc < CH_OUT; oc++)
    {
        int index = (oc * CH_IN + 0) * 9 + 4;

        weights[index] = FIXED_ONE;
    }

    xil_printf("Test data prepared.\r\n");
}

/* =========================================================
 * 6. Cache 同步
 * ========================================================= */

static void flush_buffers(void)
{
    /*
     * ARM Cortex-A9 有数据缓存。
     *
     * ARM 修改数组后，最新数据可能只在 Cache 中，
     * 还没有写入实际 DDR。
     *
     * FPGA 通过 AXI HP 接口访问 DDR，
     * 因此启动前需要把数据写回 DDR。
     */

    Xil_DCacheFlushRange((INTPTR)input, sizeof(input));

    Xil_DCacheFlushRange((INTPTR)weights, sizeof(weights));

    Xil_DCacheFlushRange((INTPTR)bias, sizeof(bias));

    Xil_DCacheFlushRange((INTPTR)output, sizeof(output));

    xil_printf("Cache flushed.\r\n");
}

/* =========================================================
 * 7. 配置加速器输入和输出地址
 * ========================================================= */

static void configure_addresses(void)
{
    /*
     * 将数组地址作为 32 位物理地址传给 FPGA。
     *
     * 本测试使用 Zynq-7000 裸机环境，
     * 默认采用 DDR 地址恒等映射。
     */

    uint32_t input_addr = (uint32_t)(UINTPTR)input;

    uint32_t weight_addr = (uint32_t)(UINTPTR)weights;

    uint32_t bias_addr = (uint32_t)(UINTPTR)bias;

    uint32_t output_addr = (uint32_t)(UINTPTR)output;

    /*
     * 四路 AXI Master 访问同一份输入数据。
     *
     * 注意：
     *   不是将输入数组拆分成四份！
     */
    conv_write(REG_IN1, input_addr);
    conv_write(REG_IN2, input_addr);
    conv_write(REG_IN3, input_addr);
    conv_write(REG_IN4, input_addr);

    /* 四路权重读取接口 */
    conv_write(REG_W1, weight_addr);
    conv_write(REG_W2, weight_addr);
    conv_write(REG_W3, weight_addr);
    conv_write(REG_W4, weight_addr);

    /* 偏置地址 */
    conv_write(REG_BIAS, bias_addr);

    /* 四路输出写回接口 */
    conv_write(REG_OUT1, output_addr);
    conv_write(REG_OUT2, output_addr);
    conv_write(REG_OUT3, output_addr);
    conv_write(REG_OUT4, output_addr);

    /* 打印 DDR 地址，便于定位问题 */
    xil_printf("Input  DDR: 0x%x\r\n", input_addr);
    xil_printf("Weight DDR: 0x%x\r\n", weight_addr);
    xil_printf("Bias   DDR: 0x%x\r\n", bias_addr);
    xil_printf("Output DDR: 0x%x\r\n", output_addr);
}

/* =========================================================
 * 8. 配置卷积参数
 * ========================================================= */

static void configure_conv(void)
{
    /*
     * ch_in = 32
     * ch_out = 64
     * fsize = 208
     * stride = 2
     * kernel = 3
     * act = 0
     *
     * kernel = 3：3x3 标准卷积
     * act = 0：不使用 LeakyReLU
     */

    conv_write(REG_CH_IN, CH_IN);
    conv_write(REG_CH_OUT, CH_OUT);
    conv_write(REG_FSIZE, INPUT_H);
    conv_write(REG_STRIDE, STRIDE);
    conv_write(REG_KERNEL, KERNEL_SIZE);
    conv_write(REG_ACT, 0);

    xil_printf("Conv parameters configured.\r\n");
}

/* =========================================================
 * 9. 检查寄存器配置
 * ========================================================= */

static int verify_registers(void)
{
    /*
     * 检查部分关键寄存器是否正确接收数据。
     *
     * 只能证明 AXI4-Lite 配置成功，
     * 还不能证明 FPGA 已经执行计算。
     */

    if (conv_read(REG_IN1) != (uint32_t)(UINTPTR)input)
    {
        xil_printf("ERROR: input address mismatch\r\n");
        return -1;
    }

    if (conv_read(REG_W1) != (uint32_t)(UINTPTR)weights)
    {
        xil_printf("ERROR: weight address mismatch\r\n");
        return -1;
    }

    if (conv_read(REG_OUT1) != (uint32_t)(UINTPTR)output)
    {
        xil_printf("ERROR: output address mismatch\r\n");
        return -1;
    }

    if (conv_read(REG_KERNEL) != KERNEL_SIZE)
    {
        xil_printf("ERROR: kernel parameter mismatch\r\n");
        return -1;
    }

    xil_printf("Register configuration OK.\r\n");

    return 0;
}

/* =========================================================
 * 10. 启动 FPGA 并等待计算完成
 * ========================================================= */

static int run_hardware_conv(void)
{
    /*
     * ap_ctrl 寄存器：
     *
     * bit 0 = ap_start
     * bit 1 = ap_done
     * bit 2 = ap_idle
     * bit 3 = ap_ready
     *
     * 写 bit0 = 1，启动一次计算。
     */

    xil_printf("CTRL before: 0x%x\r\n", conv_read(REG_AP_CTRL));

    xil_printf("Starting FPGA convolution...\r\n");

    /* 启动 FPGA */
    conv_write(REG_AP_CTRL, 0x01);

    /*
     * 轮询 ap_done。
     *
     * 该状态位具有 Clear-On-Read 行为，
     * 因此每轮只读取一次控制寄存器。
     *
     * 不依赖任何计时头文件。
     */
    uint32_t ctrl = 0;
    uint32_t count = 0;

    int done = 0;

    for (count = 0; count < MAX_POLL_COUNT; count++)
    {
        ctrl = conv_read(REG_AP_CTRL);

        if ((ctrl & 0x02U) != 0)
        {
            done = 1;
            break;
        }
    }

    if (!done)
    {
        xil_printf("ERROR: FPGA timeout!\r\n");
        xil_printf("Last CTRL: 0x%x\r\n", ctrl);
        xil_printf("Poll count: %u\r\n", (unsigned)count);

        return -1;
    }

    xil_printf("FPGA computation completed.\r\n");

    xil_printf("Poll count: %u\r\n", (unsigned)count);

    /*
     * 注意：
     * 这个 count 不是时钟周期数，
     * 也不能直接换算成 FPGA 的计算时间。
     */

    return 0;
}

/* =========================================================
 * 11. 从 DDR 读取并校验 FPGA 输出
 * ========================================================= */

static int verify_output(void)
{
    /*
     * FPGA 写回 DDR 后，
     * ARM Cache 中可能仍保留旧数据。
     *
     * 因此需要使输出区域的缓存失效，
     * 让 ARM 重新从 DDR 读取计算结果。
     */

    Xil_DCacheInvalidateRange((INTPTR)output, sizeof(output));

    xil_printf("Checking output data...\r\n");

    int errors = 0;

    /*
     * 每一个输出元素的理论值都是 512。
     *
     * 不只检查第一个元素，
     * 而是检查完整的 64x104x104 输出张量。
     */

    for (int i = 0; i < OUTPUT_COUNT; i++)
    {
        if (output[i] != FIXED_ONE)
        {
            /*
             * 为避免串口刷屏，
             * 只打印前 10 个错误。
             */
            if (errors < 10)
            {
                xil_printf("Mismatch [%d]: got %d, expected %d\r\n", i, (int)output[i], FIXED_ONE);
            }

            errors++;
        }
    }

    xil_printf("Checked %d elements.\r\n", OUTPUT_COUNT);

    if (errors == 0)
    {
        xil_printf("\r\n");
        xil_printf("============================\r\n");
        xil_printf(" TEST PASS\r\n");
        xil_printf(" All outputs are correct!\r\n");
        xil_printf("============================\r\n");

        return 0;
    }

    xil_printf("\r\n");
    xil_printf("============================\r\n");
    xil_printf(" TEST FAIL\r\n");
    xil_printf(" Total errors: %d\r\n", errors);
    xil_printf("============================\r\n");

    return -1;
}

/* =========================================================
 * 12. ARM 裸机主程序
 * ========================================================= */

int main(void)
{
    xil_printf("\r\n");
    xil_printf("==================================\r\n");
    xil_printf(" Zynq-7020 CNN Accelerator Test\r\n");
    xil_printf("==================================\r\n");

    /*
     * 第一步：
     * ARM 在 DDR 中准备输入数据、权重及偏置。
     */
    prepare_test_data();

    /*
     * 第二步：
     * 将 CPU Cache 中的数据同步到 DDR。
     */
    flush_buffers();

    /*
     * 第三步：
     * 将 DDR 地址传递给 FPGA。
     */
    configure_addresses();

    /*
     * 第四步：
     * 设置卷积尺寸、步长等参数。
     */
    configure_conv();

    /*
     * 第五步：
     * 检查关键寄存器。
     */
    if (verify_registers() != 0)
    {
        xil_printf("Register test failed.\r\n");

        while (1)
        {
        }
    }

    /*
     * 第六步：
     * ARM 启动 FPGA，等待计算完成。
     */
    if (run_hardware_conv() != 0)
    {
        xil_printf("Hardware execution failed.\r\n");

        while (1)
        {
        }
    }

    /*
     * 第七步：
     * ARM 读取 FPGA 输出并验证结果。
     */
    verify_output();

    /*
     * 裸机环境没有操作系统管理进程退出，
     * 测试完成后保持程序运行。
     */
    while (1)
    {
    }

    return 0;
}
