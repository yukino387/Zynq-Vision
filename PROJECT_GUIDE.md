# 在 Zynq-7020 上复现 YOLOv4-tiny FPGA 推理架构

适用环境：Vivado 2026.1、Vitis Unified IDE 2026.1、Zynq-7020 裸机应用。  
文档更新：2026年10月11日。  
工程目录：`C:\00_workplace\fpga\cnn_accelerator`。

本文说明当前工程的软件架构、数据约定和独立测试流程，帮助你从已验证的硬件算子逐步推进到真实模型部署。内容采用任务导向的技术文档组织方式。

> **重要**
> 当前已通过人工权重测试，验证了输入到两个原始预测张量的完整调用链。真实权重、真实图像和最终检测结果尚未验证。本文中的 PASS 不代表模型检测精度或实际部署性能已达标。

## 当前项目状态

| 组件 | 状态 | 已验证内容 |
|---|---|---|
| FPGA Conv IP | 已完成 | AXI-Lite 控制、DDR 数据读写和卷积执行 |
| XConv 驱动 | 已验证 | 参数设置、启动、完成查询 |
| basic_op | 已适配 | 当前 BSP 初始化及硬件算子调用 |
| BasicConv | 已实现 | 单层卷积封装、参数存储和析构 |
| Resblock_body | 已实现 | 四层卷积、通道拆分与拼接、池化 |
| CSPDarkNet | 已实现 | backbone 全部阶段和两个特征输出 |
| Yolo4_Tiny | 已实现 | 两个预测分支、上采样和关闭激活的最终预测卷积 |
| 真实参数与输入加载 | 未实现 | 权重、偏置、图像读取及转换待接入 |
| 真实模型数值对照 | 未验证 | 各阶段及预测输出待与作者参考结果比较 |
| 检测后处理 | 未实现 | sigmoid、框解码、NMS 和图像坐标还原 |
| 正式应用集成 | 未完成 | 当前通过独立测试 ELF 验证，原应用未接入完整网络 |

## 前提条件

复现本文测试前，请准备：

- 可正常供电并通过 JTAG 连接的 Zynq-7020 板卡。
- 已安装的 AMD 2026.1 工具链。当前脚本使用 `C:\AMDDesignTools\2026.1\Vitis`。
- 当前导出的 standalone BSP、XConv 驱动和原链接脚本。
- 已有的 `cnn_app\_ide\bitstream\cnn_accelerator.bit`。
- 已有的 `cnn_app\_ide\psinit\ps7_init.tcl`。

测试脚本使用工程已有的 bitstream 和 PS 初始化脚本，不重新生成硬件。脚本会重置 PS、配置 FPGA、下载测试 ELF，并在测试结束断点处停止 CPU；运行前结束占用同一板卡的其他调试会话。

## 了解工程文件

### 软件封装文件

| 文件 | 职责 |
|---|---|
| `basic_op.h/.cpp` | 初始化 XConv，设置寄存器，启动卷积、池化或上采样 |
| `basic_conv.h/.cpp` | 保存单层配置，分配权重和偏置，调用卷积算子 |
| `resblock_body.h/.cpp` | 组织四个 BasicConv，管理分支中间缓冲区 |
| `cspdarknet.h/.cpp` | 组织三个 BasicConv 和三个 Resblock_body |
| `yolo4_tiny.h/.cpp` | 组织 backbone、P5/P4 分支及两个原始预测输出 |

迁移参考来自作者工程的 `Code/Vitis/src/basic_op.cpp`、`basic_block.h` 和 `yolo4_tiny.h`。当前实现拆分为独立文件，复用已有模块，没有改变作者的网络连接顺序。

### 独立测试目录

```text
temporary/
├── basic_op_test/
├── basic_conv_test/
├── resblock_test/
├── cspdarknet_test/
└── yolo4_tiny_test/
```

各目录包含 `main.cpp`、`build.ps1`、`run.ps1`、`run.tcl`、日志及 `build/` 产物。测试代码未加入原 `cnn_app` 的正式源码目录。

## 了解调用链

```text
Yolo4_Tiny
  ├─ CSPDarkNet
  │    ├─ BasicConv
  │    └─ Resblock_body → BasicConv / sampling
  ├─ BasicConv
  ├─ sampling
  └─ 最终预测卷积：conv_leakyrelu(..., act=0)
          ↓
       basic_op
          ↓
       XConv 驱动
          ↓
       FPGA Conv IP ↔ DDR
```

### BasicConv

构造函数参数顺序为 `(h, w, k, s, p, ch_in, ch_out)`。对象分配 `ch_out × ch_in × k × k` 个权重元素和 `ch_out` 个偏置元素。构造函数不填充参数；执行前必须完成初始化。

`forward(input, output)` 固定调用 `conv_leakyrelu(..., act=1)`。对象不拥有调用者传入的输入和输出缓冲区。析构函数释放权重和偏置。当前类禁止拷贝，避免重复释放。

### Resblock_body

`forward(input, feat, out)` 的数据顺序为：

1. conv1 生成 `route`。
2. conv2 读取 route 后半通道，写入拼接缓冲区后半通道。
3. conv3 读取 conv2 输出，写入拼接缓冲区前半通道。
4. conv4 读取完整拼接缓冲区，生成 `feat`。
5. 分别池化 route 和 feat，将结果写入 out 的前、后通道区域。

因此拼接顺序是 `[conv3 输出, conv2 输出]`，池化输出顺序是 `[pool(route), pool(feat)]`。拼接通过地址偏移完成，不复制 feature map。此模块没有逐元素残差相加。

输出尺寸：

- `feat`：`ch_out × h × w`。
- `out`：`2 × ch_out × (h/2) × (w/2)`。

### CSPDarkNet

| 执行阶段 | 输入 CHW | 输出 CHW |
|---|---|---|
| BasicConv1：3×3，stride=2 | 3×416×416 | 32×208×208 |
| BasicConv2：3×3，stride=2 | 32×208×208 | 64×104×104 |
| Resblock1 | 64×104×104 | 128×52×52 |
| Resblock2 | 128×52×52 | 256×26×26 |
| Resblock3 | 256×26×26 | 512×13×13，同时输出 feat1：256×26×26 |
| BasicConv3：3×3，stride=1 | 512×13×13 | feat2：512×13×13 |

`forward(input, feat1, feat2)` 使用对象内部的中间缓冲区。BasicConv2 是作者结构的一部分，不应省略。

### Yolo4_Tiny

`forward(input, out0, out1)` 先执行 P5 预测分支，再执行上采样及 P4 分支。

| 执行阶段 | 输入 CHW | 输出 CHW | 激活 |
|---|---|---|---|
| backbone | 3×416×416 | feat1：256×26×26；feat2：512×13×13 | 各卷积启用 |
| conv_forP5：1×1 | 512×13×13 | P5：256×13×13 | 启用 |
| P5 BasicConv：3×3 | 256×13×13 | 512×13×13 | 启用 |
| P5 预测卷积：1×1 | 512×13×13 | out0：75×13×13 | 关闭 |
| upsample_conv：1×1 | P5：256×13×13 | 128×13×13 | 启用 |
| sampling：2倍上采样 | 128×13×13 | 128×26×26 | 不使用卷积激活 |
| 通道拼接 | 上采样输出和 feat1 | P4：384×26×26 | 不适用 |
| P4 BasicConv：3×3 | 384×26×26 | 256×26×26 | 启用 |
| P4 预测卷积：1×1 | 256×26×26 | out1：75×26×26 | 关闭 |

P4 的前128通道是上采样结果，后256通道是 feat1。backbone 直接写入 `P4 + 128*26*26`，随后上采样写入 P4 前半部分。

当前 `Yolo4_Tiny::OUT_CH` 固定为75，对应 `3 × (20 + 5)`。最终预测层直接调用 `conv_leakyrelu(..., act=0)`，不使用固定开启激活的 BasicConv。两个输出仍是原始预测数值，不执行 sigmoid、decode 或 NMS。

## 遵循数据和内存约定

### 数据格式

软件 `data_t` 为当前平台的16位有符号 `short`，缩放因子为512。例如，512表示1.0，-512表示-1.0。

所有 feature map 使用 CHW 连续布局：

```text
offset(c, r, col) = c*H*W + r*W + col
```

人工测试按照输出通道、输入通道、卷积核行列排列权重。后续导入真实参数时，应核对作者导出文件的排列、BN折叠和定点转换规则。

作者 `read_params()` 先读取 float 二进制数据，再执行 `round(value*512)` 转成 data_t。当前新建网络类尚未实现 `load_weight()`，不能直接把 float 文件当作 short 数组读取，也不能认为已完成 SD 加载。

### 缓冲区和所有权

调用者负责输入、输出缓冲区；网络对象负责自己的层参数和中间缓冲区。输入和输出使用独立、64字节对齐的 DDR 区域。网络内部缓冲区通过额外分配空间进行对齐，并保留原始指针用于释放。

| 顶层缓冲区 | 元素数 | 有效数据字节数 |
|---|---:|---:|
| input：3×416×416 | 519,168 | 1,038,336 |
| feat2：512×13×13 | 86,528 | 173,056 |
| P5：256×13×13 | 43,264 | 86,528 |
| out0_tmp：512×13×13 | 86,528 | 173,056 |
| P5_Upsample：128×13×13 | 21,632 | 43,264 |
| P4：384×26×26 | 259,584 | 519,168 |
| out1_tmp：256×26×26 | 173,056 | 346,112 |
| out0：75×13×13 | 12,675 | 25,350 |
| out1：75×26×26 | 50,700 | 101,400 |

表中不包含 backbone 内部缓冲区、权重、偏置、对齐填充或测试哨兵。Yolo4_Tiny 不单独分配 feat1，使用 P4 后256通道保存该特征。

out0、out1 的有效长度不是完整缓存行倍数。分配时应补齐尾部缓存行，避免邻接对象与输出共享缓存行。不要将输出区与输入、权重或其他活动缓冲区重叠。

### Cache 同步

FPGA通过DDR访问数据。ARM写入输入、权重或偏置后，在硬件读取前执行 `Xil_DCacheFlushRange()`；硬件写回后，在CPU读取前执行 `Xil_DCacheInvalidateRange()`。

- basic_op 和 BasicConv 本身不执行完整 Cache 同步；单独调用时由调用者负责。
- Resblock_body、CSPDarkNet、Yolo4_Tiny 在各自执行路径中处理相应的同步。
- 更新 P4 时保留后256通道的 feat1；不要用旧缓存内容覆盖硬件输出。

当前软件共用一个 XConv 实例，使用同步轮询调用。不要并发执行多个 forward，也不要在一次 forward 尚未完成时修改其输入或参数。

### 当前接口限制

basic_op 使用 h 设置硬件 `fsize`，p和w不写入硬件参数。当前网络按作者的正方形特征图和既定padding约定工作，不是任意尺寸卷积接口。

作者上采样硬件固定处理128×13×13到128×26×26。已有测试仅覆盖本工程所需配置；不能据此推断其他上采样尺寸可用。

basic_op 内部完成等待没有软件超时。独立测试由XSDB设置40秒运行超时，用于定位未完成的硬件调用。正式应用的超时处理尚未实现。

## 编译并运行独立测试

以下步骤复现完整顶层人工权重测试。无需修改原应用构建配置。

### 1. 打开工程目录

在PowerShell中执行：

```powershell
Set-Location -LiteralPath 'C:\00_workplace\fpga\cnn_accelerator'
```

### 2. 编译测试

```powershell
& .\temporary\yolo4_tiny_test\build.ps1
```

脚本编译现有XConv驱动、全部软件封装和独立测试，生成：

```text
temporary/yolo4_tiny_test/build/yolo4_tiny_test.elf
temporary/yolo4_tiny_test/build/yolo4_tiny_test.map
```

当前顶层测试仅通过链接参数设置32 MiB堆和64 KiB栈。它复用 `cnn_app/src/lscript.ld`，没有修改原链接脚本。原脚本默认8 KiB堆不足以分配完整网络；正式集成前需要单独确认堆、栈和DDR空间。

### 3. 连接板卡并运行

确认板卡供电和JTAG连接正常，执行：

```powershell
& .\temporary\yolo4_tiny_test\run.ps1
```

脚本通过XSDB执行现有PS初始化流程，加载已有bitstream和测试ELF。当前脚本在调试会话中设置 `force-mem-accesses`，用于访问已确认的PL地址；这不是Vivado地址配置修改。

### 4. 检查结果

```powershell
Get-Content .\temporary\yolo4_tiny_test\result.log
```

成功时日志应包含：

```text
test_stage = test_stage  : 4
test_errors = test_errors  : 0
test_checked = test_checked  : 733967
negative_out0 = negative_out0  : 6253
negative_out1 = negative_out1  : 25012
PASS: one Yolo4_Tiny instance constructed and destroyed, 733967 outputs checked, zero mismatches
```

result.log每次运行会覆盖。需要保留历史记录时，在下一次运行前另存该日志。不要只根据ELF生成或进程退出判断硬件测试通过。

## 查看已完成的验证

| 测试目录 | 校验元素数 | 当前结果 |
|---|---:|---|
| temporary/basic_op_test | 1,384,448 | PASS，两次卷积 |
| temporary/basic_conv_test | 1,384,448 | PASS，两次构造、执行和析构 |
| temporary/resblock_test | 302,848 | PASS，分支、拼接和池化 |
| temporary/cspdarknet_test | 2,941,952 | PASS，五个中间阶段及feat1/feat2 |
| temporary/yolo4_tiny_test | 733,967 | PASS，六个中间缓冲区及out0/out1 |

顶层测试使用确定性输入、人工中心卷积核和分支偏置。最终预测权重交替使用正、负系数，逐项检查正负输出，验证预测层关闭激活。P4两部分、输出长度及边界哨兵均纳入校验。

这些测试没有使用训练后的真实权重，没有测量检测精度，也没有建立可靠的性能基准。顶层测试的空间输入在每个通道内为常量；此前Resblock独立测试另外覆盖了随位置变化的输入。

## 排查常见问题

| 现象 | 检查和操作 |
|---|---|
| Bitstream is not programmed、DONE PIN is not HIGH | 检查供电与JTAG；断电约5秒后上电，重试加载工程已有bitstream |
| Level shifters are not enabled | 确认执行已有PS初始化和 `ps7_post_config` 流程 |
| PL地址未加入调试内存映射 | 使用本工程已验证的运行脚本；确认访问地址为0x43C00000 |
| DAP APB transaction error、无法访问ARM核 | 保留日志，断电重启后检查JTAG连接并复测 |
| forward超时 | 确认CTRL、参数、DDR地址和硬件响应；不能仅通过延长超时判定正确 |
| 数据错位或部分元素错误 | 核对CHW布局、参数数量、通道偏移和Cache同步 |
| 构造失败或运行停住 | 检查堆大小、DDR分配范围及动态内存是否足够 |
| 人工负值预测被缩小 | 检查最终预测卷积是否误用act=1 |

曾在完整backbone验证时出现DAP故障，断电重启后复测通过。该记录不确定故障根因，不应据此认定网络代码或硬件设计存在特定缺陷。

## 推进到真实模型部署

按以下顺序实施，每一步单独验证：

1. 确认作者模型对应的类别数、参数文件、BN折叠方式和参考输入。
2. 实现独立参数加载层，核对文件长度、读取结果、float到定点转换及数值范围。
3. 接入符合作者预处理约定的图像输入，包括尺寸、通道顺序和数值缩放。
4. 使用真实参数逐层对照BasicConv、Resblock和backbone输出，定义固定点误差判据。
5. 对照真实模型的out0/out1，确认通道顺序、预测层激活和类别配置。
6. 在原始预测输出验证后，实现sigmoid、decode、NMS及图像坐标还原。
7. 集成正式裸机应用，验证资源使用、重复推理、异常处理和最终检测结果。

当前新建类不提供权重文件解析接口。不要直接调用作者的load_weight示例而假定该接口已经存在，也不要在参数未初始化时执行forward。

## 保留或清理测试文件

保留根目录中的软件封装文件。`temporary/` 下的测试源码、脚本和构建产物可以在完成验证后删除；建议先另存需要追溯的result.log及对应测试源码。

删除临时目录不影响软件封装源码，但会失去本文运行步骤依赖的脚本。正式应用尚未接入完整网络，因此删除测试目录后不能依靠原应用复现顶层测试。
