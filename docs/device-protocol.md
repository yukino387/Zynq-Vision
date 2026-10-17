# 现有 Zynq UDP 协议

来源：`camera/udp_output.cpp/.h`、`camera/int8/live_main.cpp`、`camera/winui/BoardClient.cs`。本平台没有修改固件。

端点配置默认 `169.254.140.110:5001`；Server 独立接收端口为 5003，CNN Studio 为 5002。所有 u32/i32 为 little-endian。

## Command / 16 bytes

| offset | type | value             |
| ------ | ---- | ----------------- |
| 0      | u32  | 0x31434e43 / CNC1 |
| 4      | u32  | request ID        |
| 8      | u32  | command 0..4      |
| 12     | i32  | value             |

0 查询状态（不接管 peer），1 接管接收端并启用 preview/running；2 设置 running，3 设置 camera_only，4 亮度 -4..4。除命令 0/1 外，只有当前 peer 可以修改控制状态。状态响应不含独立 ACK 字段，控制后必须核对回报。

旧协议的一字节 0/1 只设置 peer 和 preview；本 Adapter 使用 16 字节命令。

## Status / 48 bytes

依次为 `magic=0x31545343, request, device=0x7020, flags, frame, capture_us, conversion_us, inference_us, transfer_us, cycle_us, errors, brightness(i32)`。

flags：bit0 running、bit1 camera_only、bit2 preview。`errors` 是当前固件错误码（1 亮度、2 采集、3 推理/传输路径），不是累计错误计数。时间来自现有重叠流水线，不能相加解释为独立硬件负载。

没有设备时间戳、版本字符串、层耗时或硬件利用率。Adapter 的 receivedAt 为服务器接收时间，timestamp 保持 null。FPS 只由非零 cycle_us 计算。

## Frame fragments

20 字节头：`magic=0x314f4c59, frameId, type, totalBytes, offset`，随后最多 1400 字节。类型 0=1617 字节 INT8 head0，1=6468 字节 INT8 head1，2=346112 字节 RGB565_LE。

必须检查端点、magic、总长度、offset 对齐、尾片长度和完整性。乱序/相同重复片可接受；冲突重复片丢弃；最多 3 个组装帧，2 秒过期。完整帧才进入预览；正常推理要求三个 stream，camera_only 仅要求 type2。帧号按独立键处理，支持 u32 回绕。

RGB565 解码和 YOLO sigmoid/anchors/scales/NMS 对齐现有 C# 源码。Server 做检测头后处理，卷积仍由 PL 执行。224 输入为从原始帧按 `gray.cpp` 和整数系数重建的派生资产，来源明确标记，不能称为板端直接上报的输入。

固件没有释放 peer 命令；断开 Server socket 不代表恢复其他客户端的 peer。测试若改变 running，应按测试前状态恢复。CNN Studio 再连接会通过 command1 接管。
