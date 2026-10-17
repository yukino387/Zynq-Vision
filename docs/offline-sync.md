# 离线与同步

手机原图先持久化，再加入队列。H5 使用 IndexedDB Blob；原生端使用 uni.saveFile，队列元数据用 uni 存储。状态 QUEUED / SYNCING / FAILED / SYNCED，持久化 attempts、nextRetryAt、error、serverId。

每个样本固定 clientId、idempotencyKey、capturedAt、localSequence。失败不会更换键，服务端唯一约束和请求串行化防止并发重复。网络超时后重试会返回已经创建的样本。不同用户不能使用相同 key 读取他人幂等结果。

同步顺序逐个上传，失败按指数退避（最高 60 秒）保留原图，手动“同步全部”可立即重试。仅收到服务端确认并写入本地 serverId 后清理本地原图。进程退出前的 SYNCING 在下次启动恢复 QUEUED。未同步样本可在队列页编辑备注。

CaptureSet 通过 clientCaptureSetId 将板端和手机样本关联。同步采样是 best effort，不宣称硬件触发同步；分别保留服务器接收时间和手机采集时间。手机成功、板端失败会明确提示部分成功，不删除已保存证据。

当前真实 Zynq 没有本地结果存储或离线回传协议，offlineSync/localStorage 为 false。断线不能假装补齐丢失帧。Simulator 也不把服务器离线期间不存在的数据制造为真实回传。

持久 Job 表提供 Training、Deployment、ASSET_PROCESSING、DATASET_EXPORT、SYNC 和 CLEANUP 排队，记录 attempts/error/timestamps。首次上传的预览和质量报告同步生成；后续质量重算和大规模导出可以排队。导出采用流式落盘，记录 zip SHA256，原始资产不删除。Cleanup 仅清理已过期的一次性配对令牌。

服务端重启后，对执行状态不确定的 RUNNING job 标 FAILED，要求重新核实，不会自动标 ACTIVE。移动队列绑定采集时的服务器地址；切换服务器不会把旧样本自动发往新的工作空间。

2026-10-16 H5 实测：停止 API 后仍能保存标有 SIMULATED 的测试原图，刷新后队列保留；API 恢复后自动重试成功。六次尝试最终仅有一个服务器 Sample/RAW Asset，原文件与本地夹具 SHA256 和字节一致。
