# 硬件接入与差异

本页保留裸机 UDP 接入记录。Linux 终端的 HLS 装载重叠优化、实测性能及验证边界见 [CNN 加速器性能记录](cnn-accelerator-performance.md)。

不改 `hardware/`、`camera/` 或 `vitis_live/`。适配位置 `apps/server/src/devices/zynq.ts`、`packages/device-protocol/`。业务服务不接触 UDP socket。

主机配置 169.254.140.109，当前板端配置 169.254.140.110:5001；以 .env 和实际网卡为准。Zynq 注册项是配置端点，不冒充固件报告的唯一身份。固件目前没有版本发现字段。

真实验证顺序：确认 CNN Studio/5002、5003 占用 → GET_STATUS（不接管）→ 保存原运行状态 → command1 接管 → 接收完整 raw/out0/out1 → decode/postprocess → 保存 Sample/Inspection → 恢复原 running → 断开本地 transport。

2026-10-16 本机验证得到真实 48 字节状态、RGB565 帧和两个输出头，成功保存 source=BOARD 的样本。该短测状态包含 cycle=59685 μs、inference=59502 μs、errorCode=0；没有进行 HLS、布局布线或烧录，不是性能优化结果。本次发现板端初始暂停，测试后恢复暂停。偏绿和长时间稳定性未在本次判定。

RAW、Preview、从原始帧重建的 MODEL_INPUT/MODEL_INPUT_PREVIEW 和两个 TENSOR_OUT 资产可保留。重建代码移植自 gray.cpp（RGB565 bit replication → 整数 BT.601 → 两遍带裁剪 resize → floor((gray*127+127)/255)），读取现有系数表。输入证据标记 SERVER_RECONSTRUCTION，未获得板端直接输入字节确认。

## 尚需固件协议支持的功能

| 功能                | 当前状态     | 需要实际设备新增的报告/确认                     |
| ------------------- | ------------ | ----------------------------------------------- |
| 固件/模型/plan 版本 | NOT REPORTED | 版本字段、持久身份、协议协商                    |
| 层耗时              | NOT REPORTED | 明确每层时间及量纲，不能拿总延迟代替            |
| 模型上传            | UNAVAILABLE  | 分块制品、大小/hash/manifest 验证和设备 ACK     |
| 双槽与回滚          | UNAVAILABLE  | 槽状态、原子切换、自检结果、active version      |
| 离线补传            | UNAVAILABLE  | 本地持久队列、序号、幂等确认                    |
| DSP/DDR/BRAM 利用率 | NOT REPORTED | 可验证测量源；不能用 HLS 资源估算伪装实时使用率 |

这些字段在 UI 显示未知/不可用，不能通过数据库填写成设备“已报告”。JTAG 加载仍是现有正式入口，不等于更新开机镜像。
