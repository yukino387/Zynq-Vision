import { Injectable, Inject } from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { z } from "zod";
import sharp from "sharp";
import { createHash } from "node:crypto";
import type { Source } from "@vision/contracts";
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
  async capture(dto: CaptureDto, actor: string, requestId: string) {
    return this.idempotent(
      dto.idempotencyKey,
      actor,
      createHash("sha256").update(JSON.stringify(dto)).digest("hex"),
      () =>
        this.commands.run(dto.deviceId, "CAPTURE", requestId, async () => {
          const frame = await this.devices
            .transport(dto.deviceId)
            .captureOnce();
          const device = await this.db.device.findUniqueOrThrow({
            where: { id: dto.deviceId },
          });
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
          const quality = await this.assets.quality(frame.preview);
          const sample = await this.db.$transaction(async (tx) => {
            const set = await tx.captureSet.upsert({
              where: { clientId: dto.captureSetClientId ?? dto.idempotencyKey },
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
            await this.inspection(
              tx,
              created.id,
              device,
              frame,
              source,
              dto.taskId,
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
            "device.inspection.completed",
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
    const result =
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
    return tx.inspection.create({
      data: {
        sampleId,
        deviceId: device.id,
        stationId: device.stationId,
        taskId,
        modelId: model?.id,
        modelVersion,
        planVersion: frame.modelState.planVersion ?? null,
        firmwareVersion: device.firmwareVersion,
        frameId: frame.frameId,
        source,
        startedAt: new Date(frame.receivedAt),
        completedAt: new Date(),
        latency: frame.telemetry?.inferenceUs
          ? frame.telemetry.inferenceUs / 1000
          : null,
        result,
        reason:
          source !== "SIMULATION"
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
          telemetry: frame.telemetry as unknown as Prisma.InputJsonValue,
          rule:
            source === "SIMULATION"
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
