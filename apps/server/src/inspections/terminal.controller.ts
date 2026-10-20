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
import { type BatchSnapshot } from "@vision/contracts";
import {
  canonical,
  assessInspectionImage,
  evaluateInspection,
} from "@vision/shared";
import { detect, decodeRgb565 } from "@vision/device-protocol";
import { Public, Roles, type Request } from "../core/auth.js";
import { terminalStatus } from "../devices/terminal-state.js";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { parse, DomainError } from "../core/errors.js";
import { AssetsService } from "../assets/assets.service.js";
import { serverAddresses, mobileServerUrl } from "../system/network.js";
import { config } from "../config.js";

const recordSchema = z
  .object({
    formatVersion: z.literal(1),
    batchId: z.string().min(1),
    bootId: z.string().uuid(),
    sequence: z.number().int().min(1).max(2147483647),
    frameId: z.number().int().min(0).max(4294967295),
    monotonicNs: z.string().regex(/^\d{1,20}$/),
    capturedAt: z.string().datetime().nullable(),
    modelPayloadSha256: z.string().regex(/^[a-f0-9]{64}$/),
    raw: z.string().length(461484),
    out0: z.string().length(2156),
    out1: z.string().length(8624),
    rawSha256: z.string().regex(/^[a-f0-9]{64}$/),
    localResult: z.enum(["PASS", "FAIL", "REVIEW", "ERROR"]),
  })
  .strict();

const heartbeatSchema = z
  .object({
    bootId: z.string().uuid(),
    uptime: z.number().finite().nonnegative(),
    jobId: z.string().min(1).max(80).nullable(),
    paused: z.boolean(),
    fresh: z.boolean(),
    modelVersion: z.string().max(128).nullable(),
    total: z.number().int().min(0).max(2147483647),
    pendingSync: z.number().int().min(0).max(2147483647),
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
    const batch = dto.jobId
      ? await this.db.inspectionBatch.findUniqueOrThrow({
          where: { id: dto.jobId },
        })
      : null;
    if (
      batch &&
      (batch.deviceId !== device.id || batch.execution !== "TERMINAL")
    )
      throw new DomainError("FORBIDDEN", "当前作业不属于此终端", 403);
    const metadata = device.metadata as Record<string, Prisma.InputJsonValue>;
    const receivedAt = new Date().toISOString();
    const address = (req.ip ?? "").replace(/^::ffff:/, "");
    const state = {
      ...dto,
      jobName: batch?.name ?? null,
      batchStatus: batch?.status ?? null,
      receivedAt,
      credentialId: credential.id,
    };
    await this.db.device.update({
      where: { id: device.id },
      data: {
        metadata: {
          ...metadata,
          runtimeProfile: "LINUX_TERMINAL",
          terminal: state,
          ...(address ? { terminalAddress: address } : {}),
        },
      },
    });
    return {
      receivedAt,
      jobId: batch?.id ?? null,
      batchStatus: batch?.status ?? null,
    };
  }

  @Get(":deviceId/status") async terminalStatus(
    @Param("deviceId") deviceId: string,
  ) {
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: deviceId, type: "ZYNQ" },
    });
    return terminalStatus(this.db, device);
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

  @Get(":deviceId/frame")
  async frame(
    @Param("deviceId") deviceId: string,
    @Res({ passthrough: true }) reply: FastifyReply,
  ): Promise<Buffer> {
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: deviceId, type: "ZYNQ" },
    });
    const metadata = device.metadata as Record<string, unknown>;
    const host =
      typeof metadata.terminalAddress === "string" && metadata.terminalAddress
        ? metadata.terminalAddress
        : config.ZYNQ_HOST;
    let response: Response;
    try {
      response = await fetch(`http://${host}:8879/frame`, {
        signal: AbortSignal.timeout(1500),
      });
    } catch {
      throw new DomainError("UNAVAILABLE", "板端预览不可达", 503);
    }
    if (!response.ok) {
      if (response.status === 409)
        throw new DomainError(
          "NO_FRAME",
          "板端尚未启用检测作业或暂无画面",
          409,
        );
      throw new DomainError("UNAVAILABLE", "板端预览不可达", 503);
    }
    const raw = Buffer.from(await response.arrayBuffer());
    const pixels = 416 * 416 * 2;
    const frame =
      raw.length === pixels
        ? raw
        : raw.length >= 4 && 4 + raw.readUInt32LE(0) + pixels === raw.length
          ? raw.subarray(4 + raw.readUInt32LE(0))
          : null;
    if (!frame)
      throw new DomainError("INVALID_FRAME", "板端画面格式异常", 502);
    const jpeg = await sharp(decodeRgb565(frame), {
      raw: { width: 416, height: 416, channels: 3 },
    })
      .jpeg({ quality: 80 })
      .toBuffer();
    reply.type("image/jpeg").header("Cache-Control", "no-store");
    return jpeg;
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
    const batch = await this.db.inspectionBatch.findUniqueOrThrow({
      where: { id: dto.batchId },
    });
    if (batch.deviceId !== credential.deviceId)
      throw new DomainError("FORBIDDEN", "终端不能提交其他设备的记录", 403);
    if (batch.execution !== "TERMINAL")
      throw new DomainError(
        "INVALID_STATE",
        "此批次由平台采集执行，不能接收板端离线记件",
        409,
      );
    const snapshot = batch.snapshot as unknown as BatchSnapshot;
    if (snapshot.modelPayloadSha256 !== dto.modelPayloadSha256)
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "离线记录的模型与批次不一致",
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
    const boxes = detect(out0, out1).map((box) => ({
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
    // Local data is evidence, not authority. Recompute decisions and flag disagreement or late arrivals.
    if (decision.result !== dto.localResult || batch.status === "CLOSED") {
      decision.result = "REVIEW";
      decision.reason =
        batch.status === "CLOSED"
          ? "离线记录在批次结束后到达，请核对实际作业时间"
          : "板端与平台判定不一致，请核对原始证据";
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
    try {
      const sample = await this.db.$transaction(async (tx) => {
        const created = await tx.sample.create({
          data: {
            name: `终端检查 ${dto.sequence}`,
            source: "BOARD",
            clientId,
            localSequence: dto.sequence,
            idempotencyKey: key,
            taskId: batch.taskId,
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
            taskId: batch.taskId,
            batchId: batch.id,
            source: "BOARD",
            modelId: snapshot.modelId,
            modelVersion: snapshot.modelVersion,
            planVersion: `${snapshot.planId}@${snapshot.planVersion}`,
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
