import {
  Body,
  Controller,
  Get,
  Inject,
  Param,
  Post,
  Req,
  Res,
} from "@nestjs/common";
import type { FastifyReply } from "fastify";
import { Prisma } from "@prisma/client";
import { createHash, randomBytes } from "node:crypto";
import sharp from "sharp";
import { z } from "zod";
import {
  acceptanceSchema,
  postprocessSchema,
  inspectionRegionSchema,
  planPurposeSchema,
  type BatchSnapshot,
} from "@vision/contracts";
import {
  canonical,
  assessInspectionImage,
  evaluateInspection,
} from "@vision/shared";
import { detect, detectObjects, decodeRgb565 } from "@vision/device-protocol";
import { Public, Roles, type Request } from "../core/auth.js";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { parse, DomainError } from "../core/errors.js";
import { AssetsService } from "../assets/assets.service.js";
import { serverAddresses, mobileServerUrl } from "../system/network.js";
import { config } from "../config.js";
import { batchModel } from "./batch-package.js";
import {
  buildAssignmentSnapshot,
  ensureBatchForRecord,
  reconcileProductionBatch,
} from "./terminal-batch.js";

const acceptance = acceptanceSchema;
const runCountsSchema = z
  .object({
    PASS: z.number().int().min(0),
    FAIL: z.number().int().min(0),
    REVIEW: z.number().int().min(0),
    ERROR: z.number().int().min(0),
  })
  .strict();

const recordSchema = z
  .object({
    formatVersion: z.literal(1),
    postprocess: postprocessSchema.optional(),
    planId: z.string().min(1),
    planVersion: z.number().int().min(1),
    planName: z.string().min(1).max(120),
    product: z.string().min(1).max(120),
    modelId: z.string().min(1),
    modelVersion: z.string().min(1).max(128),
    modelPayloadSha256: z.string().regex(/^[a-f0-9]{64}$/),
    acceptance,
    bootId: z.string().uuid(),
    sequence: z.number().int().min(1).max(2147483647),
    frameId: z.number().int().min(0).max(4294967295),
    monotonicNs: z.string().regex(/^\d{1,20}$/),
    capturedAt: z.string().datetime().nullable(),
    raw: z.string().length(461484),
    out0: z.string().length(2156),
    out1: z.string().length(8624),
    rawSha256: z.string().regex(/^[a-f0-9]{64}$/),
    localResult: z.enum(["PASS", "FAIL", "REVIEW", "ERROR"]),
    productionRunId: z.string().uuid().nullable().optional(),
    passage: z
      .object({
        samples: z.number().int().min(1).max(2147483647),
        votes: z.tuple([
          z.number().int().nonnegative(),
          z.number().int().nonnegative(),
          z.number().int().nonnegative(),
          z.number().int().nonnegative(),
        ]),
        interrupted: z.boolean(),
        consensus: z
          .object({
            algorithm: z.literal("COUNT_VECTOR_V1"),
            mode: z.enum(["COUNT_VECTOR", "PERSISTENT_DEFECT"]),
            support: z.number().int().min(1).max(2147483647),
            consecutive: z.number().int().min(1).max(2147483647),
            durationMs: z.number().int().min(0).max(2147483647),
            patterns: z.number().int().min(1).max(8),
            unstable: z.boolean(),
            counts: z
              .array(
                z
                  .object({
                    classId: z.number().int().min(0).max(5),
                    count: z.number().int().min(0).max(300),
                    uncertain: z.number().int().min(0).max(300),
                  })
                  .strict(),
              )
              .max(6),
          })
          .strict()
          .optional(),
      })
      .strict()
      .refine(
        (value) =>
          value.votes.reduce((a, b) => a + b, 0) === value.samples &&
          (!value.consensus ||
            (value.consensus.support <= value.samples &&
              value.consensus.consecutive <= value.consensus.support &&
              value.consensus.patterns <= value.samples)),
        "过件帧数不一致",
      )
      .optional(),
  })
  .strict();

const heartbeatSchema = z
  .object({
    bootId: z.string().uuid(),
    uptime: z.number().finite().nonnegative(),
    model: z
      .object({
        id: z.string().min(1),
        version: z.string().min(1).max(128),
        payloadSha256: z.string().regex(/^[a-f0-9]{64}$/),
        weightsSha256: z.string().regex(/^[a-f0-9]{64}$/),
        classes: z.array(z.string().min(1)).min(1),
      })
      .strict()
      .nullable(),
    product: z
      .object({
        id: z.string().min(1),
        name: z.string().min(1).max(120),
        version: z.number().int().min(1),
        product: z.string().max(120).optional(),
        instructions: z.string().max(2000).optional(),
        purpose: planPurposeSchema.optional(),
        postprocess: postprocessSchema.optional(),
        region: inspectionRegionSchema.optional(),
        checks: z
          .array(
            z
              .object({
                classId: z.number().int().min(0).max(5),
                label: z.string().min(1).max(40),
                min: z.number().int().min(0).max(100),
                max: z.number().int().min(0).max(100),
                region: inspectionRegionSchema.optional(),
              })
              .strict(),
          )
          .max(6)
          .optional(),
        acceptance,
      })
      .strict()
      .nullable(),
    total: z.number().int().min(0).max(2147483647),
    counts: runCountsSchema,
    runTotal: z.number().int().min(0).max(2147483647),
    runCounts: runCountsSchema,
    production: z.boolean(),
    productionRunId: z.string().uuid().nullable(),
    passagePhase: z.enum([
      "STOPPED",
      "CLEARING",
      "WAITING",
      "INSPECTING",
      "SAVING",
    ]),
    fps: z.number().finite().nonnegative().max(1000).nullable().optional(),
    timing: z
      .object({
        frameId: z.number().int().min(0),
        captureMs: z.number().finite().nonnegative(),
        prepareMs: z.number().finite().nonnegative(),
        convMs: z.number().finite().nonnegative(),
        forwardMs: z.number().finite().nonnegative(),
        postMs: z.number().finite().nonnegative(),
        extractMs: z.number().finite().nonnegative(),
      })
      .strict()
      .nullable()
      .optional(),
    paused: z.boolean(),
    fresh: z.boolean(),
    pendingSync: z.number().int().min(0).max(2147483647),
    pendingRequestId: z.string().uuid().nullable(),
    last: z
      .object({
        sequence: z.number().int().min(0),
        result: z.enum(["PASS", "FAIL", "REVIEW", "ERROR"]),
        bootId: z.string().uuid().optional(),
        productionRunId: z.string().uuid().nullable().optional(),
        reason: z.string().max(1000).optional(),
        findings: z
          .array(
            z
              .object({
                classId: z.number().int().min(0).max(5),
                label: z.string().max(40),
                min: z.number().int().nonnegative(),
                max: z.number().int().nonnegative(),
                count: z.number().int().nonnegative(),
                uncertain: z.number().int().nonnegative(),
                result: z.enum(["PASS", "FAIL", "REVIEW", "ERROR"]),
              })
              .strict(),
          )
          .max(6)
          .optional(),
      })
      .strict()
      .nullable(),
    error: z.string().max(1000),
    syncError: z.string().max(1000),
    cpuPercent: z.number().finite().min(0).max(100).nullable(),
    memoryUsed: z.number().finite().nonnegative().max(17179869184),
    memoryTotal: z.number().finite().nonnegative().max(17179869184),
  })
  .strict();

@Controller("api/terminal")
export class TerminalController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(AssetsService) private assets: AssetsService,
    @Inject(Events) private events: Events,
  ) {}

  private async terminalCredential(req: Request) {
    const bearer = req.headers.authorization?.replace(/^Bearer /, "") ?? "";
    if (!/^[a-f0-9]{64}$/.test(bearer))
      throw new DomainError("UNAUTHORIZED", "终端凭据无效", 401);
    const credential = await this.db.deviceToken.findUnique({
      where: { tokenHash: createHash("sha256").update(bearer).digest("hex") },
    });
    if (
      !credential ||
      credential.revokedAt ||
      (credential.expiresAt && credential.expiresAt <= new Date())
    )
      throw new DomainError("UNAUTHORIZED", "终端凭据已失效", 401);
    return credential;
  }

  @Public() @Post("heartbeat") async heartbeat(
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const credential = await this.terminalCredential(req);
    const dto = parse(heartbeatSchema, body);
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: credential.deviceId, type: "ZYNQ" },
    });
    const metadata = device.metadata as Record<string, Prisma.InputJsonValue>;
    const receivedAt = new Date().toISOString();
    const address = (req.ip ?? "").replace(/^::ffff:/, "");
    const state = {
      ...dto,
      receivedAt,
      credentialId: credential.id,
    };
    await this.db.device.update({
      where: { id: device.id },
      data: {
        metadata: {
          ...metadata,
          runtimeProfile: "LINUX_TERMINAL",
          terminal: state as unknown as Prisma.InputJsonValue,
          ...(address ? { terminalAddress: address } : {}),
        },
      },
    });
    await reconcileProductionBatch(this.db, this.events, this.assets, device, {
      ...dto,
      receivedAt,
    });
    {
      const pending = await this.db.deployment.findMany({
        where: {
          deviceId: device.id,
          status: { in: ["DOWNLOADING", "VERIFYING"] },
        },
      });
      for (const deployment of pending) {
        const receipt = deployment.receipt as Prisma.JsonObject;
        if (
          !dto.model ||
          receipt.modelId !== dto.model.id ||
          receipt.modelPayloadSha256 !== dto.model.payloadSha256
        ) {
          // A fresh heartbeat still reporting another model resolves an expired request.
          if (Date.now() - deployment.createdAt.getTime() > 90000) {
            await this.db.deployment.update({
              where: { id: deployment.id },
              data: {
                status: "FAILED",
                error: "下发超时，设备仍运行其他模型；请核对设备后重新下发",
              },
            });
            this.events.emit(
              "deployment.failed",
              deployment.id,
              { status: "FAILED" },
              "BOARD",
            );
          }
          continue;
        }
        await this.db.$transaction([
          this.db.deployment.updateMany({
            where: {
              deviceId: device.id,
              id: { not: deployment.id },
              status: "ACTIVE",
            },
            data: { status: "SUPERSEDED" },
          }),
          this.db.deployment.update({
            where: { id: deployment.id },
            data: {
              status: "ACTIVE",
              progress: 100,
              receipt: {
                ...receipt,
                modelVersion: dto.model.version,
                verified: true,
                loaded: true,
                active: true,
                confirmedAt: receivedAt,
              },
            },
          }),
        ]);
        this.events.emit(
          "deployment.completed",
          deployment.id,
          { status: "ACTIVE" },
          "BOARD",
        );
      }
    }
    this.events.emit(
      "device.status.changed",
      device.id,
      { id: device.id, receivedAt },
      "BOARD",
    );
    return { receivedAt };
  }

  /** 终端凭据下载已批准模型制品；只允许该设备存在对应部署记录。 */
  @Public()
  @Get("model/:modelId")
  async downloadModel(
    @Param("modelId") modelId: string,
    @Req() req: Request,
    @Res() reply: FastifyReply,
  ) {
    const credential = await this.terminalCredential(req);
    const deployment = await this.db.deployment.findFirst({
      where: {
        deviceId: credential.deviceId,
        modelId,
        status: { in: ["DOWNLOADING", "VERIFYING", "ACTIVE", "ROLLBACK"] },
      },
    });
    if (!deployment)
      throw new DomainError("FORBIDDEN", "此模型未下发给当前终端", 403);
    const artifact = await batchModel(this.db, this.assets, modelId);
    return reply
      .type("application/octet-stream")
      .header("Cache-Control", "no-store")
      .header("x-model-version", artifact.model.version)
      .header("x-model-payload-sha256", artifact.payloadSha256)
      .header("x-weights-sha256", artifact.manifest.weights.sha256)
      .send(artifact.weights);
  }

  @Roles("ADMIN", "ENGINEER") @Post(":deviceId/credential") async credential(
    @Param("deviceId") deviceId: string,
    @Body() body: unknown,
  ) {
    const dto = parse(
      z
        .object({
          confirm: z.literal(true),
          server: z
            .string()
            .url()
            .refine(
              (value) =>
                mobileServerUrl(value) && new URL(value).protocol === "http:",
              "请选择板卡可达的局域网 HTTP 服务地址",
            ),
        })
        .strict(),
      body,
    );
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: deviceId, type: "ZYNQ" },
    });
    const token = randomBytes(32).toString("hex"),
      expiresAt = new Date(Date.now() + 30 * 86400000);
    await this.db.$transaction(async (tx) => {
      await tx.device.update({
        where: { id: deviceId },
        data: {
          metadata: {
            ...(device.metadata as Record<string, Prisma.InputJsonValue>),
            runtimeProfile: "LINUX_TERMINAL",
          },
        },
      });
      await tx.deviceToken.updateMany({
        where: { deviceId, revokedAt: null },
        data: { revokedAt: new Date() },
      });
      await tx.deviceToken.create({
        data: {
          deviceId,
          tokenHash: createHash("sha256").update(token).digest("hex"),
          expiresAt,
        },
      });
    });
    return {
      deviceId,
      token,
      expiresAt,
      server: dto.server.replace(/\/$/, ""),
    };
  }

  @Roles("ADMIN", "ENGINEER") @Get("addresses") addresses() {
    return serverAddresses(config.SERVER_PORT);
  }

  @Public() @Post("records") async ingest(
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const credential = await this.terminalCredential(req);
    const dto = parse(recordSchema, body),
      clientId = `terminal:${credential.deviceId}:${dto.bootId}`,
      key = `${clientId}:${dto.sequence}`;
    const fingerprint = createHash("sha256")
      .update(canonical(dto))
      .digest("hex");
    const existing = async () => {
      const sample = await this.db.sample.findUnique({
        where: { idempotencyKey: key },
        include: { inspections: true },
      });
      if (!sample) return null;
      if (
        (sample.metadata as Record<string, unknown>).requestFingerprint !==
        fingerprint
      )
        throw new DomainError(
          "IDEMPOTENCY_CONFLICT",
          "检查编号已经用于不同的证据",
          409,
        );
      return {
        id: key,
        sampleId: sample.id,
        inspectionId: sample.inspections[0]!.id,
        result: sample.inspections[0]!.result,
        rawSha256: dto.rawSha256,
      };
    };
    const previous = await existing();
    if (previous) return previous;
    const matched = await ensureBatchForRecord(
      this.db,
      this.events,
      this.assets,
      credential.deviceId,
      {
        productionRunId: dto.productionRunId ?? undefined,
        planId: dto.planId,
        modelId: dto.modelId,
        modelPayloadSha256: dto.modelPayloadSha256,
        acceptance: dto.acceptance,
        capturedAt: dto.capturedAt,
      },
    );
    const batch = matched?.batch ?? null;
    const snapshot =
      (batch?.snapshot as unknown as BatchSnapshot | undefined) ??
      (await buildAssignmentSnapshot(
        this.db,
        this.assets,
        dto.modelId,
        dto.planId,
        dto.acceptance,
      ));
    if (
      snapshot.modelId !== dto.modelId ||
      snapshot.modelVersion !== dto.modelVersion ||
      snapshot.modelPayloadSha256 !== dto.modelPayloadSha256 ||
      snapshot.planVersion !== dto.planVersion ||
      canonical(snapshot.acceptance) !== canonical(dto.acceptance)
    )
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "记录的方案、模型或验收条件与快照不一致",
        422,
      );
    const decode = (text: string, size: number) => {
      const bytes = Buffer.from(text, "base64");
      if (bytes.length !== size || bytes.toString("base64") !== text)
        throw new DomainError(
          "VALIDATION_ERROR",
          "终端证据长度或编码无效",
          400,
        );
      return bytes;
    };
    const raw = decode(dto.raw, 416 * 416 * 2),
      out0 = decode(dto.out0, 1617),
      out1 = decode(dto.out1, 6468);
    if (createHash("sha256").update(raw).digest("hex") !== dto.rawSha256)
      throw new DomainError("CHECKSUM_ERROR", "终端原图摘要不匹配", 422);
    if (snapshot.rules.postprocess && !dto.postprocess)
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "此方案要求新版后处理参数，请更新终端程序后重试",
        422,
      );
    // 离线记录用它采集时的后处理参数重算；方案后来调整参数不应让
    // 已保存的证据永久卡在同步队列里。
    const policy = postprocessSchema.parse(
      dto.postprocess ?? snapshot.rules.postprocess ?? {},
    );
    const filtered = dto.postprocess ? detectObjects(out0, out1, policy) : null;
    const boxes = (filtered?.boxes ?? detect(out0, out1)).map((box) => ({
      ...box,
      label: snapshot.modelClasses[box.classId]!,
    }));
    const quality = assessInspectionImage(raw),
      decision = evaluateInspection({
        rules: snapshot.rules,
        acceptance: snapshot.acceptance,
        detections: boxes,
        width: 416,
        height: 416,
        quality: quality.status,
      });
    if (filtered?.report.overflow || filtered?.report.invalid) {
      decision.result = "REVIEW";
      decision.reason = "目标过多或候选数据异常，请人工复核";
    }
    // Local data is evidence, not authority. Recompute decisions and flag disagreement or late arrivals.
    const evidenceResult = decision.result;
    const late = matched?.late ?? false;
    if (decision.result !== dto.localResult || late) {
      decision.result = "REVIEW";
      decision.reason = late
        ? "离线记录在批次结束后到达，请核对实际作业时间"
        : "板端与平台判定不一致，请核对原始证据";
    }
    const consensus = dto.passage?.consensus;
    if (!late && consensus) {
      const counts = decision.findings.map(({ classId, count, uncertain }) => ({
        classId,
        count,
        uncertain,
      }));
      const stableDefect =
        consensus.mode === "PERSISTENT_DEFECT" &&
        evidenceResult === "FAIL" &&
        decision.findings.some(
          (finding) => finding.max === 0 && finding.count > 0,
        ) &&
        consensus.consecutive >= 2 &&
        consensus.durationMs >= 60;
      const stableCount =
        consensus.mode === "COUNT_VECTOR" &&
        consensus.support * 5 >= dto.passage!.samples * 3 &&
        consensus.consecutive >= 3 &&
        consensus.durationMs >= 140;
      if (
        canonical(counts) !== canonical(consensus.counts) ||
        consensus.durationMs > 250 * (consensus.consecutive - 1) ||
        consensus.support >
          dto.passage!.votes[
            { PASS: 0, FAIL: 1, REVIEW: 2, ERROR: 3 }[evidenceResult]
          ]! ||
        consensus.unstable ||
        (!stableDefect && !stableCount)
      ) {
        decision.result = "REVIEW";
        decision.reason = "多帧数量不一致或连续证据不足，请人工复核";
      }
    }
    if (
      !late &&
      dto.passage &&
      (dto.passage.interrupted ||
        dto.passage.samples < 3 ||
        (!consensus &&
          Math.max(...dto.passage.votes) * 5 < dto.passage.samples * 3))
    ) {
      decision.result = "REVIEW";
      decision.reason = "过件证据不足或检测中断，请人工复核";
    }
    const preview = await sharp(decodeRgb565(raw), {
      raw: { width: 416, height: 416, channels: 3 },
    })
      .jpeg({ quality: 85 })
      .toBuffer();
    const stored = await Promise.all([
      this.assets.store(
        raw,
        "RAW",
        "BOARD",
        "frame.rgb565",
        "application/octet-stream",
        416,
        416,
      ),
      this.assets.store(
        preview,
        "PREVIEW",
        "BOARD",
        "frame.jpg",
        "image/jpeg",
        416,
        416,
      ),
      this.assets.store(
        out0,
        "TENSOR_OUT0",
        "BOARD",
        "out0.int8",
        "application/octet-stream",
      ),
      this.assets.store(
        out1,
        "TENSOR_OUT1",
        "BOARD",
        "out1.int8",
        "application/octet-stream",
      ),
    ]);
    stored[0]!.format = "RGB565_LE";
    try {
      const sample = await this.db.$transaction(async (tx) => {
        const created = await tx.sample.create({
          data: {
            name: `终端检查 ${dto.sequence}`,
            source: "BOARD",
            clientId,
            localSequence: dto.sequence,
            idempotencyKey: key,
            taskId: batch?.taskId ?? null,
            planId: dto.planId,
            capturedAt: dto.capturedAt ? new Date(dto.capturedAt) : new Date(),
            metadata: {
              uploadedBy: `terminal:${credential.deviceId}`,
              requestFingerprint: fingerprint,
              timestampProvenance: dto.capturedAt
                ? "DEVICE_WALL_CLOCK_UNVERIFIED"
                : "SERVER_RECEIVE_TIME",
              bootId: dto.bootId,
              monotonicNs: dto.monotonicNs,
            },
            assets: { create: stored },
            quality: { create: quality },
          },
        });
        const inspection = await tx.inspection.create({
          data: {
            sampleId: created.id,
            deviceId: credential.deviceId,
            taskId: batch?.taskId ?? null,
            batchId: batch?.id ?? null,
            source: "BOARD",
            modelId: dto.modelId,
            modelVersion: dto.modelVersion,
            planVersion: `${dto.planId}@${dto.planVersion}`,
            frameId: dto.frameId,
            acquisitionId: `${dto.bootId}:${dto.monotonicNs}`,
            startedAt: dto.capturedAt ? new Date(dto.capturedAt) : new Date(),
            completedAt: new Date(),
            result: decision.result,
            reason: decision.reason,
            metadata: {
              decision: decision as unknown as Prisma.InputJsonValue,
              snapshot: snapshot as unknown as Prisma.InputJsonValue,
              bootId: dto.bootId,
              monotonicNs: dto.monotonicNs,
              localResult: dto.localResult,
              ...(filtered
                ? {
                    postprocess:
                      filtered.report as unknown as Prisma.InputJsonValue,
                  }
                : {}),
              manual: !dto.productionRunId,
              ...(dto.productionRunId
                ? { productionRunId: dto.productionRunId }
                : {}),
              ...(dto.passage ? { passage: dto.passage } : {}),
              offline: true,
            },
            detections: { create: boxes },
          },
        });
        return {
          id: key,
          sampleId: created.id,
          inspectionId: inspection.id,
          result: inspection.result,
          rawSha256: dto.rawSha256,
        };
      });
      this.events.emit(
        "device.inspection.completed",
        credential.deviceId,
        sample,
        "BOARD",
        req.id,
      );
      return sample;
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === "P2002"
      ) {
        const saved = await existing();
        if (saved) return saved;
      }
      throw error;
    }
  }
}
