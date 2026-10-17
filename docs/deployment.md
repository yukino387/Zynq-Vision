# 模型发布与回滚

manifestSchema 由 contracts 共享。检查 networkTemplate、firmwareInterfaceVersion、preprocessProfile、input width/height/channels/dtype、output shapes、classCount/classes、量化参数与 artifact SHA256/size。

每次读取模型 artifact 都重新计算 SHA256，不相信数据库声明的 hash。JSON 属性顺序不影响兼容性；数值与数组仍严格比较。模拟 profile 使用可稳定 JSON 往返的数值常量。

Training 仅接受 FROZEN dataset，分 Preparing Dataset、Loading Samples、Training、Validation、Exporting、Quantization、Packaging、Completed。真实样本读取和校验真实执行，但训练数学过程和产物是 **SIMULATED TRAINING / SIMULATOR_FIXTURE_ONLY**。它不是可部署到 FPGA 的 YOLO 权重。

Benchmark 当前执行 Simulator profile 兼容性及当前遥测记录，`candidateExecuted:false`，accuracy、precision、recall、mAP 为 null。它不会宣称评估了真实模型精度。

模拟发布经 APPROVED → DOWNLOADING → VERIFYING → VERIFIED → ACTIVATING → SELF_TEST → ACTIVE。只有回执 downloaded、verified、loaded、selfTest、active 全为 true，checksum 匹配，transport 当前模型等于目标，才写 ACTIVE。Desired State 只表示目标。

设备命令统一经 CommandsService，每设备串行，队列上限 8，记录 requestId、状态、attempts、结果和错误。不同设备可以独立排队。当前没有对有副作用命令自动重试。

模拟设备在候选失败时保留之前的模型。部署保留 previousVersion，管理员/工程师可执行 rollback；回滚也经过 artifact 校验和设备自检回执。新版本激活后，旧 ACTIVE 记录变为 SUPERSEDED；回滚后恢复相应旧模型的历史发布状态。失败会保持 FAILED，而不是返回虚假成功。真板没有部署协议时直接 NO_CAPABILITY / 422。

导出 zip 包含 manifest、weights、metadata、checksum；模拟 weights 文件明确命名 simulated，不会生成或替换 ELF/bitstream/SD/QSPI 启动镜像。
