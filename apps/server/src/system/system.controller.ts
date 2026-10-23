import {
  Controller,
  Get,
  Post,
  Body,
  Query,
  Req,
  Inject,
  Param,
  Res,
} from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { z } from "zod";
import { randomBytes, createHash } from "node:crypto";
import { serverAddresses, mobileServerUrl } from "./network.js";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { Roles, Public, type Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { AssetsService } from "../assets/assets.service.js";
import { DevicesService } from "../devices/devices.service.js";
import { config } from "../config.js";
import { createReadStream } from "node:fs";
import type { FastifyReply } from "fastify";
@Controller("api")
export class SystemController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(Events) private events: Events,
    @Inject(AssetsService) private assets: AssetsService,
    @Inject(DevicesService) private devices: DevicesService,
  ) {}
  @Public() @Get("health") async health() {
    await this.db.$queryRaw`SELECT 1`;
    return { status: "ok", timestamp: new Date().toISOString() };
  }
  /** 产线总览。屏上约十个计数，逐个用列表 total 探测要发十几次请求，
   *  且其中三项落在操作工过不去的类级 @Roles 后面——所以服务端算好一次给出。
   *  角色打不开的明细一律返回 null 而不是 0，避免泄露一个点进去就 403 的数字。 */
  @Get("overview") async overview(
    @Query() query: unknown,
    @Req() req: Request,
  ) {
    const { from, to, deviceId } = parse(
      z
        .object({
          from: z.string().datetime().optional(),
          to: z.string().datetime().optional(),
          deviceId: z.string().optional(),
        })
        .strict(),
      query,
    );
    // 默认近 24 小时。不用「本班次」是因为班次一翻页整屏就是 0——
    // 而闭环那几项统计的是存量不按时间窗，两类数字并排会看起来互相矛盾。
    const now = new Date(),
      start = from ?? new Date(now.getTime() - 24 * 3600_000).toISOString(),
      end = to ?? now.toISOString();
    const base = {
      createdAt: { gte: new Date(start), lte: new Date(end) },
      ...(deviceId ? { deviceId } : {}),
    };
    const [byResult, samples, snapshots] = await Promise.all([
      this.db.inspection.groupBy({
        by: ["result"],
        _count: { _all: true },
        where: base,
      }),
      this.db.sample.groupBy({
        by: ["status"],
        _count: { _all: true },
        where: { deletedAt: null },
      }),
      this.devices.snapshots(),
    ]);
    const count = (result: string) =>
      byResult.find((r) => r.result === result)?._count._all ?? 0;
    const sampleCount = (status: string) =>
      samples.find((s) => s.status === status)?._count._all ?? 0;
    const engineer = req.actor.role !== "OPERATOR";
    const [reviewSamples, pendingDeployments, capabilities] = engineer
      ? await Promise.all([
          this.db.sample.count({
            where: {
              deletedAt: null,
              status: { in: ["PENDING", "NEEDS_WORK"] },
            },
          }),
          this.db.deployment.count({ where: { status: "APPROVED" } }),
          this.db.device.findMany({ select: { capabilities: true } }),
        ])
      : [0, 0, []];
    /** 数据闭环：采样 → 审核 → 数据集 → 训练 → 模型 → 部署 → 检测。
     *  每一环给出已完成的量与还在等人工的量，界面据此显示卡在哪一步。
     *  操作工看不到其中四环（接口对他是 403），所以整条链对他为 null。 */
    const stages = engineer
      ? await Promise.all([
          this.db.sample.count({ where: { deletedAt: null } }),
          this.db.dataset.groupBy({ by: ["status"], _count: { _all: true } }),
          this.db.trainingJob.groupBy({
            by: ["status"],
            _count: { _all: true },
          }),
          this.db.model.groupBy({ by: ["status"], _count: { _all: true } }),
          this.db.deployment.groupBy({
            by: ["status"],
            _count: { _all: true },
          }),
        ])
      : null;
    const loop = stages
      ? (() => {
          const [sampleTotal, dataset, training, model, deployment] = stages;
          const pick = (
            rows: { status: string; _count: { _all: number } }[],
            keys: string[],
          ) =>
            rows
              .filter((r) => keys.includes(r.status))
              .reduce((s, r) => s + r._count._all, 0);
          return [
            {
              key: "capture",
              label: "采样",
              done: sampleTotal,
              waiting: sampleCount("PENDING"),
              to: "data",
            },
            {
              key: "review",
              label: "审核",
              done: sampleCount("REVIEWED"),
              waiting: reviewSamples,
              to: "data/annotation",
            },
            {
              key: "dataset",
              label: "数据集",
              done: pick(dataset, ["FROZEN"]),
              waiting: pick(dataset, ["DRAFT", "READY"]),
              to: "data/datasets",
            },
            {
              key: "training",
              label: "训练",
              done: pick(training, ["COMPLETED"]),
              waiting: pick(training, ["QUEUED", "RUNNING"]),
              to: "models/training",
            },
            {
              key: "model",
              label: "模型",
              done: pick(model, ["APPROVED"]),
              waiting: pick(model, ["CANDIDATE"]),
              to: "models/registry",
            },
            {
              key: "deployment",
              label: "部署",
              done: pick(deployment, ["ACTIVE"]),
              waiting: pendingDeployments,
              to: "models/deployments",
            },
            {
              key: "inspection",
              label: "检测",
              done: byResult.reduce((s, r) => s + r._count._all, 0),
              waiting: 0,
              to: "records/all",
            },
          ];
        })()
      : null;
    const unsupported = [
      ...new Set(
        capabilities.flatMap((d) =>
          Object.entries((d.capabilities ?? {}) as Record<string, unknown>)
            .filter(([, value]) => value === false)
            .map(([key]) => key),
        ),
      ),
    ].sort();
    const active = snapshots.find((s) => s.telemetry) ?? snapshots[0];
    const readiness = engineer
      ? await Promise.all([
          this.db.sample.count({
            where: { deletedAt: null, source: { not: "SIMULATION" } },
          }),
          this.db.sample.count({
            where: {
              deletedAt: null,
              source: { not: "SIMULATION" },
              annotations: { some: { status: "COMPLETE" } },
            },
          }),
          this.db.sample.count({
            where: { deletedAt: null, source: "SIMULATION" },
          }),
          this.db.dataset.findMany({
            where: { status: "FROZEN" },
            include: {
              items: { select: { sample: { select: { source: true } } } },
            },
          }),
          this.db.model.count({
            where: { source: { not: "SIMULATION" }, status: "CANDIDATE" },
          }),
          this.db.model.count({
            where: { source: { not: "SIMULATION" }, status: "APPROVED" },
          }),
          this.db.deployment.count({
            where: { source: { not: "SIMULATION" }, status: "ACTIVE" },
          }),
        ])
      : null;
    return {
      window: { from: start, to: end },
      inspections: {
        total: byResult.reduce((sum, r) => sum + r._count._all, 0),
        pass: count("PASS"),
        fail: count("FAIL"),
        review: count("REVIEW"),
        error: count("ERROR"),
      },
      samples: {
        pending: sampleCount("PENDING"),
        reviewed: sampleCount("REVIEWED"),
      },
      devices: {
        total: snapshots.length,
        online: snapshots.filter((d) => d.connectionState === "ONLINE").length,
        stale: snapshots.filter((d) => d.connectionState === "STALE").length,
        offline: snapshots.filter((d) => d.connectionState === "OFFLINE")
          .length,
        fault: snapshots.filter((d) => d.runtimeState === "FAULT").length,
      },
      /** 设备内存里的最近一帧遥测；没有过遥测时为 null，界面显示未上报。 */
      through: active?.telemetry ?? null,
      pipeline: engineer ? { reviewSamples, pendingDeployments } : null,
      loop,
      trainingReadiness: readiness
        ? {
            realSamples: readiness[0],
            annotatedReal: readiness[1],
            simulatedSamples: readiness[2],
            readyDatasets: readiness[3]
              .filter(
                (dataset) =>
                  dataset.items.length >= 2 &&
                  dataset.items.every(
                    (item) => item.sample.source !== "SIMULATION",
                  ),
              )
              .map((dataset) => ({
                id: dataset.id,
                name: dataset.name,
                version: dataset.version,
                count: dataset.items.length,
              })),
            candidateModels: readiness[4],
            approvedModels: readiness[5],
            activeDeployments: readiness[6],
          }
        : null,
      /** 设备 capability 里显式为 false 的项——即固件当前不提供的能力。
       *  缺失的项不生成占位数值，界面显示「未上报」。 */
      firmwareGaps: engineer ? { unsupported } : null,
    };
  }
  @Roles("ADMIN", "ENGINEER") @Get("system") async system() {
    const [
      wal,
      size,
      storage,
      pendingJobs,
      errors,
      migrations,
      freeBytes,
      snapshots,
      pageSize,
      exportJobs,
    ] = await Promise.all([
      this.db.$queryRaw<{ journal_mode: string }[]>`PRAGMA journal_mode`,
      this.db.$queryRaw<{ page_count: bigint }[]>`PRAGMA page_count`,
      this.db.asset.groupBy({
        by: ["kind"],
        _sum: { size: true },
        _count: true,
      }),
      this.db.job.count({ where: { status: { in: ["QUEUED", "RUNNING"] } } }),
      this.db.job.findMany({
        where: { status: "FAILED" },
        take: 10,
        orderBy: { createdAt: "desc" },
      }),
      this.db.$queryRaw<
        { migration_name: string }[]
      >`SELECT migration_name FROM _prisma_migrations WHERE finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1`,
      this.assets.freeSpace(),
      this.devices.snapshots(),
      this.db.$queryRaw<{ page_size: bigint }[]>`PRAGMA page_size`,
      this.db.$queryRaw<
        { total: bigint | null }[]
      >`SELECT SUM(CAST(json_extract(payload,'$.output.size') AS INTEGER)) AS total FROM Job WHERE type='DATASET_EXPORT' AND status='COMPLETED'`,
    ]);
    return {
      server: {
        status: "READY",
        uptimeSeconds: Math.floor(process.uptime()),
        version: "0.1.0",
      },
      database: {
        engine: "SQLite",
        journalMode: wal[0]?.journal_mode,
        pages: Number(size[0]?.page_count ?? 0),
        sizeBytes:
          Number(size[0]?.page_count ?? 0) *
          Number(pageSize[0]?.page_size ?? 0),
        latestMigration: migrations[0]?.migration_name,
      },
      storage: {
        status: "READY",
        groups: storage,
        freeBytes,
        exportsBytes: Number(exportJobs[0]?.total ?? 0),
      },
      websocket: { path: config.WS_PATH, clients: this.events.count() },
      pendingJobs,
      errors,
      devices: snapshots.map((d) => ({
        id: d.id,
        source: d.source,
        network: d.connectionState,
        runtime: d.runtimeState,
      })),
      network: serverAddresses(config.SERVER_PORT),
    };
  }
  @Roles("ADMIN", "ENGINEER") @Get("system/jobs") async jobs(
    @Query() query: unknown,
  ) {
    const { q, args } = listing(query, ["createdAt", "status"]);
    return page(
      await this.db.job.findMany(args),
      await this.db.job.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN", "ENGINEER") @Get("system/jobs/:id/content") async jobContent(
    @Param("id") id: string,
    @Res() reply: FastifyReply,
  ) {
    const job = await this.db.job.findUniqueOrThrow({ where: { id } });
    const output = (
      job.payload as { output?: { storageKey?: string; sha256?: string } }
    ).output;
    if (
      job.status !== "COMPLETED" ||
      job.type !== "DATASET_EXPORT" ||
      !output?.storageKey?.startsWith("exports/")
    )
      throw new DomainError("INVALID_STATE", "Export is not ready");
    reply.header(
      "Content-Disposition",
      `attachment; filename="export-${id}.zip"`,
    );
    if (output.sha256) reply.header("X-SHA256", output.sha256);
    return reply
      .type("application/zip")
      .send(createReadStream(this.assets.path(output.storageKey)));
  }
  @Roles("ADMIN") @Post("system/cleanup") cleanup() {
    return this.db.job.create({
      data: {
        type: "CLEANUP",
        entityId: "expired-pairing-tokens",
        payload: {},
      },
    });
  }
  @Post("system/sync-jobs") async syncJob(
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          clientId: z.string().max(120),
          sampleKeys: z.array(z.string()).max(100),
        })
        .strict(),
      body,
    );
    return this.db.$transaction(async (tx) => {
      const sync = await tx.syncJob.create({
        data: { clientId: dto.clientId, payload: dto },
      });
      return tx.job.create({
        data: {
          type: "SYNC",
          entityId: sync.id,
          payload: { ...dto, userId: req.actor.id },
        },
      });
    });
  }
  @Get("events") async eventList(@Query() query: unknown) {
    const { q, args } = listing(query, ["createdAt", "deviceId", "source"]);
    return page(
      await this.db.deviceEvent.findMany(args),
      await this.db.deviceEvent.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN") @Get("audit") async audit(@Query() query: unknown) {
    const { q, args } = listing(query, ["createdAt"]);
    return page(
      await this.db.auditLog.findMany({
        ...args,
        include: { user: { select: { name: true, role: true } } },
      }),
      await this.db.auditLog.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN", "ENGINEER") @Post("system/pairing") async pairing(
    @Body() body: unknown,
  ) {
    const dto = parse(
      z
        .object({
          stationId: z.string().optional(),
          serverUrl: z
            .string()
            .trim()
            .url()
            .refine(
              mobileServerUrl,
              "请使用手机可访问的电脑 WLAN 地址，不能使用 localhost、回环地址或带路径的地址",
            ),
        })
        .strict(),
      body,
    );
    if (dto.stationId)
      await this.db.station.findUniqueOrThrow({ where: { id: dto.stationId } });
    const token = randomBytes(32).toString("base64url"),
      expiry = new Date(Date.now() + 5 * 60 * 1000);
    await this.db.pairingToken.create({
      data: {
        hash: createHash("sha256").update(token).digest("hex"),
        expiresAt: expiry,
        stationId: dto.stationId,
      },
    });
    return {
      serverUrl: new URL(dto.serverUrl).origin,
      stationId: dto.stationId,
      pairingToken: token,
      expiry: expiry.toISOString(),
      protocolVersion: 1,
    };
  }
  @Public() @Post("system/pairing/redeem") async redeem(@Body() body: unknown) {
    const { token } = parse(
      z.object({ token: z.string().min(20).max(100) }).strict(),
      body,
    );
    return this.db.$transaction(async (tx) => {
      const pairing = await tx.pairingToken.findUnique({
        where: { hash: createHash("sha256").update(token).digest("hex") },
      });
      if (!pairing || pairing.usedAt || pairing.expiresAt < new Date())
        throw new DomainError(
          "INVALID_PAIRING_TOKEN",
          "Expired or already used pairing token",
          400,
        );
      await tx.pairingToken.update({
        where: { id: pairing.id },
        data: { usedAt: new Date() },
      });
      return {
        stationId: pairing.stationId,
        protocolVersion: 1,
        authenticationRequired: true,
      };
    });
  }
  @Post("system/sync") async sync(@Body() body: unknown, @Req() req: Request) {
    const dto = parse(
      z
        .object({
          clientId: z.string().max(120),
          sampleKeys: z.array(z.string()).max(100),
        })
        .strict(),
      body,
    );
    const samples = await this.db.sample.findMany({
      where: { clientId: dto.clientId, idempotencyKey: { in: dto.sampleKeys } },
      select: { id: true, idempotencyKey: true, metadata: true },
    });
    const accepted = samples
      .filter(
        (s) =>
          (s.metadata as Record<string, unknown>).uploadedBy === req.actor.id,
      )
      .map((s) => ({ id: s.id, idempotencyKey: s.idempotencyKey }));
    await this.db.syncJob.create({
      data: {
        clientId: dto.clientId,
        status: "COMPLETED",
        attempts: 1,
        startedAt: new Date(),
        completedAt: new Date(),
        payload: {
          received: dto.sampleKeys.length,
          accepted: accepted as Prisma.InputJsonValue,
        },
      },
    });
    return { accepted };
  }
}
