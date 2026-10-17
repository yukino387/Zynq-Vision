# FIELD / IoT Vision Platform

本地 pnpm Monorepo / NestJS Modular Monolith。开发仓库仍为 `C:/00_workplace/fpga/cnn_accelerator`，现有 HLS、Vivado、PS 和 CNN Studio 保留。

## 责任与数据流

| 边界            | 责任                                                                                   |
| --------------- | -------------------------------------------------------------------------------------- |
| Zynq            | OV5640 采集、PS 灰度预处理/调度、PL 卷积、原有 UDP 输出                                |
| DeviceTransport | 原有协议适配、分片重组、预览解码、设备回报；不替代 PL 推理                             |
| Server          | JWT/角色、命令排队、证据保存、审核、标注版本、数据集快照、模拟训练、模型制品和部署状态 |
| Web             | 工程工作台、证据查看、数据与模型生命周期、设备控制、Debug、审计                        |
| uni-app         | 任务导向采样、相机入口、IMU 提示、本地原图队列、幂等上传、复核                         |
| Simulator       | 明确标记 SIMULATED 的帧、候选框、遥测、故障和部署回执                                  |

`Capture → RAW + Preview + reconstructed input → Sample → Inspection → Review/Hard Sample → versioned AnnotationSet → DatasetItem snapshot → Freeze → SIMULATED Training → ModelArtifact → compatibility Benchmark → SIMULATED Deployment → receipt → rollback`。

实时预览仅缓存完整的最近帧，不逐帧写 SQLite。采样才创建资产和检测实体。WebSocket 承载更新，REST/SQLite 提供持久状态。页面重连先取 snapshot；网络离线和设备运行状态分别表达。

原始资产写 `data/storage/`，数据库为 `data/app.db`，SQLite WAL 开启。文件 UUID 键防止路径穿越；SHA256 绑定制品和证据；没有覆盖原图的操作。

## Repository audit / 2026-10-16

- 原仓库没有 Node、Web 或 uni-app 项目；可复用 `camera/udp_output.cpp`、`camera/int8/live_main.cpp`、`camera/int8/gray.cpp`、`camera/winui/BoardClient.cs` 和 `Postprocess.cs`。
- 摄像头实际为 416×416 RGB565_LE，输入为 224×224×1 INT8（灰度 0..127），输出为 33×7×7 和 33×14×14；六类由现有后处理定义。
- 传输是 CNC1 / CST1 / YLO1 小端二进制；详见 [device-protocol.md](device-protocol.md)。不能用 HTTP 替代板端协议。
- Prompt 中 95.718 ms 基线不是当前值。本次短测实际状态出现 inference 59502 μs、cycle 59685 μs、errorCode 0；这是一次短测的状态读数，不是长期稳定性或提速结论。
- 真实模型版本、固件版本、设备时钟、设备唯一序列号、逐层耗时：当前 wire protocol **UNKNOWN / NOT REPORTED**。本地注册 serial 和源码协议标识不等于设备报告。
- 真板模型下载、双槽、自检部署回执、计划更新、离线结果回传：**UNAVAILABLE**。真实部署 API 返回 422，不会把模拟成功用于真板。

## 当前验证边界

`pnpm test` 验证服务端权限、UDP 重组、模型输入端点、后处理、幂等、冻结不变性、模拟训练/部署/回滚、配对和 WebSocket 鉴权。真实 UDP 已完成状态、预览、采样、输出与遥测短测，并恢复测试前暂停状态。

uni-app H5 可构建；原生安装包、手机真机 IMU/相机、长时间网络与偏绿问题仍需真机验证。不存在真正 YOLO 训练或 mAP 测量；当前 Benchmark 明确记录 `candidateExecuted:false`，仅验证模拟配置兼容性和当前模拟遥测。
