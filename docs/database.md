# SQLite / Prisma

Schema：`apps/server/prisma/schema.prisma`。迁移：`apps/server/prisma/migrations/202610160001_initial/migration.sql`。启用 WAL、foreign_keys 和 5 秒 busy_timeout。

实体包括 User、Device、DeviceToken、Station、InspectionPlan、Task、Workpiece、CaptureSession、CaptureSet、Sample、Asset、QualityReport、AnnotationSet/Annotation、Inspection/Detection、Review、Dataset/DatasetItem、TrainingJob、Benchmark、Model/ModelArtifact、Deployment、SyncJob、Job、Command、DeviceEvent、AuditLog、SystemEvent、PairingToken。迁移 202610160002_sample_review 增加样本独立审核；手机/导入样本不需要伪造 Inspection 才能接受审核。

外键在数据库执行，用户名、设备序列号、资产键、样本 idempotencyKey、clientId/localSequence、数据集 name/version、模型 name/version、标注 sample/version 唯一。设备活跃时间、检测设备/任务/结果/时间、样本来源/时间、队列状态/时间等有索引。

JSON 保存能力、状态、manifest、快照和可选元数据。SQLite enum 由 Prisma 校验，HTTP DTO 另行校验。初始迁移显式将 JSON 默认值写作 `'{}'`，避免当前 Prisma migration diff 的未加引号输出。

标注保存产生新版本；冻结数据集引用确定的 AnnotationSet 并保存 boxes/资产 checksum 快照。后续标注不会改写冻结内容。新一轮迭代 clone 成下一个 dataset version。冻结后不能增删条目。

User 不对 API 暴露 passwordHash。样本删除只设置 deletedAt，原图保留，操作审计。DeviceToken 表预留给未来可鉴权的设备协议；当前 legacy UDP 不虚构设备令牌握手。

备份时应停止服务后复制数据库及 storage，或使用 SQLite 在线备份接口；不要仅复制正在写入的主 db 而忽略 WAL。`data/`、`.env` 和生成文件均忽略入 Git。
