# 工程协作约定

## 接手工程
- 实际开发仓库：`C:/00_workplace/fpga/cnn_accelerator`。不要修改同级作者参考工程。
- 首先查看 `git status --short`、`git log -5 --oneline`，再按当前任务读取相关代码；不要全量读取历史、日志和报告。
- 本文件记录长期约定；性能、板卡连接和程序运行状态必须重新确认，不能沿用旧结论。
- 最新已知进度（2026-10-20）：工作区（未提交）已实现 Linux 终端单一运行时：模型、产品、批次分离，平台与板端面板双向启停/检查，预览统一为 `device.preview.frame`，批次随生产开始/停止自动创建/关闭。板端已部署到 SD 根文件系统并通过断电重启验证：engine/panel/manager、16bpp `vision_fb.ko`、rcS/inittab 均持久化，重启后自动加载模型/产品。长期稳定性、真实产线精度和 30 FPS 预览未验证；以最新实测为准。

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
- 当前加载入口为 JTAG 加载；不能据此宣称已更新 SD/QSPI 启动镜像或上电自动运行。
- 软件改动优先复用平台构建应用；只有硬件改动需要时才重新执行 HLS/Vivado。综合及布局布线允许最多 16 线程，避免并发重型构建。
- 长构建复用已有会话和完成标记，不重复启动或频繁轮询完整日志；异常时再读取相关尾部和报告。
- JTAG 连接异常先检查目标和已有进程；确需断电时再请用户操作，不反复要求重启。

## 通信与已知注意事项
- 当前电脑地址 `169.254.140.109`，板卡 `169.254.140.110:5001`；上位机接收端口 5002，独立测试通常用 5003。先确认实际网卡和 PS 网口连接。
- UDP 测试可能接管接收端。测试前确认上位机占用，结束后恢复正式程序及用户正在使用的上位机。
- PS 使用 NEON；BSP 必须保留 `FPU_HARD_FLOAT_ABI_ENABLED=1`，确保中断保存浮点/NEON 上下文。
- lwIP 裸机主循环分配内存、网口中断释放内存；保留 `LWIP_ALLOW_MEM_FREE_FROM_OTHER_CONTEXT=1`。两项配置均在 `camera/create_app.py` 中设置。
- 画面间歇异常需区分传感器颜色、采集、缓冲区、网络及显示问题；短测通过不能宣称长期稳定。
