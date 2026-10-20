import { isLinuxTerminal } from "../devices/terminal-state.js";
import { terminalRequest } from "../devices/terminal-client.js";
import { decodeRgb565 } from "@vision/device-protocol";
import { Injectable, Inject } from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { z } from "zod";
import sharp from "sharp";
import { createHash } from "node:crypto";
import type { Source, BatchSnapshot } from "@vision/contracts";
import { evaluateInspection, assessInspectionImage } from "@vision/shared";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { DomainError } from "../core/errors.js";
import { AssetsService } from "../assets/assets.service.js";
import { modelInput } from "../assets/preprocess.js";
import { DevicesService } from "../devices/devices.service.js";
import { CommandsService } from "../devices/commands.service.js";
import type { CapturedFrame } from "../devices/transport.js";
export const captureSchema = z
  .object({
    deviceId: z.string(),
    taskId: z.string().optional(),
    planId: z.string().optional(),
    batchId: z.string().optional(),
    idempotencyKey: z.string().min(8).max(160),
    clientId: z.string().min(1).max(120),
    localSequence: z.number().int().min(0).max(2147483647),
    captureSetClientId: z.string().optional(),
  })
  .strict();
export const uploadSchema = z
  .object({
    source: z.enum(["MOBILE", "IMPORT"]),
    taskId: z.string().optional(),
    planId: z.string().optional(),
    idempotencyKey: z.string().min(8).max(160),
    clientId: z.string().min(1).max(120),
    localSequence: z.number().int().min(0).max(2147483647),
    capturedAt: z.string().datetime(),
    captureSetClientId: z.string().optional(),
    metadata: z.record(z.unknown()).default({}),
  })
  .strict();
export type CaptureDto = z.infer<typeof captureSchema>;
@Injectable()
export class SamplesService {
  private locks = new Map<string, Promise<unknown>>();
  constructor(
    @Inject(Db) private db: Db,
    @Inject(AssetsService) private assets: AssetsService,
    @Inject(DevicesService) private devices: DevicesService,
    @Inject(CommandsService) private commands: CommandsService,
    @Inject(Events) private events: Events,
  ) {}
  private async idempotent<T>(
    key: string,
    actor: string,
    fingerprint: string,
    action: () => Promise<T>,
  ) {
    const previous = this.locks.get(key) ?? Promise.resolve();
    const next = previous
      .catch(() => undefined)
      .then(async () => {
        const existing = await this.db.sample.findUnique({
          where: { idempotencyKey: key },
          include: {
            assets: true,
            inspections: { include: { detections: true } },
          },
        });
        if (existing) {
          if (
            (existing.metadata as Record<string, unknown>).uploadedBy !== actor
          )
            throw new DomainError(
              "CONSTRAINT_VIOLATION",
              "Idempotency key belongs to another actor",
              409,
            );
          if (
            (existing.metadata as Record<string, unknown>)
              .requestFingerprint !== fingerprint
          )
            throw new DomainError(
              "IDEMPOTENCY_CONFLICT",
              "Key was already used for a different request",
              409,
            );
          return existing;
        }
        return action();
      });
    this.locks.set(key, next);
    try {
      return await next;
    } finally {
      if (this.locks.get(key) === next) this.locks.delete(key);
    }
  }
  private async productPlan(
    dto: { planId?: string; taskId?: string },
    db: Prisma.TransactionClient,
  ) {
    const task = dto.taskId
      ? await db.task.findUniqueOrThrow({ where: { id: dto.taskId } })
      : null;
    const planId = dto.planId ?? task?.planId;
    if (dto.planId && task?.planId && dto.planId !== task.planId)
      throw new DomainError("INVALID_STATE", "产品与采样任务不匹配");
    if (planId)
      await db.inspectionPlan.findUniqueOrThrow({
        where: { id: planId, deletedAt: null },
      });
    return planId;
  }
  private async requireOpenTask(
    taskId: string | undefined,
    db: Prisma.TransactionClient = this.db,
  ) {
    if (!taskId) return;
    const task = await db.task.findUniqueOrThrow({
      where: { id: taskId, status: { not: "DELETED" } },
    });
    if (task.status !== "OPEN")
      throw new DomainError(
        "INVALID_STATE",
        "采样任务已完成，请重新开放任务或选择其他任务",
      );
  }
  async capture(
    dto: CaptureDto,
    actor: string,
    requestId: string,
    authorization = "",
  ) {
    return this.idempotent(
      dto.idempotencyKey,
      actor,
      createHash("sha256").update(JSON.stringify(dto)).digest("hex"),
      () =>
        this.commands.run(dto.deviceId, "CAPTURE", requestId, async () => {
          await this.requireOpenTask(dto.taskId);
          if (dto.batchId) {
            const batch = await this.db.inspectionBatch.findUniqueOrThrow({
              where: { id: dto.batchId },
            });
            if (
              batch.status !== "OPEN" ||
              batch.deviceId !== dto.deviceId ||
              batch.taskId !== dto.taskId
            )
              throw new DomainError(
                "INVALID_STATE",
                "批次已结束或设备、任务不匹配",
                409,
              );
          }
          const device = await this.db.device.findUniqueOrThrow({
            where: { id: dto.deviceId },
          });
          let frame: CapturedFrame;
          let terminalPlanId: string | undefined;
          if (isLinuxTerminal(device)) {
            const response = await terminalRequest(
              device,
              "/capture",
              authorization,
            );
            const binary = Buffer.from(await response.arrayBuffer());
            if (binary.length < 4)
              throw new DomainError("INVALID_FRAME", "设备画面不完整", 502);
            const length = binary.readUInt32LE(0);
            if (length > 65536 || binary.length !== 4 + length + 416 * 416 * 2)
              throw new DomainError("INVALID_FRAME", "设备画面格式错误", 502);
            const metadata = JSON.parse(
              binary.subarray(4, 4 + length).toString(),
            );
            terminalPlanId = metadata.planId ?? undefined;
            if (!metadata.fresh)
              throw new DomainError(
                "DEVICE_TIMEOUT",
                "当前画面已过期，请开始检测后再采样",
                409,
              );
            const raw = binary.subarray(4 + length);
            frame = {
              frameId: metadata.frameId,
              receivedAt: new Date().toISOString(),
              raw,
              width: 416,
              height: 416,
              format: "RGB565_LE",
              preview: await sharp(decodeRgb565(raw), {
                raw: { width: 416, height: 416, channels: 3 },
              })
                .jpeg()
                .toBuffer(),
              detections: metadata.boxes.map((box: { classId: number }) => ({
                ...box,
                label:
                  metadata.modelClasses?.[box.classId] ??
                  `类别 ${box.classId + 1}`,
              })),
              telemetry: null,
              modelState: {
                modelVersion: metadata.modelVersion ?? null,
                modelPayloadSha256: metadata.modelPayloadSha256 ?? null,
              },
            };
          } else
            frame = await this.devices.transport(dto.deviceId).captureOnce();
          const source: Source =
            device.type === "SIMULATOR" ? "SIMULATION" : "BOARD";
          const stored = await this.assets.store(
            frame.raw,
            "RAW",
            source,
            `frame-${frame.frameId}.rgb565`,
            "application/octet-stream",
            416,
            416,
          );
          stored.format = frame.format;
          const preview = await this.assets.store(
            frame.preview,
            "PREVIEW",
            source,
            `frame-${frame.frameId}.jpg`,
            "image/jpeg",
            416,
            416,
          );
          const input = modelInput(frame.raw),
            inputAsset = await this.assets.store(
              input,
              "MODEL_INPUT",
              source,
              "reconstructed-input.int8",
              "application/octet-stream",
              224,
              224,
            );
          inputAsset.format = "INT8_CHW";
          const inputPng = await sharp(
            Buffer.from(input.map((v) => Math.round((v * 255) / 127))),
            { raw: { width: 224, height: 224, channels: 1 } },
          )
            .png()
            .toBuffer();
          const inputPreview = await this.assets.store(
            inputPng,
            "MODEL_INPUT_PREVIEW",
            source,
            "reconstructed-input.png",
            "image/png",
            224,
            224,
          );
          const tensors = frame.outputs
            ? await Promise.all([
                this.assets.store(
                  frame.outputs.out0,
                  "TENSOR_OUT0",
                  source,
                  "out0.int8",
                  "application/octet-stream",
                ),
                this.assets.store(
                  frame.outputs.out1,
                  "TENSOR_OUT1",
                  source,
                  "out1.int8",
                  "application/octet-stream",
                ),
              ])
            : [];
          const quality = dto.batchId
            ? assessInspectionImage(frame.raw)
            : await this.assets.quality(frame.preview);
          const sample = await this.db.$transaction(async (tx) => {
            await this.requireOpenTask(dto.taskId, tx);
            const set = await tx.captureSet.upsert({
              where: {
                clientId: dto.captureSetClientId ?? dto.idempotencyKey,
              },
              create: {
                clientId: dto.captureSetClientId ?? dto.idempotencyKey,
                session: { create: { taskId: dto.taskId, source } },
                metadata: {
                  timing: "best effort; independent acquisition timestamps",
                },
              },
              update: {},
            });
            const created = await tx.sample.create({
              data: {
                name: `${source === "SIMULATION" ? "SIMULATED " : " "}Frame ${frame.frameId}`,
                source,
                clientId: dto.clientId,
                localSequence: dto.localSequence,
                idempotencyKey: dto.idempotencyKey,
                taskId: dto.taskId,
                planId: await this.productPlan(
                  {
                    ...dto,
                    planId:
                      dto.planId ?? (dto.taskId ? undefined : terminalPlanId),
                  },
                  tx,
                ),
                captureSetId: set?.id,
                capturedAt: new Date(frame.receivedAt),
                metadata: {
                  uploadedBy: actor,
                  requestFingerprint: createHash("sha256")
                    .update(JSON.stringify(dto))
                    .digest("hex"),
                  deviceId: device.id,
                  frameId: frame.frameId,
                  timestampProvenance: "SERVER_RECEIVE_TIME",
                  modelInputProvenance:
                    "SERVER_RECONSTRUCTION_FROM_RGB565; device does not transmit input",
                },
                assets: {
                  create: [
                    stored,
                    preview,
                    inputAsset,
                    inputPreview,
                    ...tensors,
                  ],
                },
                quality: { create: quality },
              },
            });
            // A retained image is training evidence, not an additional inspected item.
            if (!isLinuxTerminal(device))
              await this.inspection(
                tx,
                created.id,
                device,
                frame,
                source,
                dto.taskId,
                dto.batchId,
                quality.status,
              );
            return tx.sample.findUniqueOrThrow({
              where: { id: created.id },
              include: {
                assets: true,
                inspections: { include: { detections: true } },
              },
            });
          });
          this.events.emit(
            "sample.created",
            device.id,
            sample,
            source,
            requestId,
          );
          return sample;
        }),
    );
  }
  private async inspection(
    tx: Prisma.TransactionClient,
    sampleId: string,
    device: {
      id: string;
      stationId: string | null;
      firmwareVersion: string | null;
    },
    frame: CapturedFrame,
    source: Source,
    taskId?: string,
    batchId?: string,
    qualityStatus = "WARNING",
  ) {
    const modelVersion = frame.modelState.modelVersion ?? null;
    const model = modelVersion
      ? await tx.model.findFirst({
          where: {
            version: modelVersion,
            source: source === "SIMULATION" ? "SIMULATION" : "IMPORT",
          },
        })
      : null;
    const classes = (model?.manifest as { classes?: string[] } | undefined)
      ?.classes;
    const boxes =
      frame.detections?.map((box) => ({
        ...box,
        label:
          classes?.[box.classId] ??
          (source === "SIMULATION" ? box.label : `类别 ${box.classId + 1}`),
      })) ?? null;
    const confidence = boxes?.length
      ? Math.max(...boxes.map((b) => b.confidence))
      : null;
    let result: "PASS" | "FAIL" | "REVIEW" | "ERROR" =
      source !== "SIMULATION"
        ? "REVIEW"
        : !boxes
          ? "REVIEW"
          : boxes.length === 0
            ? source === "SIMULATION"
              ? "PASS"
              : "REVIEW"
            : confidence! >= 0.7
              ? "FAIL"
              : "REVIEW";
    let decision: ReturnType<typeof evaluateInspection> | null = null;
    let snapshot: BatchSnapshot | null = null;
    if (batchId) {
      const batch = await tx.inspectionBatch.findUniqueOrThrow({
        where: { id: batchId },
      });
      if (
        batch.status !== "OPEN" ||
        batch.deviceId !== device.id ||
        batch.taskId !== taskId
      )
        throw new DomainError(
          "INVALID_STATE",
          "批次已结束或设备、任务不匹配",
          409,
        );
      snapshot = batch.snapshot as unknown as BatchSnapshot;
      const changed =
        frame.modelState.modelVersion !== snapshot.modelVersion ||
        (snapshot.modelPayloadSha256 !== null &&
          frame.modelState.modelPayloadSha256 !== snapshot.modelPayloadSha256);
      if (changed)
        throw new DomainError(
          "MODEL_INCOMPATIBLE",
          "设备模型已改变，请结束当前批次并重新建批",
          422,
        );
      const age = Date.now() - Date.parse(frame.receivedAt);
      if (!Number.isFinite(age) || age < -1000 || age > 5000)
        throw new DomainError(
          "DEVICE_TIMEOUT",
          "本次图像已过期，请重新检查",
          409,
        );
      // The fixed model and plan snapshot, rather than mutable model labels, governs this batch.
      decision = evaluateInspection({
        rules: snapshot.rules,
        acceptance: snapshot.acceptance,
        detections: boxes,
        width: frame.width,
        height: frame.height,
        quality: qualityStatus,
        errorCode: frame.telemetry?.errorCode,
      });
      result = decision.result;
    }
    return tx.inspection.create({
      data: {
        sampleId,
        deviceId: device.id,
        stationId: device.stationId,
        taskId,
        batchId,
        acquisitionId: batchId ? `host:${frame.frameId}` : null,
        modelId: model?.id,
        modelVersion,
        planVersion: snapshot
          ? `${snapshot.planId}@${snapshot.planVersion}`
          : (frame.modelState.planVersion ?? null),
        firmwareVersion: device.firmwareVersion,
        frameId: frame.frameId,
        source,
        startedAt: new Date(frame.receivedAt),
        completedAt: new Date(),
        latency: frame.telemetry?.inferenceUs
          ? frame.telemetry.inferenceUs / 1000
          : null,
        result,
        reason: decision
          ? decision.reason
          : source !== "SIMULATION"
            ? "当前为对象候选输出，尚未应用经过验证的方案规则，请人工复核"
            : !boxes
              ? "Inference tensors unavailable"
              : boxes.length
                ? "Defect candidate; host postprocess"
                : source === "SIMULATION"
                  ? "SIMULATED acceptance plan: no defect candidates"
                  : "No defect candidates; acceptance plan not reported",
        confidence,
        metadata: {
          ...(decision
            ? {
                decision: decision as unknown as Prisma.InputJsonValue,
                snapshot: snapshot as unknown as Prisma.InputJsonValue,
              }
            : {}),
          telemetry: frame.telemetry as unknown as Prisma.InputJsonValue,
          rule: decision
            ? "ACCEPTANCE_V1"
            : source === "SIMULATION"
              ? "SIMULATOR_FIXTURE_ONLY"
              : "CANDIDATES_ONLY; acceptance plan not applied",
        },
        detections: boxes ? { create: boxes } : undefined,
      },
    });
  }
  async upload(
    dto: z.infer<typeof uploadSchema>,
    file: Buffer,
    name: string,
    mime: string,
    actor: string,
  ) {
    await this.requireOpenTask(dto.taskId);
    return this.idempotent(
      dto.idempotencyKey,
      actor,
      createHash("sha256")
        .update(JSON.stringify(dto))
        .update(file)
        .digest("hex"),
      async () => {
        const preview = await this.assets.preview(file);
        const meta = await sharp(preview).metadata();
        const originalMeta = await sharp(file).metadata();
        const mimeTypes: Record<string, string> = {
          jpeg: "image/jpeg",
          png: "image/png",
          webp: "image/webp",
          avif: "image/avif",
          gif: "image/gif",
          svg: "image/svg+xml",
          tiff: "image/tiff",
        };
        const raw = await this.assets.store(
          file,
          "RAW",
          dto.source,
          name,
          mimeTypes[originalMeta.format ?? ""] ?? "application/octet-stream",
          originalMeta.width,
          originalMeta.height,
        );
        raw.format = originalMeta.format ?? mime;
        const derived = await this.assets.store(
          preview,
          "PREVIEW",
          dto.source,
          "preview.jpg",
          "image/jpeg",
          meta.width,
          meta.height,
        );
        const quality = await this.assets.quality(preview);
        return this.db.$transaction(async (tx) => {
          await this.requireOpenTask(dto.taskId, tx);
          const set = await tx.captureSet.upsert({
            where: { clientId: dto.captureSetClientId ?? dto.idempotencyKey },
            create: {
              clientId: dto.captureSetClientId ?? dto.idempotencyKey,
              session: { create: { taskId: dto.taskId, source: dto.source } },
            },
            update: {},
          });
          return tx.sample.create({
            data: {
              name,
              source: dto.source,
              taskId: dto.taskId,
              planId: await this.productPlan(dto, tx),
              clientId: dto.clientId,
              localSequence: dto.localSequence,
              idempotencyKey: dto.idempotencyKey,
              captureSetId: set?.id,
              capturedAt: new Date(dto.capturedAt),
              metadata: JSON.parse(
                JSON.stringify({
                  ...dto.metadata,
                  uploadedBy: actor,
                  requestFingerprint: createHash("sha256")
                    .update(JSON.stringify(dto))
                    .update(file)
                    .digest("hex"),
                }),
              ) as Prisma.InputJsonValue,
              assets: { create: [raw, derived] },
              quality: { create: quality },
            },
            include: { assets: true },
          });
        });
      },
    );
  }
}
