# 阶段一：工程事实与证据索引

审计日期：2026-10-25（Asia/Shanghai）；仓库基准 `5bcc771354f1fe061fc8297c5fed886473d2bbbc`。配套文档：[工程事实审计](01_ENGINEERING_AUDIT.md)。

E01～E40保留第一阶段调查时的口径；E41～E52为2026-10-25按用户补充信息开展的定向调查。“本轮”在旧条目中仍指第一阶段。本轮只补充牛奶盒/瓶盖兼容性、早期裸机性能与演进证据，不追溯性改写旧测试条件。源文件链接相对本目录解析到仓库真实文件；函数/字段/提交哈希是检索定位词，不依赖易变行号。

## 使用约定

- **S**：当前源码/配置，证明实现；**R**：HLS/Vivado 原始报告；**T**：已有运行日志/测试结果；**G**：Git 提交；**D**：文档/指南/人工摘要；**A**：图片/视频素材；**I**：本轮只读计算或推断。
- **高**表示直接检查过对应源码、原始报告或可核对结果，仅在限定范围内成立；**中**表示主要依赖摘要/提交或版本链不完整；**待确认**表示缺证据或只有目标。
- 视频“可”仅表示技术说法有出处，仍需制作可读画面；“有条件”必须保留测试条件/补现场镜头；“否”不宜作为成果画面。所有历史测试都不是本轮现场实测。
- 本轮不读取 `.env`、业务数据库、连接配置或私人会话内容，不复制令牌/凭证。记录的模型/构建 SHA 是版本标识，不是凭证。开源前仍需单独整理可公开文件。

## A. 基准、规则与全局架构

| 编号 | 结论 | 证据位置与定位方式 | 类型 | 可信程度/限制 | 是否适合视频 |
|---|---|---|---|---|---|
| <a id="e01"></a>E01 | 当前代码基准与历史现场状态分开；本轮未做板级操作 | `git status --short`、`git status --short --untracked-files=no`、`git log -5 --oneline`、`git rev-parse HEAD`；[AGENTS.md](../../AGENTS.md) 仅作长期约定 | G/S/I | 高：受跟踪文件原本无差异，未跟踪文件很多；当前板端状态未知 | 否；作为审计元数据 |
| <a id="e02"></a>E02 | 本地指南含初级组资格、器件、提交、评分、AI 协作要求；未证实 180 秒来自官方 | [guide.pdf](../../temporary/competition_2026/guide.pdf)，PDF 页 22～25、28，印刷页 19～22、25；§3.3.1～3.3.5.5、第六节 | D | 高：已直接提取这些页；中：副本来源/最新效力未确认。官网 `https://www.fpgachina.cn/` 本轮抓取超时，未引用第三方评分标准 | 否；用于选题与交付约束，180 秒遵用户要求 |
| <a id="e03"></a>E03 | 工程含 HLS/RTL、裸机与 Linux、训练、Web/手机/模拟器 | [package.json](../../package.json)、[server/package.json](../../apps/server/package.json)、[web/package.json](../../apps/web/package.json)、[mobile/package.json](../../apps/mobile/package.json)、[CMakeLists.txt](../../camera/terminal/CMakeLists.txt)；根目录只读清单 | S | 高：依赖配置与入口存在；不证明本轮所有依赖已安装或全部页面已验收 | 可：简化为端侧与管理端，勿堆技术栈 |
| <a id="e04"></a>E04 | 摄像头采集由 PL 接入，帧为 416×416 RGB565，经异步 FIFO 与 AXI DMA 到 DDR | [ov5640_capture.v](../../hardware/camera/ov5640_capture.v)：`packed_pixels`、`word_count==86527`、`line_bytes!=832`、`xpm_fifo_async`；[build.tcl](../../hardware/camera/build.tcl)：`camera_dma`/S2MM/HP0；[ov5640_mode.h](../../hardware/camera/ov5640_mode.h)；[hardware.cpp](../../camera/terminal/hardware.cpp)：`initialize_camera/start_capture/wait_capture` | S | 高：源码直接支持；摄像头实际曝光/FPS/连接本轮未现场读回 | 可：硬件实拍加 32 位打包/跨域示意 |
| <a id="e05"></a>E05 | 8 个 AXI master bundle 分组共享 4 个 HP，最终共享 PS DDR；采集/显示会争用 | [top.cpp](../../hardware/hls/src/top.cpp)：FM1～4/W1～4，bias=W1；[base_system.tcl](../../hardware/camera/base_system.tcl)：接口连接；[build.tcl](../../hardware/camera/build.tcl)：DMA→HP0；[integrate.tcl](../../hardware/display/integrate.tcl)：VDMA→HP3；[build.tcl](../../hardware/camera/build.tcl)：`accelerator_mhz=125.0`、part `xc7z020clg400-2` | S | 高；不是 8 个 DDR 通道；base Tcl 的 100 MHz 被构建入口覆盖 | 可：明确画共享 DDR，突出带宽问题 |

## B. 网络、计算核心与 PS/PL 协作

| 编号 | 结论 | 证据位置与定位方式 | 类型 | 可信程度/限制 | 是否适合视频 |
|---|---|---|---|---|---|
| <a id="e06"></a>E06 | 固定图 33 命令，实际 21 卷积；224 输入、1/3 通道；两路 33 通道头共 8085 字节 | [graph.json](../../camera/training/graph.json)：`commands` 第 8 字段；[model.h](../../camera/int8/model.h)；[pl_model.py](../../camera/training/pl_model.py)：`commands_for/FixedGraph/HEADS`；[hardware.cpp](../../camera/terminal/hardware.cpp)：`load_model` 图匹配、`frame.out0/out1.resize`；[upsample.cpp](../../hardware/hls/src/upsample.cpp)：128 通道/7→14 | S/I | 高：本轮统计 `{3:14,1:7,5:8,2:3,0:1}`；图形状受限；不等于任意网络平台 | 可：写“33 条算子命令/21 层卷积”，不写“33 层卷积” |
| <a id="e07"></a>E07 | W8A8、INT32 部分和、INT64 重定标，正负参数和舍入/饱和需一致 | [type.h](../../hardware/hls/src/type.h)；[std_conv.cpp](../../hardware/hls/src/std_conv.cpp)：`requant/quantize_output/quant_nm/quant_ns`；[top.cpp](../../hardware/hls/src/top.cpp)：kernel=5 查表；[pl_model.py](../../camera/training/pl_model.py)：`requant/export_int8/integer_forward` | S | 高；不是所有运算都 8 位；LeakyReLU 负支路通过参数实现 | 可：简明数据精度图；完整舍入公式留报告 |
| <a id="e08"></a>E08 | 48×8 乘法并行；双权重打包使一个 DSP 乘法给出两个 INT8 乘积 | [std_conv.cpp](../../hardware/hls/src/std_conv.cpp)：`Tm/Tn/compute`；[packed_multiply.h](../../hardware/hls/src/packed_multiply.h)：`multiply_pair`、高半部符号修正；[analyze.py](../../temporary/hls_research_20261024/analyze.py)、[findings.json](../../temporary/hls_research_20261024/findings.json)：`packing_check/source_sha256` | S/T/I | 高：源码与研究指纹本轮全部匹配；既有 Python 穷举记录 16,777,216 组三元输入、33,554,432 个乘积零差异；本轮未重跑穷举；不是 RTL 全覆盖 | 可：最强硬件原理候选，强调同一输入共乘 |
| <a id="e09"></a>E09 | compute 子流水 II=1、迭代 latency=11、192 DSP 是 HLS 估计；顶层资源不能替代 Routed | [compute 流水报告](../../hardware/hls/build/conv/hls/syn/report/compute_Pipeline_VITIS_LOOP_228_4_VITIS_LOOP_229_5_csynth.rpt)：Loop/Utilization；[conv_csynth.xml](../../hardware/hls/build/conv/hls/syn/report/conv_csynth.xml)：Resources；[build.tcl](../../hardware/hls/build.tcl)：7 ns 目标 | R | 高：报告日期 10-20，工具 2026.1；顶层估计 LUT117802/DSP217/BRAM18K204；报告不是本轮生成，7 ns 不等于当前 125 MHz 的 8 ns | 可：标 HLS 子流水，禁止“一周期一层”与“整网实测96GOPS” |
| <a id="e10"></a>E10 | 行补齐/权重重排、54 KiB 条件缓存、A/B 装载计算重叠、SRL 写回；非全网三阶段全重叠 | [layout.h](../../hardware/hls/src/layout.h)；[std_conv.cpp](../../hardware/hls/src/std_conv.cpp)：`weight_cache/load_input_pair/load_weight_lane/load_compute/compute_output/store_output/cache_enabled`；[pl_model.py](../../camera/training/pl_model.py)：`pack_weights` | S/I | 高：按声明算缓存55296B、输入双缓冲15312B、权重双缓冲6912B、部分和43008B；物理分区开销另计；`TRin` 注释27过时，表达式实际29 | 可：A/B 缓冲动画与空间块复用；保留预填/排空 |
| <a id="e11"></a>E11 | Linux PS 逐层启动同一 PL 核心，同时准备下一帧；计时范围不同 | [hardware.cpp](../../camera/terminal/hardware.cpp)：`Hardware::capture/prepare_capture`、33 循环、`std::async`/CPU0、`conv_ns/forward_ns`；[vision_accel.c](../../camera/terminal/linux/vision_accel.c)：`dma_alloc_coherent/dma_mmap_coherent/vision_open`；[vision_uapi.h](../../camera/terminal/linux/vision_uapi.h) | S | 高；`hwConvMs` 含命令交接；`hwForwardMs` 含等下一帧；都非曝光到判定延迟。独占硬件打开不代表无多线程 | 可：PS/PL 分工及两帧交叠图，不画 PL 自主 sequencer |
| <a id="e12"></a>E12 | 本地界面由 ARM 绘制，PL 扫描 RGB565 framebuffer 到 720p60 HDMI | [integrate.tcl](../../hardware/display/integrate.tcl)、[video_timing.v](../../hardware/display/video_timing.v)、[hdmi_scanout.v](../../hardware/display/hdmi_scanout.v)、[tmds_encoder.v](../../hardware/display/tmds_encoder.v)、[tmds_serializer.v](../../hardware/display/tmds_serializer.v)；[vision_fb.c](../../camera/terminal/linux/vision_fb.c)：1280/720/16bpp/双页；[panel.cpp](../../camera/terminal/panel.cpp) | S | 高：60 Hz 为视频扫描，不是 CNN FPS；显示真实画质/无闪烁需实拍 | 可：展示板端 HDMI 与实物同框 |

## C. 检测业务、模型与管理链路

| 编号 | 结论 | 证据位置与定位方式 | 类型 | 可信程度/限制 | 是否适合视频 |
|---|---|---|---|---|---|
| <a id="e13"></a>E13 | 检测头解码、sigmoid/exp 查表、过滤、跟踪、ROI 与数量判定在 ARM | [core.cpp](../../camera/terminal/core.cpp)：`decode_candidates/filter_boxes/detect_objects/Tracker::update/evaluate/quality`；[core.h](../../camera/terminal/core.h)；[engine.cpp](../../camera/terminal/engine.cpp)：`frame_detections/filtered_decision/tick` | S | 高：有 BOX_FILTER_V3 分支；算法存在不等于实场景准确率已达标 | 可：解释 PL 原始头→ARM 框→产品判定 |
| <a id="e14"></a>E14 | 一件产品由多帧完整计数向量共识，空场/入场/出场和中断门槛决定保存 | [passage.h](../../camera/terminal/passage.h)：`same/sample/observe/finish`；[presence.h](../../camera/terminal/presence.h)：`ScenePresence::observe`；[engine.cpp](../../camera/terminal/engine.cpp)：`save_passage/save_evidence` | S | 高：源码可核对；固定相机、产品分离等条件明显；不跨帧累加框数冒充数量 | 有条件：需实际过件录像；状态机可用示意 |
| <a id="e15"></a>E15 | 液位为固定包专用兼容路径；判定主要由 ARM 归一化图像测量实现 | [level_compat.h](../../camera/terminal/level_compat.h)：`level_model_sha256/level_band_low/high`；[level_compat.cpp](../../camera/terminal/level_compat.cpp)：`prepare_level/measure_level/level_detections/level_decision`；[hardware.cpp](../../camera/terminal/hardware.cpp)：`level_enabled`；[v1.3 manifest](../../temporary/pkgs_20261023/level_v13/manifest.json) | S/D | 高：当前 hash3aca8253…、85～102.9；无液面低、无红标签复核；网络框用于显示、标签可作为存在框；行数非毫米；包头名与 manifest 版本不同 | 有条件：可展示真实液位，但须说明 ARM 测量；不能全归功 CNN |
| <a id="e16"></a>E16 | 当前预览为 HTTP RGB565 二进制及元数据，平台转 JPEG、WS 推送 | [engine.cpp](../../camera/terminal/engine.cpp)：`preview`、`/frame`；[manager.py](../../camera/terminal/manager.py)：`PreviewHandler`、8879、`/preview`；[terminal-client.ts](../../apps/server/src/devices/terminal-client.ts)；[terminal-preview.ts](../../apps/server/src/devices/terminal-preview.ts)：`parseTerminalFrame/readTerminalPreview`；[devices.service.ts](../../apps/server/src/devices/devices.service.ts)：`device.preview.frame` | S | 高；服务端 sharp 转码；不能写“当前视频全部经 UDP”或把预览 WS 接收 FPS 等同件速 | 可：录真实端侧/平台同帧；不用长展示协议 |
| <a id="e17"></a>E17 | 裸机 UDP/WinUI 与 Vitis/JTAG 路径仍保留；两项 BSP 修复可复现 | [create_app.py](../../camera/create_app.py)：源列表、`FPU_HARD_FLOAT_ABI_ENABLED`、`LWIP_ALLOW_MEM_FREE_FROM_OTHER_CONTEXT`；[live_main.cpp](../../camera/int8/live_main.cpp)、[udp_output.cpp](../../camera/udp_output.cpp)、[run_live.tcl](../../vitis_live/run_live.tcl)、[BoardClient.cs](../../camera/winui/BoardClient.cs) | S/G | 高：代码存在；不是当前 Linux 运行时能力的证明 | 有条件：作演进背景，主视频不宜混用两套控制界面 |
| <a id="e18"></a>E18 | 曾完成 QSPI+SD 自启动及后续单运行时持久化；当前启动源未复查 | [build-boot.ps1](../../camera/terminal/build-boot.ps1)、[rcS](../../camera/terminal/linux/rcS)、[inittab](../../camera/terminal/linux/inittab)；[10-19 verification](../../temporary/terminal_qspi_20261019/verification.json)、[sd-flash-result.json](../../temporary/terminal_flash_20261019/sd-flash-result.json)；[10-20 verification](../../temporary/unify_runtime_20261020/verification.json)：`sd_boot` | S/T/D | 高/中：有烧写/回读、用户断电确认摘要及 bootId/进程记录；10-19 描述 QSPI FSBL+PL+U-Boot，10-20 描述 SD BOOT.bin；具体选择须现场核对 | 有条件：需当前同版本无 JTAG 冷启动实拍 |
| <a id="e19"></a>E19 | 模型包固定模板校验，产品类别需对应；Linux 能力不开放固件 OTA | [hardware.cpp](../../camera/terminal/hardware.cpp)：`load_model` 的 size/CRC/SHA/version/graph 校验；[zynq-profile.ts](../../apps/server/src/models/zynq-profile.ts)：`validate...`/固定包常量；[engine.cpp](../../camera/terminal/engine.cpp)：`set_model/set_product`；[terminal-state.ts](../../apps/server/src/devices/terminal-state.ts)：`firmwareUpdate:false` | S | 高：6416360B包=128头+6350208权重+66024元数据；不能用裸机 OTA 源码宣称当前 Linux A/B 固件远程升级 | 可：模型换型+规则分配；不演示不存在的能力 |
| <a id="e20"></a>E20 | 固定图训练/量化导出/参考由 PC 侧 PyTorch 完成，非 FPGA 训练 | [train.py](../../camera/training/train.py)：`run`、split/seed、CUDA/AMP、export；[pl_model.py](../../camera/training/pl_model.py)：`FixedGraph/export_int8/integer_forward`；[training.service.ts](../../apps/server/src/models/training.service.ts)；[schema.prisma](../../apps/server/prisma/schema.prisma)：Dataset/TrainingJob/Model/InspectionBatch 等 | S | 高：流程实现；独立测试集效果、模型数据来源许可、训练结果与实场景泛化另需证据 | 有条件：作为换型配套，不用训练界面代替 FPGA 原理 |

## D. 实现报告、性能与验证结果

| 编号 | 结论 | 证据位置与定位方式 | 类型 | 可信程度/限制 | 是否适合视频 |
|---|---|---|---|---|---|
| <a id="e21"></a>E21 | 含 HDMI 的全设计 Routed：LUT45299、FF60859、BRAM112.5 Tile、DSP217 | [utilization.rpt](../../hardware/camera/build/terminal/utilization.rpt)：Date/Design State、Slice Logic/Block RAM Tile/DSPs；[timing.rpt](../../hardware/camera/build/terminal/timing.rpt) 时钟摘要；[build.tcl](../../hardware/camera/build.tcl)：125 MHz | R/S | 高：10-20 报告原件；分母53200/106400/140/220；分别85.15/57.20/80.36/98.64%；不是当前板卡实时采样 | 可：写“125 MHz，布局布线报告”，不要写“实时资源实测” |
| <a id="e22"></a>E22 | 时序数值通过但不构成完整签核；报告与现存 bitstream 有实验 hash 关联 | [timing.rpt](../../hardware/camera/build/terminal/timing.rpt)：WNS0.060/WHS0.046、no_input_delay1/no_output_delay8；[bus_skew.rpt](../../hardware/camera/build/terminal/bus_skew.rpt)：摘要4条/最小slack6.670；[final-results.json](../../temporary/fps_optimize_20261020/final-results.json)：hardware.bitstreamSha256；[正式 bit](../../hardware/camera/build/terminal/system_wrapper.bit) | R/T/I | 高：本轮 SHA 比对正式与实验副本一致；报告 Date/原始路径吻合。未证明现场加载/全部启动副本一致；欠缺 I/O delay 解释 | 有条件：不写“所有接口已完全签核” |
| <a id="e23"></a>E23 | 10-20 RGB 含显示约两分钟15.21检测FPS；6黄金向量及3回放通过 | [final-results.json](../../temporary/fps_optimize_20261020/final-results.json)、[presentation-results.json](../../temporary/fps_optimize_20261020/presentation-results.json)、[final-summary.json](../../temporary/fps_optimize_20261020/final-summary.json)；[final-golden-results.txt](../../temporary/fps_optimize_20261020/final-golden-results.txt)：`GOLDEN_VERIFY_PASS/GOLDEN_CAPTURE_PASS`；[final-adopt-results.txt](../../temporary/fps_optimize_20261020/final-adopt-results.txt) | T | 高：121.527s、15.2147/15.2184 FPS，6×8085=48510输出字节，hashc046d903…；underflow377不增长；当时 boot未更新、runtime-only；非长期/精度 | 有条件：历史主性能候选，标模型/日期/显示开启；需新实拍配合 |
| <a id="e24"></a>E24 | 旧液位模型 ARM 标量 vs PL 约254.7×，不能当最优 ARM 基线 | [results.json](../../temporary/arm_vs_pl_20261022/results.json)、[cpu_infer.cpp](../../temporary/arm_vs_pl_20261022/cpu_infer.cpp)、[validate.py](../../temporary/arm_vs_pl_20261022/validate.py)、[report.md](../../temporary/arm_vs_pl_20261022/report.md) | T/S/I/D | 高：原始数组可复算，ARM2次均值16725.7585ms；PL15次中位65.680ms、范围65.216～76.450。中：执行摘要，缺当次共同输入PL对拍；8085字节零差异为CPU与Python验证 | 有条件：必须带“单核标量INT8、旧LEVEL-v3、纯33命令区间”；255不是当前实时检测结论 |
| <a id="e25"></a>E25 | 10-23 MILK RGB 恢复约15 FPS，NEON 阴影校正保持等价 | [results.json](../../temporary/fps_recover_20261023/results.json)、[final_deploy.py.log](../../temporary/fps_recover_20261023/final_deploy.py.log)；[hardware.cpp](../../camera/terminal/hardware.cpp)：Q8 gains NEON | T/S | 高：记录30s、三次样本均值15.0368，engine hashfbdbeacc…；12完整帧/全部RGB565色/Q8 64～1024等价为摘要；无物理过件/液位持续性能验证 | 有条件：只作该版本恢复结果，不能混进最新液位曲线 |
| <a id="e26"></a>E26 | 10-24 液位空场7.31→14.10 FPS；有瓶函数148.786→77.4082ms | [results.json](../../temporary/level_fps_20261024/results.json)、[bench_board.py.log](../../temporary/level_fps_20261024/bench_board.py.log)、[deploy.py.log](../../temporary/level_fps_20261024/deploy.py.log)、[before.txt](../../temporary/level_fps_20261024/before.txt)、[after.txt](../../temporary/level_fps_20261024/after.txt) | T | 高：无标签、生产停止、hash3aca8253…，3样本13.9862/14.1469/14.1538；35案例等价记录；有瓶为函数bench且原引擎运行；不是有瓶产线14FPS | 有条件：更适合报告，视频若用必须显著标“无标签场景” |
| <a id="e27"></a>E27 | 跟踪/规则有可核对合成测试，不能代表真实精度 | [tracking verification](../../temporary/tracking_20261021/verification.json)：checks97/crossingIdSwitches0/scope；[runtime verification](../../temporary/runtime_finish_20261020/verification.json)：rulesParityCases21；[board-tests.log](../../temporary/runtime_finish_20261020/board-tests.log) | T/D | 高/中：合成序列及规则一致性；源码后来还有变化，非当前产线IDF1/MOTA；不能说所有检测零差错 | 有条件：显示方法和复核意识，具体分数不作识别准确率 |
| <a id="e28"></a>E28 | 液位移植有参考/ARM/回放/API证据，但物理验证覆盖有限 | [native-verification.json](../../temporary/level_port_reference_20261022/results/native-verification.json)、[model-verification.json](../../temporary/level_port_reference_20261022/results/model-verification.json)、[deployment-verification.json](../../temporary/level_port_reference_20261022/deployment-verification.json)、[all_results_new.json](../../temporary/level_low_test_20261022/all_results_new.json) | T/D | 高：旧hashd64e7b51…、旧band85～98.5；瞬态实瓶明确acceptedAsPhysicalValidation=false；341记录含模拟/无真值，不能算准确率；不等于v1.3完整验收 | 有条件：仅作为历史回放依据；最新高/合格/低/无液面需实拍 |
| <a id="e29"></a>E29 | Linux 模型/产品/批次双向操作、预览、SD持久化有历史闭环记录 | [verification.json](../../temporary/unify_runtime_20261020/verification.json)：api_test/manager_test/end_to_end/sd_boot；[v2-e2e-results.json](../../temporary/unify_runtime_20261020/v2-e2e-results.json)、[live-results.json](../../temporary/unify_runtime_20261020/live-results.json)；[terminal-batch.ts](../../apps/server/src/inspections/terminal-batch.ts) | T/S/D | 高/中：真实e2e数据与汇总相互支持；日期10-20、MILK测试产品；当前数据库/产品未查询，不继承现场状态 | 可：单件与批次闭环很适合真实录屏，正式拍摄前重核当前配置 |

## E. Git 决策、失败候选、复用与素材

| 编号 | 结论 | 证据位置与定位方式 | 类型 | 可信程度/限制 | 是否适合视频 |
|---|---|---|---|---|---|
| <a id="e30"></a>E30 | 从 INT16/PL自主序列器转为 INT8/PS逐条启动，不能混用架构 | `git show 04a96fa`、`git show bc59dec`、`git show 56aecb6`、`git show bec917a`；[int8_rebuild_test](../../temporary/int8_rebuild_test/board.cpp)、[test.cpp](../../temporary/int8_rebuild_test/test.cpp)、[run_board.tcl](../../temporary/int8_rebuild_test/run_board.tcl)；[当前 top.cpp](../../hardware/hls/src/top.cpp) | G/S | 高：当前与历史源码架构；中：历史35阶段/三次上板数字只留提交和脚本，本轮查看目录无对应build结果 | 可：做有依据的架构演进，不以提交数量计成果 |
| <a id="e31"></a>E31 | 10-15 多次改进来自搬运/量化/调度，而非改变网络精度或一味加DSP | `git show fecf226/ad1cbf7/de2d083/e0bcc33`；[conv_load_test/compare.py](../../temporary/conv_load_test/compare.py)、[micro_io_test](../../temporary/micro_io_test/board.cpp)、[input_pair_test/compare.py](../../temporary/input_pair_test/compare.py)、[loader_test.cpp](../../temporary/input_pair_test/loader_test.cpp)、[rtl_test.py](../../temporary/input_pair_test/rtl_test.py) | G/S | 中：67.442→58.893ms等来自提交正文；保留脚本但原始配对输出缺失。后续图表需补原始结果，不把跨版本数字直接连线 | 有条件：可讲优化方法；数字暂不作为最强主结论 |
| <a id="e32"></a>E32 | 存在失败候选退出及资源取舍，速度不是唯一门槛 | `git show 04a96fa`：127.941→133.667ms变慢；`git show ad1cbf7`：组合输入缓存因拥塞停止；`git show de2d083`：BRAM FIFO多16 BRAM18K未采用；[evidence.md](../../skill/fpga-accelerator-workflow/references/evidence.md)：错误量化流水hash失配105阶段摘要 | G/D | 高/中：取舍记载可查；早期失败hash缺原始结果，不能编造完整调试过程。后续fecf226验证通过，不把早期失败状态当当前问题 | 有条件：报告很有价值，视频只取一个清晰案例 |
| <a id="e33"></a>E33 | 裸机NEON中断与lwIP内存释放曾导致真实工程问题，当前生成配置已保留修复 | `git show e52338d`、`git show 1cdac02`、[create_app.py](../../camera/create_app.py)；[USB verification](../../temporary/usb_input_20261019/verification.json)、[mouse-verification.json](../../temporary/terminal_qspi_20261019/mouse-verification.json) 补充板级输入边界 | G/S/T | 高：配置/日志字段；中：100s1789帧等历史描述；30FPS是裸机纯预览。鼠标evdev注入与物理手动验收分开，后者记录false | 有条件：体现定位能力，不能把短测写长期稳定 |
| <a id="e34"></a>E34 | 新增track ID瓶盖累计与永久拒绝记录跳过，计数/同步语义须分开 | `git show 8e7622f`、`git show 5bcc771`；[engine.cpp](../../camera/terminal/engine.cpp)：`count_belt/sync`、`.rejected`；[probe2.py.log](../../temporary/belt_count_20261024/probe2.py.log)、[testcaps.py.log](../../temporary/belt_count_20261024/testcaps.py.log) | G/S/T | 高：当前实现；中：最新提交称队列9→0但不是全部成功入库，永久拒绝证据仍在；轨迹ID计数尚无带真值的误差统计 | 有条件：必须真实已知数量演示；禁止把本帧框数当累计件数 |
| <a id="e35"></a>E35 | 初始网络/算子有作者参考基础；不能宣称全部从零原创 | `git show --stat 0bf4ae4`、`git show --stat e19a41f`，后者标题“preserve author operator sources as optimization baseline”；[早期 PROJECT_GUIDE](../../PROJECT_GUIDE.md)、[根目录 yolo4_tiny.cpp](../../yolo4_tiny.cpp) | G/S/D | 高：复用事实；待确认：原作者姓名、仓库URL、完整许可与模型/数据授权未从这些材料确认。本轮未修改同级参考工程 | 有条件：在报告准确归属，视频说具体自研优化不说原创YOLO |
| <a id="e36"></a>E36 | 有AI协作元数据/经验包，但还没有可提交的完整原始交互证据 | `git show -s 5bcc771/9a204dc/2a71512`：Claude Code协作标记；[AGENTS.md](../../AGENTS.md)、[Skill总说明](../../skill/README.md)、[workflow SKILL.md](../../skill/fpga-accelerator-workflow/SKILL.md)、[evidence.md](../../skill/fpga-accelerator-workflow/references/evidence.md)、[diagnostic SKILL.md](../../skill/fpga-engineering-tools/SKILL.md) | G/D/S | 高：存在辅助流程及包使用/边界说明；中：决策摘要；不能反推人员/AI逐行贡献。本轮未读取私人聊天；跨板/PYNQ复用未证实 | 有条件：可讲验证方法；提示词/回答/纠错需队员提供可公开原件 |
| <a id="e37"></a>E37 | 多项工具/IP/库复用明确，有些依赖固定版本，许可清单尚未统一 | [prepare_deps.ps1](../../camera/terminal/prepare_deps.ps1)：nlohmann/json3.12.0、httplib0.20.1、LVGL9.4.0、FreeType2.13.3及commit；[CMakeLists.txt](../../camera/terminal/CMakeLists.txt)、[vision_mqtt.py](../../camera/terminal/vision_mqtt.py)；[XP.css许可](../../camera/terminal/assets/xp/XP.css-LICENSE.txt)、[winXP许可](../../camera/terminal/assets/xp/winXP-LICENSE.txt) | S/D | 高：声明/许可文件存在；根项目未见统一LICENSE。MQTT配置不是物理剔除成功证据；不能承诺成熟工业安全性 | 可：报告写复用边界，视频不堆库名 |
| <a id="e38"></a>E38 | 旧指南/白皮书混有历史状态或未经验证目标 | [PROJECT_GUIDE.md](../../PROJECT_GUIDE.md)：10-11状态；[TECHNICAL_BASELINE_SPECIFICATION.md](../TECHNICAL_BASELINE_SPECIFICATION.md)：§1.1的30ms/30FPS目标、裸机/OTA与Linux混写；[旧液位deployment](../../temporary/level_port_reference_20261022/deployment-verification.json) | D/S | 高：文本冲突可核对；低：目标已达成、工业成熟度等说法。旧技术文档PDF/DOCX存在，但未作为性能来源 | 否；用于排除不可靠表述 |
| <a id="e39"></a>E39 | 展示页同时有实时遥测与历史常量，不能把整页当同一实时测量 | [Showcase.vue](../../apps/web/src/views/Showcase.vue)：`PL_S=0.06567`、`resources`、`gmacs=fps*0.9775`、历史页脚；[showcase.png](../../temporary/video_demo_20261024/shots/showcase.png) | S/A | 高：已目视，顶端CAPS、历史基准页脚LEVEL-v3；动画中的完成帧数不是硬件采样；资源来自Routed；图上“实测”标签不足以统一口径 | 有条件：重录/加清楚历史测试说明；目前不能整页无说明用于性能证明 |
| <a id="e40"></a>E40 | 现有素材有空白、异常状态与未审视频，成功实物画面缺口大 | [real_pass.png](../../temporary/showcase_redesign_20261024/real_pass.png)；[screen.png](../../temporary/terminal_redesign_20261024/screen.png)、[preview-main.png](../../temporary/terminal_redesign_20261024/preview-main.png)；[样片-平台巡览.mp4](../../temporary/video_demo_20261024/样片-平台巡览.mp4)；[frame_01.png](../../temporary/level_low_test_20261022/frame_01.png)等仅登记 | A | 高：前3张已目视，全白/REVIEW/同步异常；视频仅确认存在13865744B，未逐帧审；液位样本图未全部视觉验收 | 空白否；异常图仅作问题说明；其余待审。新实拍成功闭环优先 |

## 关键测量的可复核细节

### E23：RGB 约两分钟试验

同一实验结果分开记录 detection 与 presentation，不能只挑一个称为“系统全部性能”。

| 字段 | 原始值 | 解释 |
|---|---|---|
| `sustained.seconds` | 121.527055976 | 非长时间可靠性测试 |
| `detectionFps` | 15.214718938 | 此次 engine 检测帧推进 |
| `presentationFps` | 15.218443094 | 此次显示呈现统计 |
| `presentationMedianMs/P95Ms/MaxMs` | 66.640812 / 83.325889 / 116.342851 | 显示间隔，非曝光到判定延迟 |
| `skippedIds` | 0 | 此实验呈现帧ID未跳过；不推出全采集链永不丢帧 |
| `underflows[].count` | 各次均377 | 区间无新增，不是从上电开始一直0 |
| `correctness` | 6 vectors / 48510 bytes / 3 replays / 30 preprocessing cases | 特定向量/回放的等价性，不是实物识别精度 |
| `deployment.sdQspiBootUpdated` | false | 当次运行优化不能自动当作重启后生效 |

后来的 E18/E29 有 SD 持久化/重启记录，但测试日期、运行时 hash 不同；没有新共同记录前，不将它们合并为“最新版冷启动后同样15.21FPS”。

### E24：ARM 与 PL 比较

模型为 `LEVEL-v3-20261022`、单通道，包 SHA-256 `d64e7b51b21930a6f213e94b462e6d7ab69405fbe99a3d091a89e0b17aa439ae`，Linux6.6.159，A9记录为666.667MHz。CPU是标量直接卷积参考（即使编译标志含 `-mfpu=neon` 也不能称为已做NEON内核优化），绑定CPU1，engine仍运行。

- ARM两次：16685.308、16766.209 ms，复算均值16725.7585 ms。
- PL十五次：76.450、65.938、65.680、65.468、65.848、66.012、65.745、65.646、65.452、65.216、65.802、65.493、65.461、65.857、65.671 ms。
- 本轮复算中位65.680 ms，16725.7585/65.680约254.655，取一位小数254.7倍合理。原摘要中位65.67属于近似，正文最大66.0遗漏了76.450样本，正式材料采用原数组。
- `hwConvMs`含33命令启动/轮询，不含图像前后处理、网络及多帧决定；`hwForwardMs`有采集预处理等待，不用于此纯算子比较。
- `validate.py`读取C++输出与Python整数计算比对；不能凭该句认定当次最新PL与参考共同输入全面一致。

### E26：液位优化

包 SHA-256 `3aca8253f829d85562fa3952a70df36e756fbecc399b30ebc5c4e08e983ab065`；engine记录 `bd0fbbb70de84c86caae0d1faf752d861ee5f1637ae37d76f9635061b25cd7ab`。

实机FPS采样明确为没有找到红标签、生产停止。无标签可直接跳过形态学，正是这一条件使优化后均值达14.0956 FPS。有标签fixture预处理还需77.4082 ms，此数又是在原引擎运行中测函数所得，无法据此可靠换算完整生产FPS。35个案例记录bbox/crop/row/strength/geometry/gray hash一致，说明代码改造保持了这些fixture的行为，不证明场景泛化或误检率。

## 本轮冻结的文件身份

这些 SHA-256 是本轮只读计算；只用于识别文件，不能独自证明源码、报告、板端三者完全对应。

| 文件 | SHA-256 / 关联 |
|---|---|
| 本地 `guide.pdf` | `c6ad82acd4f7bdcd13bd412e232ed85d05f2a87dd5e2cdd04f9d219f88b569fc` |
| terminal `timing.rpt` | `2a4c5ac167bac758553c12a5a4d19feb8990d82b923ef549757b1acde9837f6e` |
| terminal `utilization.rpt` | `3d1548e4786337e50aebfe1f43c542a0da2b428f8aa43427155d60760eca7de8` |
| terminal `system_wrapper.bit` | `1322b788d0fb06436374128d98ebafbb5105dd9f8be500d285a6e9acc4d81972` |
| `temporary/fps_optimize_20261020/hardware_rgb565_default4/system_wrapper.bit` | 与上一行完全一致；也与 E23 `final-results.json` 中记录一致 |
| 当前 HLS `.cpp/.h` | 本轮全部匹配 E08 `findings.json.source_sha256`；这是研究源码关联，未独立建立全部HLS生成产物的可复现证明 |

## 已发现但不作为本轮强证据的材料

| 材料 | 排除/降级原因 | 后续最小动作 |
|---|---|---|
| early `temporary/*_test/build/comparison.json` 等技能摘要指向的输出 | 本轮查看相应 int8_rebuild/conv_load/input_pair 等目录主要保留脚本，未找到对应原始build结果；提交数字不补造为现存文件 | 队员若有归档可补；没有则不把它作为核心数值图表 |
| cap便携包冻结验证 `summary.json` | 是图像名称到数量的映射，不能直接推出检测准确率或板上计数误差 | 核对标注、预测和采集场景，另组独立测试 |
| 液位341条汇总 | 包含模拟样本/无标签/缺真值，不能作为341次实物准确验证 | 只筛带明确来源和真值的样本，不以样本总量宣传 |
| 手机相机 `verification.json` | 证明权限、首帧/超时/取消等生命周期；不证明Zynq推理速度 | 移动端仅作配套体验证据 |
| UI 中运行5h55m、合格率或置信度 | 一个截图的运行时长/历史记录不构成连续正确性证明；合格率不是识别准确率 | 绑定真实连续录像、原始日志与真值再使用 |
| `.PASS`、`.exit=0`、文件存在 | 仅runner/程序退出或产物存在，不是时序/功能/板级全部通过 | 读取相应范围的报告与输出，未知仍标未知 |

## 素材可用性初审与最小补证清单

| 类别 | 已有入口 | 当前判定 | 下一步（须经阶段审核后另行执行） |
|---|---|---|---|
| 现有素材 | E21/E22实现报告，E09 HLS报告，E23/E24原始结果 | 技术画面依据足，可制作可读局部截图/图表 | 冻结版本后整理选用，不遮掉日期/模型条件 |
| 现有素材 | E39展示页、E40终端截图/巡览视频 | 存在混合口径、空场和异常状态，非成品成功演示 | 逐帧审样片；替换空白/不合适画面 |
| 需要实拍 | 板卡丝印/相机/接口、实际瓶盖或液位对象、HDMI同框 | 本轮未发现足够强的完整连续成功录像 | 固定照明构图；记录已知真值和操作顺序 |
| 需要录屏 | 当前模型/产品分配、启停、真实判定、证据详情、同步批次 | 旧e2e记录可参考，现场状态未知 | 使用同一冻结配置，成功/异常各留连续过程 |
| 需要制作动画 | 48×8阵列、双INT8打包、A/B缓存、DDR共享及PS交接 | 源码可支撑；尚未审定现有实验动画数值/边界 | 下一阶段挑少量原理，保持真实并行范围 |
| 尚不具备展示条件 | “工业级”“30ms闭环”“当前有瓶14/30FPS”“任意CNN”“最优ARM255倍”“物理自动剔除” | 无相应证据或表述超范围 | 不使用；确需主张时再针对性补测，避免全量重构/构建 |

更换软件、产品规则、模型、bitstream或测试条件后，保留旧记录并新增对应证据，不静默覆盖历史条件。

## F. 定向补充：牛奶盒应用与裸机优化历程

用户已明确牛奶盒案例为**盒面贴片模拟缺陷**，不是吸管缺失或液位检测。用户陈述用于界定展示对象；实现、速度和准确率仍按以下证据分别判断。完整解释与时间线见[03A](03A_OPTIMIZATION_TIMELINE.md)，新的定位见[03](03_PROJECT_NARRATIVE.md)。

| 编号 | 结论 | 证据位置与定位方式 | 类型 | 可信程度/限制 | 是否适合视频 |
|---|---|---|---|---|---|
| <a id="e41"></a>E41 | 牛奶盒贴片缺陷有独立模型链，不是液位；存在灰度/RGB及失败交付版本 | [v15 manifest](../../temporary/deploy_milk_20261017/manifest.json)、[v15 report](../../temporary/deploy_milk_20261017/report.json)、[交付说明](../../temporary/deploy_milk_20261017/README_给队长.md)；[旧适配清单](../../temporary/milk_model_import/MODEL_DELIVERY_STANDARD.md)；[吸管候选说明](../../temporary/model_train_20261018/milk_delivery/README.md) | S/D/T | 高：v15包2a25f824…、GRAY、单缺陷槽；report明确45张有标注训练集指标偏乐观，18照片旁证、预处理近似且未上板；旧不合格清单仅对应旧包。吸管28e1c5df…是另一个候选，不可冒称当前贴片模型 | 可：贴片案例有模型依据；不可把训练集mAP或18照结果写板上准确率 |
| <a id="e42"></a>E42 | RGB缺陷包有真实板执行记录；MILK-RGB-v3有运行证据，但其类别元数据存在冲突 | [live-verification.json](../../temporary/model_eval_fix/live-verification.json)：source=BOARD、candidateExecuted、RGB/缺陷、62638us；[历史diagnosis](../../temporary/model_eval_20261018/diagnosis.json)；[MILK-RGB旧包](../../data/storage/models/65ce8fc8-29a6-4ff9-b85e-53e95c3c636c)；[v3包](../../data/storage/models/61136c5e-efdd-4ca3-a25f-7546391866bc)；E23/E25；[data/app.db](../../data/app.db)仅定向只读Model查询 | T/S/I | 高：旧RGB包0f69bdf4…与执行记录对应，但无标注，accuracy等为null；v3=c046d903…/RGB，Model.manifest.classes仍是六钢材名，不能仅凭版本名确定语义或把它等同旧RGB包。数据库是2026-10-25本地快照，非板端现场状态 | 有条件：可讲模型执行能力；v3入片前必须确认训练语义/显示标签及实物结果 |
| <a id="e43"></a>E43 | 当前单缺陷类别不能自动等价于“好盒存在/合格过件” | [engine.cpp](../../camera/terminal/engine.cpp)：`set_product`要求至少一个minimum>0类别；[passage.h](../../camera/terminal/passage.h)：按必需主类触发；[core.cpp](../../camera/terminal/core.cpp)：`evaluate`；E41单defect槽；E15液位另有标签存在框 | S/I | 高：仅有缺陷框时无框无法区分好盒/空场/漏检；不能把缺陷类设为必需主类再声称无缺陷是合格过件。可用固定实物存在的人工核验/触发展示缺陷框，具体记录流程待验收 | 可：真实缺陷定位；自动好/坏件闭环未经补证不宣称 |
| <a id="e44"></a>E44 | 当前牛奶盒RGB与瓶盖RGB可复用同一固定PL结构，切换权重、量化元数据、标签和规则 | [v3包](../../data/storage/models/61136c5e-efdd-4ca3-a25f-7546391866bc)、[旧RGB缺陷包](../../data/storage/models/65ce8fc8-29a6-4ff9-b85e-53e95c3c636c)、[CAPS包](../../data/storage/models/f261f38b-8d78-4b22-9a0a-d8fa6ed5e625)、[graph.json](../../camera/training/graph.json)；[hardware.cpp](../../camera/terminal/hardware.cpp)：`load_model/prepare_capture`；[engine.cpp](../../camera/terminal/engine.cpp)：`set_model/set_product` | S/I | 高：本轮解析三包33×10命令逐项一致，与灰度模板仅首层ch_in=3不同；6416360B/CRC正确；元数据hash不同。兼容不证明切换已在当前板验收，非同时双模型推理；灰度版本还要改输入通道/预处理；只有液位专用hash进入level路径 | 可：同核换型的结构图；无需新HLS/bitstream的前提是兼容固定图及已支持输入模式 |
| <a id="e45"></a>E45 | “约1.7FPS”可追溯：10-11提交记载1.69；10-12原始数组可复算1.773445 | `git show 0fcf673`（20完整检测帧、91预览帧、1.69/7.53）；`git show d42e2d9`；[baseline_camera100_results.json](../../temporary/operator_pipeline_test/build/baseline_camera100_results.json)、[board_ps_test.py](../../temporary/operator_pipeline_test/board_ps_test.py)；`git show d42e2d9:temporary/camera_inference_test/live_main.cpp`、同版本`yolo4_tiny.h`/WinUI Postprocess | G/T/S/I | 高：原100MHz、裸机、416RGB→INT16×512、75×13/26头/20类旧YOLO；预热后51状态样本、50完整检测接收帧、约27.630s接收区间，infer538326us/cycle563805us/接收1.773445FPS、错误0。1.69仅提交记载，旧权重整包SHA未冻结 | 可：初期工程状态；不是牛奶/瓶盖模型的相同输入基线 |
| <a id="e46"></a>E46 | 同旧模型的INT16共享核/分块与时钟组合优化有配对数据1.773→2.971FPS | `git show ca6a832`；[production_camera142_results.json](../../temporary/operator_pipeline_test/build/production_camera142_results.json)、[baseline_camera100_results.json](../../temporary/operator_pipeline_test/build/baseline_camera100_results.json)；[142实现报告](../../temporary/operator_pipeline_test/build/shared44_weight_lanes_routed142/timing.rpt) | T/G/R/I | 高：本轮按原脚本复算：正式142.857MHz数据87状态样本、86完整检测帧、约28.609s；infer311175us/cycle336654us/2.971093FPS。保持旧模型、权重/INT16语义，硬件结构与频率共同改变，不能独立归因超频或一条loader | 可：有边界的局部受控对照；报告与“正式”运行关联依提交，勿混同各候选WNS |
| <a id="e47"></a>E47 | 256输入、相机/UDP和缓存采样构成后续阶段，曾有ARM采样支线随后恢复PL | `git show 1aa9528/1075a53/b83e9fc/04a96fa`；[realtime_256 board_test](../../temporary/realtime_256_test/board_test.py)、[fps8验证](../../temporary/fps8_test/board_test.py)、[网络256头](../../yolo4_tiny.h) | G/S | 中：6.605FPS/144.846ms；ARM采样+缓存两次60s约8.062FPS；随后恢复PL采样，PL基线7.37、sequencer7.07来自后续提交；原始数组当前未找到，不能把所有节点连接成递增曲线 | 可讲变化；256缩小是任务条件改变，ARM采样结果不能标全PL |
| <a id="e48"></a>E48 | INT8迁移先慢后快；早期101ms已因计时宏修正作废 | `git show bec917a/56aecb6/aef1e9d/bc59dec`；[board.cpp](../../temporary/int8_model_test/board.cpp)：括号修正；[INT8重建测试](../../temporary/int8_rebuild_test/test.cpp)、[当前packed multiply](../../hardware/hls/src/packed_multiply.h) | G/S | 高：计时修正代码；中：原始测量依提交。正确初期INT8约404.62ms，packed阶段356.80→241.443ms/3.91FPS，48×8+新布局125MHz约104.69ms/8.382FPS；224灰度六类钢材模型已不同于旧20类模型；不能用作同任务量化提速比 | 可：突出更换精度不自动提速、数字必须验证；禁用作废101ms |
| <a id="e49"></a>E49 | INT8同图后续围绕供数/重定标/池化/输出和PS交叠优化 | `git show 78bd8c2/45d6ce0/fecf226/ad1cbf7/de2d083/e0bcc33`；E10/E31；[frame_pipeline](../../temporary/frame_pipeline_test/measure_udp.py)、[pool compare](../../temporary/pool_burst_test/compare.py)、[input_pair RTL](../../temporary/input_pair_test/rtl_test.py) | G/S | 中：同INT8模型的局部配对数值在提交中有条件说明，但相关原数组缺；可查104.690→95.718→90.105→81.088→71.673→68.078→67.438ms，成对读同ELF67.442→58.893ms；短UDP先9.396、最终约15.008FPS，不能把所有百分比相乘 | 可：重点画机制，数字以局部明确对照为限，注明历史记录 |
| <a id="e50"></a>E50 | 裸机约16FPS来自传感器根分频改动后的16.604FPS记录；30FPS是纯预览 | `git show ac57d05/536a0e2/1cdac02`；[三模式probe](../../temporary/camera_fps_test/probe.cpp)、[UDP测速脚本](../../temporary/camera_fps_test/measure_udp.py)、[完整性脚本](../../temporary/camera_quality_test/check_stream.py)；[create_app.py](../../camera/create_app.py) | G/S | 中：ac57记载125MHz PL不改bit、224灰度INT8、摄像头416RGB565、帧期66.624→33.311ms、预览30.017FPS、检测+预览16.604FPS/infer60.077/cycle60.257ms；源码脚本每模式3s、去预热3样本，原始采样文件未找到。后续提交16.603与16.54不是同一次测试；100s1789帧不可直接解成检测17.89FPS | 可：标“裸机历史短测”；不写Linux16FPS或两个应用均16.6FPS，原始数据待追补 |
| <a id="e51"></a>E51 | 有“算子RTL变快但整机失败”的直接失败证据 | [channels_comparison.json](../../temporary/operator_pipeline_test/build/channels_comparison.json)：pointwise54.12%更少周期但125MHz WNS-0.341；[pool_rows_comparison.json](../../temporary/operator_pipeline_test/build/pool_rows_comparison.json)；`git show 594c6f8/300e1bd/d42e2d9/ca6a832`；E32 | R/T/G | 高：配对RTL/失败门槛原JSON；中：dual-bank7229 slices>6664、读握手拥塞、166MHz失败与退回142.9来自提交。拒绝的候选不能列成功FPS，更不是所有方案均部署过 | 可：用一个资源/时序门槛解释取舍，不做提交列表 |
| <a id="e52"></a>E52 | 牛奶贴片实物参考照可用，但尚缺对应实机连续检测片；历史运行与缺陷语义要分开 | [golden_photo.jpg](../../temporary/milk_int8_20261017/给队长_牛奶换型包_int8_20261017/牛奶_int8_w8a8/golden_patches_4/golden_photo.jpg)；E41/E42；[旧接收result](../../temporary/camera_inference_test/received/result.json)、[preview.png](../../temporary/camera_inference_test/received/preview.png)；E40已有平台素材 | A/T | 高：本轮目视到饮料盒面白贴片、深背景，是静态参考不是板测视频；顺手抽查的`inspection_terminal/board-7.png`实际是USB原理图，不是应用截图。旧接收张量75通道不属于MILK/CAPS当前头，不能套用 | 有条件：参考构图/模拟缺陷定义；需新补实物+模型身份+检测输出对应 |

### 定向复核方法与身份

- 本轮使用只读SQLite连接，查询范围仅`Model`表中4个指定版本的`name/version/manifest`，未访问账号、凭证或生产业务记录。示例条件：`WHERE version IN ('MILK-RGB-v3-20261018','MILK-RGB-20261017','milk-v15-20261017','CAPS-RGB-v1-20261022')`。不从这张本地表推断板端当前加载状态。
- E44本轮读取包头、CRC和元数据前330个小端int32，按33×10与`graph.json`比较。RGB三包仅比灰度模板多首层ch_in=3；三包之间命令完全相同，但量化参数和权重不同。未执行推理、部署或改写包。
- E45原始JSON SHA-256：`2bd653d5e48d1760aea95362dc04ce98143395d199305024c579d291e0cc9889`；E46正式142数据JSON SHA-256：`5418a9cd280c649fa6b2e3fe7e7d1cbe81f75c10ef04561106cd20c10fd01b56`。本轮按`board_ps_test.py`过滤CST1状态及预热，并按完整组帧接收时间复算FPS，未重跑板测。
- 在已定位的`camera_fps_test`/`camera_quality_test`目录中只有测试源和脚本，无其脚本所写的`build/short_udp_results.json`等原输出。E50保留Git记载与方法证据等级，不把缺失数据补写为新数组。
