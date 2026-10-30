# 工程协作约定

## 接手工程
- 当前阶段（用户于 2026-10-30 明确确认）：工程处于开发初期。软件中的“生产/自动检测”状态是开发调试状态，不代表真实产线；任务范围内的临时停启、RAM 试验和恢复可直接执行，不为这些开发操作反复请求确认。保留用户已有代码、模型、产品和历史记录。
- 实际开发仓库：`C:/00_workplace/fpga/cnn_accelerator`。不要修改同级作者参考工程。
- 首先查看 `git status --short`、`git log -5 --oneline`，再按当前任务读取相关代码；不要全量读取历史、日志和报告。
- 本文件记录长期约定；性能、板卡连接和程序运行状态必须重新确认，不能沿用旧结论。
- 文档核对（2026-10-27）：已离线复算行重叠及720p25两轮固定输入CSV，固化复测21卷积/33命令为52.543651/57.607381 ms。10-27无采集显示ARM/PL主试验36/612次，逐输入等权212.30倍、合并样本212.29倍；NEON微内核换算24.52倍不是整网实测。当前资源45,289 LUT、61,317 FF、13,296 Slice，WNS/WHS +0.045/+0.050 ns。技术正文与当前图见 `temporary/content_revision_20261026/`，核查见 `temporary/document_update_20261027/`。部分旧JSON清单当前缺失，保留用户删除；本次未上板，不据此确认现场运行状态。
- 最新已知进度（2026-10-26）：在 48×8 INT8 行装载重叠版基础上，已固化自定义 720p25 RGB565 显示（像素 30.9375 MHz、串行 154.6875 MHz）、25 Hz 面板更新及去除 shadow 副本。正式 BOOT、QSPI、SD 启动文件和 SD 面板均已更新，软件复位从 QSPI 启动通过；固定输入卷积复测 52.544 ms、33 命令 57.607 ms，INT8 一致，WNS/WHS +0.045/+0.050 ns。当前 CAPS-RGB-v1（权重 `2658b41a`）、瓶盖计数产品，生产停止，governor=ondemand。固化时再次出现 SD 写入错误，当时 SLCR=0；根因未定，不能仅归因于锁定。RAM 环境离线文件系统检查通过，重启后 4 MiB 写入/fsync/读回及后续推理通过；断电冷启动和长期 SD 稳定性未验证。证据见 `temporary/hdmi25_deploy_20261026/`，文档见 `docs/cnn-accelerator-performance.md`。
- 阶段进度（2026-10-26）：48×8 INT8 行读取/解包重叠版已更新正式 HLS、Linux bitstream、交付 BOOT，并写入 QSPI 与 SD BOOT。固定输入卷积约 56.916→54.247 ms（降低 4.689%），首次启动后复测 54.242 ms，INT8 一致；实现 Slice 99.97%。该阶段完整 SD 分区和业务备份保存在 `temporary/load_overlap_deploy_20261026/`。
- 进度（2026-10-23）：液位判定已升到 LEVEL-ROW-v1.3：合格带 85.0~102.9、无液面显式判过低、权重 sha `3aca8253`（包头版本字符串仍是 `LEVEL-BAND-v1`，engine 按包头校验）；当时板端 engine/panel 已更新并切换到液位模型/产品，生产处于停止。平台数据库尚未导入 v1.3 模型记录，跑生产记录前需先在平台导入并重新分配。瓶盖便携训练包已核对，回退底座 `2658b41a` 与 CAPS-RGB-v1 一致。
- 进度（2026-10-20）：工作区（未提交）已实现 Linux 终端单一运行时：模型、产品、批次分离，平台与板端面板双向启停/检查，预览统一为 `device.preview.frame`，批次随生产开始/停止自动创建/关闭。板端已部署到 SD 根文件系统并通过断电重启验证：engine/panel/manager、16bpp `vision_fb.ko`、rcS/inittab 均持久化，重启后自动加载模型/产品。长期稳定性、真实产线精度和 30 FPS 预览未验证；以最新实测为准。

## 修改原则
- 采用简单、直接、最小范围的修改。不增加无需求的兼容层、hook、fallback 或抽象。
- 只处理当前任务；不要自动重构网络、整理目录、扩展功能或清理无关文件。
- 不主动新增或修改项目说明文档；本文件是接手约定的例外。
- 测试代码和输出放在 `temporary/<任务名>/`，不要混入正式推理代码。只做足以验证改动的测试。
- 保留用户已有修改和无关未跟踪文件；Git 仅按明确文件路径暂存，禁止直接 `git add .`。
- 汇报简洁：改动、验证结果、未解决问题。区分 HLS 估算、实现通过、上板正确性和实测提速。

## 关键路径与链路
- `hardware/hls/src/`：卷积加速器 HLS 源码；`hardware/camera/`：摄像头及 Vivado 工程脚本。
- `camera/int8/`：INT8 网络、权重、灰度预处理和实时调度；`camera/camera_input.cpp`：摄像头采集；`camera/udp_output.cpp`：网口通信。
- `vitis_live/`：Vitis 工作区；应用 `camera_live`，平台 `camera_platform_live`。
- `camera/create_app.py`：平台和应用配置的可复现入口；不要只修改会被重新生成的 BSP 文件。
- `camera/winui/`：CNN Studio 上位机；便携程序为 `camera/winui/build/delivery/CNNStudio/CNNStudio.exe`。
- 当前链路：OV5640 → PL 采集 → DDR → PS 灰度预处理/调度 → PL 卷积 → PS UDP → 上位机。
- 板卡为领航者 V3.9 / Zynq-7020，摄像头 ATK-MC5640 V1.2。当前采集为 416×416 RGB565，模型输入为 224×224 单通道 INT8。改动前核对当前源码。

## 构建与上板
- AMD 工具安装在 `C:/AMDDesignTools/2026.1`；PowerShell 环境入口为 `hardware/camera/vivado_env.ps1`。
- 正式 ELF：`vitis_live/camera_live/build/camera_live.elf`；正式 bitstream：`hardware/camera/build/system_wrapper.bit`。
- 正式加载入口：`vitis_live/run_live.tcl`，通过 AMD XSDB 执行。它会复位 PS、初始化 DDR、下载 bitstream/ELF 并运行；不要与 Vitis Run/Debug 并发操作板卡。
- 上述入口为裸机 JTAG 加载；当前 Linux 终端从 QSPI 启动 FSBL/FPGA/U-Boot，SD 提供内核和根文件系统。Linux 正式 bitstream 为 `hardware/camera/build/terminal/system_wrapper.bit`，启动交付镜像为 `camera/terminal/build/delivery/boot/BOOT.bin`；JTAG 临时加载不能作为持久启动证据。
- 软件改动优先复用平台构建应用；只有硬件改动需要时才重新执行 HLS/Vivado。综合及布局布线允许最多 16 线程，避免并发重型构建。
- 长构建复用已有会话和完成标记，不重复启动或频繁轮询完整日志；异常时再读取相关尾部和报告。
- JTAG 连接异常先检查目标和已有进程；确需断电时再请用户操作，不反复要求重启。
- Linux 运行时应保持 SLCR 解锁（`0xf800000c` 为 0）；只重配 PL 的试验脚本不能用写 `0xf8000004=0x767b` 收尾。Linux 启动时会解锁 SLCR，时钟等驱动后续仍需修改寄存器。收尾应重新核对锁状态及 SD I/O，不沿用裸机的锁定惯例。
- SLCR 解锁不能作为 SD 写入可靠的证明；写入正式启动文件前需检查当前内核 I/O 错误及实际 fsync/读回，出现错误立即停止写盘，保留备份后在 RAM/离线环境检查。两次异常根因仍待定位，不宣称已根治。

## 通信与已知注意事项
- 当前电脑地址 `169.254.140.109`，板卡 `169.254.140.110:5001`；上位机接收端口 5002，独立测试通常用 5003。先确认实际网卡和 PS 网口连接。
- UDP 测试可能接管接收端。测试前确认上位机占用，结束后恢复正式程序及用户正在使用的上位机。
- PS 使用 NEON；BSP 必须保留 `FPU_HARD_FLOAT_ABI_ENABLED=1`，确保中断保存浮点/NEON 上下文。
- lwIP 裸机主循环分配内存、网口中断释放内存；保留 `LWIP_ALLOW_MEM_FREE_FROM_OTHER_CONTEXT=1`。两项配置均在 `camera/create_app.py` 中设置。
- 画面间歇异常需区分传感器颜色、采集、缓冲区、网络及显示问题；短测通过不能宣称长期稳定。
