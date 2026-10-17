# 实时事件

默认路径 `/ws`。浏览器连接后发送第一条消息 `{token:<JWT>}`；5 秒未鉴权、无效/过期 token 或用户被禁用时关闭 1008。JWT 不放进 URL。身份仍由 REST 校验；不要在二维码中放 JWT。

事件：`{type,requestId,timestamp,entityId,version:1,payload,source,sequence,schemaVersion:1}`。source 为 SERVER、BOARD、MOBILE、IMPORT 或 SIMULATION。SIMULATION 在 UI 显示 SIMULATED。

成功鉴权后 `session.ready` 包含 snapshotUrl。客户端 GET `/api/devices/policy`、`/api/devices/snapshot`，再使用后续事件更新。断开显示 WS RECONNECTING，REST 历史仍可读；重连重新加载快照。Preview 的 sequence 不等于持久检测计数。

主要类型：device.telemetry、device.status.changed、device.preview.frame、device.inspection.completed、device.error、training.progress/completed、deployment.progress/completed、job.failed。

preview payload 为 frameId、receivedAt、width/height、JPEG base64 和 detections；原始协议仍是 RGB565。慢客户端超过 2MB 待发数据时丢预览，其他消息无法继续发送时关闭 1013。每帧不写数据库；样本/检测与关键状态变更分别持久化。

WebSocket 是通知通道，不是审计或业务数据库。部署 ACTIVE 必须检查实际 DeviceTransport 回执与 reported model，不能由 UI 的进度条决定。
