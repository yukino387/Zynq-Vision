# REST API

基址 `/api`。除 `GET /health`、`POST /auth/login` 和一次性 `POST /system/pairing/redeem` 外需要 `Authorization: Bearer <JWT>`。JWT 有 issuer/audience/8 小时有效期。服务端每次 REST 请求重新检查用户和角色。

角色：ADMIN 管用户/审计；ADMIN/ENGINEER 管设备控制、标注、数据集、训练、Benchmark、模型和部署；三个角色均可读设备、任务、采样、检测和 Review。前端隐藏操作不能替代服务端 403。

列表统一 `page=1&pageSize=30&sort=createdAt&order=desc`，pageSize 最大 100。支持名称/ID search，时间范围 from/to（ISO），以及实体适用的 status/source/deviceId/taskId/stationId/result；不适用字段不作为数据库过滤。排序字段按实体白名单验证。

| 资源           | 主要操作                                                                                                                         |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| auth           | POST login `{username,password}`；GET me                                                                                         |
| users          | GET/POST；PATCH :id `{role?,disabled?}`，仅 ADMIN                                                                                |
| stations       | GET/POST `{name,code}`                                                                                                           |
| tasks          | GET/POST `{name,target,stationId?,planId?}`；GET :id                                                                             |
| workpieces     | GET/POST `{name,serialNumber}`                                                                                                   |
| devices        | GET/POST `{name,serialNumber,type,stationId?}`；GET snapshot/policy/:id；POST :id/connect/disconnect/commands；PATCH :id/desired |
| samples        | GET/:id；POST capture；POST upload；POST :id/annotations；DELETE :id `{confirm:true}`                                            |
| assets         | GET 列表；GET :id/content（鉴权二进制）                                                                                          |
| inspections    | GET 列表/:id（图像、detections、reviews、模型追踪）                                                                              |
| reviews        | GET/POST `{inspectionId,verdict,note,hard}`                                                                                      |
| datasets       | GET/POST `{name,version}`；GET :id；POST :id/items `{sampleIds}`、freeze、clone、export                                          |
| trainings      | GET/POST `{name,datasetId}`；POST :id/cancel（SIMULATED）                                                                        |
| models         | GET/:id；POST import（multipart）、:id/compatibility `{deviceId}`、:id/export                                                    |
| benchmarks     | GET/POST `{name,modelId,datasetId,deviceId}`（SIMULATED）                                                                        |
| deployments    | GET/POST `{modelId,deviceId}`；POST :id/rollback                                                                                 |
| events / audit | GET，审计限 ADMIN                                                                                                                |
| system         | GET health details；GET system/jobs；POST system/pairing / pairing/redeem / sync                                                 |

capture DTO：`{deviceId,taskId?,clientId,localSequence,idempotencyKey,captureSetClientId?}`。本地序号为非负 32 位整数，幂等键至少 8 字符。重复请求返回已有样本，唯一约束覆盖并发。

upload 使用 multipart `metadata` JSON + `file`。metadata：`{source:MOBILE|IMPORT,taskId?,clientId,localSequence,idempotencyKey,capturedAt,metadata?,captureSetClientId?}`。单文件上限 20MB，必须能被实际图像解码。手机上传不自动送进 Zynq。

标注 `{status:DRAFT|COMPLETE,boxes:[{classId,label,confidence,x1,y1,x2,y2}]}`，采用原图预览像素坐标；框不能超出图像。完整标注后可加入数据集。

错误格式 `{code,message,requestId,details}`，响应另带 `X-Request-Id`。包括 VALIDATION_ERROR、UNAUTHORIZED、FORBIDDEN、NO_CAPABILITY、DEVICE_TIMEOUT、FRAME_UNAVAILABLE、MODEL_INCOMPATIBLE、CHECKSUM_ERROR、INVALID_STATE。JSON / REST 断线不会被当成硬件 FAULT。

队列接口：`POST /samples/:id/process`、`POST /datasets/:id/export-jobs`、`POST /system/sync-jobs {clientId,sampleKeys}`、`POST /system/cleanup`（ADMIN）。返回持久 Job；通过 `/system/jobs` 查看，完成的 DATASET_EXPORT 用 `GET /system/jobs/:id/content` 下载，响应包含实际 `X-SHA256`。Web 数据集导出使用异步队列。

独立样本审核：`POST /samples/:id/review {verdict:ACCEPT|REJECT|NEEDS_WORK,note,hard}`；不制造推理记录。命令取消：`POST /devices/:id/commands/:commandId/cancel`，仅接受尚未原子认领的 QUEUED 命令。

## GET /overview

产线总览屏的聚合读数。三个角色均可调用。可选 `from`/`to`（ISO）与 `deviceId`；不传时服务端默认取当前 8 小时班次。全部计数用一次 `groupBy` 得出，不做持久化也不缓存。

```json
{
  "window": { "from": "…", "to": "…" },
  "inspections": { "total": 9, "pass": 1, "fail": 3, "review": 5, "error": 0 },
  "samples": { "pending": 9, "reviewed": 0 },
  "devices": { "total": 2, "online": 1, "stale": 0, "offline": 1, "fault": 0 },
  "through": { "fps": 15.97, "inferenceUs": 55800, "cycleUs": 62600, "frameId": 12345, "errorCode": 0 },
  "pipeline": { "pendingReview": 5, "reviewSamples": 9, "pendingDeployments": 0 },
  "firmwareGaps": { "unsupported": ["modelUpdate", "localStorage"] }
}
```

`pipeline` 与 `firmwareGaps` **对 OPERATOR 返回 `null` 而不是 0**：这两块的数据源在 `models`/`datasets`/`deployments` 的类级 `@Roles` 后面，操作工点进去就是 403，不能先在总览上泄露一个他打不开的计数。界面据此不渲染这两块。

`through` 读设备内存里的最近一帧遥测（未持久化）。设备从未上报过遥测时为 `null`，界面显示「未上报」。`firmwareGaps.unsupported` 是设备 capability 中显式为 `false` 的项，即固件当前不提供的能力；不提供的能力不生成占位数值。
