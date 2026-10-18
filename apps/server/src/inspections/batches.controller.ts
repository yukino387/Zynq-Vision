import {
  Body,
  Controller,
  Get,
  Inject,
  Param,
  Post,
  Query,
  Req,
  Res,
} from "@nestjs/common";
import archiver from "archiver";
import { PassThrough } from "node:stream";
import type { FastifyReply } from "fastify";
import { Prisma } from "@prisma/client";
import { z } from "zod";
import {
  acceptanceSchema,
  planRulesSchema,
  type BatchSnapshot,
  type BatchSummary,
  type InspectionResult,
} from "@vision/contracts";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { Roles, type Request } from "../core/auth.js";
import { DomainError, parse } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { DevicesService } from "../devices/devices.service.js";
import { SamplesService, captureSchema } from "../samples/samples.service.js";
import { AssetsService } from "../assets/assets.service.js";
import { batchModel } from "./batch-package.js";

@Controller("api/batches")
export class BatchesController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(DevicesService) private devices: DevicesService,
    @Inject(SamplesService) private samples: SamplesService,
    @Inject(Events) private events: Events,
    @Inject(AssetsService) private assets: AssetsService,
  ) {}

  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "createdAt",
      "status",
      "deviceId",
      "taskId",
    ]);
    return page(
      await this.db.inspectionBatch.findMany({
        ...args,
        include: { _count: { select: { inspections: true } } },
      }),
      await this.db.inspectionBatch.count({ where: args.where }),
      q,
    );
  }

  @Roles("ADMIN", "ENGINEER") @Post() async create(
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          name: z.string().trim().min(1).max(120),
          deviceId: z.string().min(1),
          taskId: z.string().min(1),
          target: z.number().int().min(1).max(10000000),
          acceptance: acceptanceSchema,
          execution: z.enum(["HOST", "TERMINAL"]).default("HOST"),
          modelId: z.string().optional(),
        })
        .strict(),
      body,
    );
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: dto.deviceId },
    });
    const task = await this.db.task.findUniqueOrThrow({
      where: { id: dto.taskId, status: "OPEN" },
      include: { plan: true },
    });
    if (!task.plan || task.plan.deletedAt)
      throw new DomainError("INVALID_STATE", "请为任务选择有效的检查方案");
    if (task.stationId && task.stationId !== device.stationId)
      throw new DomainError("INVALID_STATE", "检测设备不属于任务指定的工位");
    const rules = parse(planRulesSchema, task.plan.rules);
    if (rules.checks.length !== rules.classes.length)
      throw new DomainError(
        "VALIDATION_ERROR",
        "每个类别都需要配置数量要求",
        400,
      );
    const state =
      dto.execution === "HOST"
        ? this.devices.transport(dto.deviceId).getCurrentConfig()
        : {};
    if (dto.execution === "HOST" && !state.modelVersion)
      throw new DomainError("INVALID_STATE", "请先连接设备并确认当前模型版本");
    const models = await this.db.model.findMany({
      where: {
        ...(dto.execution === "HOST"
          ? { version: state.modelVersion ?? "" }
          : { id: dto.modelId ?? "" }),
        source: device.type === "SIMULATOR" ? "SIMULATION" : "IMPORT",
      },
    });
    if (models.length !== 1 || models[0]!.status !== "APPROVED")
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "当前设备模型需要在平台中唯一登记并批准后才能用于作业",
        422,
      );
    const model = models[0]!,
      classes = (model.manifest as { classes?: string[] }).classes;
    if (!classes || rules.classes.some((label, i) => classes[i] !== label))
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "方案类别及顺序必须与设备模型一致",
        422,
      );
    if (
      dto.execution === "HOST" &&
      device.type !== "SIMULATOR" &&
      !/^[a-f0-9]{64}$/.test(state.modelPayloadSha256 ?? "")
    )
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "设备尚未确认模型内容摘要",
        422,
      );
    const snapshot: BatchSnapshot = {
      formatVersion: 1,
      planId: task.plan.id,
      planName: task.plan.name,
      planVersion: task.plan.version,
      rules,
      acceptance: dto.acceptance,
      modelId: model.id,
      modelVersion: model.version,
      modelClasses: classes,
      modelPayloadSha256: state.modelPayloadSha256 ?? null,
    };
    if (device.type !== "SIMULATOR") {
      const artifact = await batchModel(this.db, this.assets, model.id);
      if (
        dto.execution === "HOST" &&
        artifact.payloadSha256 !== snapshot.modelPayloadSha256
      )
        throw new DomainError(
          "MODEL_INCOMPATIBLE",
          "设备模型内容与平台批准制品不一致",
          422,
        );
      snapshot.modelPayloadSha256 = artifact.payloadSha256;
    }
    if (dto.execution === "TERMINAL" && device.type !== "ZYNQ")
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "独立终端批次需要真实设备与模型",
        422,
      );
    try {
      const batch = await this.db.inspectionBatch.create({
        data: {
          name: dto.name,
          deviceId: dto.deviceId,
          taskId: dto.taskId,
          target: dto.target,
          execution: dto.execution,
          snapshot: snapshot as unknown as Prisma.InputJsonValue,
          createdBy: req.actor.id,
        },
      });
      this.events.emit("batch.opened", batch.id, batch, "SERVER", req.id);
      return batch;
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === "P2002"
      )
        throw new DomainError(
          "INVALID_STATE",
          "此设备已有进行中的作业批次，请继续或结束原批次",
          409,
        );
      throw error;
    }
  }

  @Get(":id") detail(@Param("id") id: string) {
    return this.db.inspectionBatch.findUniqueOrThrow({
      where: { id },
      include: { _count: { select: { inspections: true } } },
    });
  }

  @Roles("ADMIN", "ENGINEER") @Get(":id/package") async package(
    @Param("id") id: string,
    @Res() reply: FastifyReply,
  ) {
    const batch = await this.db.inspectionBatch.findUniqueOrThrow({
      where: { id, status: "OPEN", execution: "TERMINAL" },
    });
    const snapshot = batch.snapshot as unknown as BatchSnapshot;
    const artifact = await batchModel(this.db, this.assets, snapshot.modelId);
    if (artifact.payloadSha256 !== snapshot.modelPayloadSha256)
      throw new DomainError("CHECKSUM_ERROR", "批次模型摘要已改变", 422);
    const zip = archiver("zip"),
      stream = new PassThrough();
    zip.on("error", (error) => stream.destroy(error));
    zip.pipe(stream);
    zip.append(
      JSON.stringify(
        {
          formatVersion: 1,
          id: batch.id,
          name: batch.name,
          deviceId: batch.deviceId,
          taskId: batch.taskId,
          target: batch.target,
          snapshot,
          modelSha256: artifact.manifest.weights.sha256,
          manifest: artifact.manifest,
        },
        null,
        2,
      ),
      { name: "job.json" },
    );
    zip.append(artifact.weights, { name: "model.bin" });
    void zip.finalize();
    return reply
      .type("application/zip")
      .header(
        "Content-Disposition",
        `attachment; filename="vision-job-${id}.zip"`,
      )
      .send(stream);
  }

  @Get(":id/summary") async summary(
    @Param("id") id: string,
  ): Promise<BatchSummary> {
    await this.db.inspectionBatch.findUniqueOrThrow({ where: { id } });
    const rows = await this.db.inspection.groupBy({
      by: ["result", "reviewResult"],
      where: { batchId: id },
      _count: { _all: true },
    });
    const machine = { PASS: 0, FAIL: 0, REVIEW: 0, ERROR: 0 },
      final = { ...machine };
    let resolved = 0,
      total = 0;
    for (const row of rows) {
      const count = row._count._all;
      total += count;
      machine[row.result] += count;
      const review = row.reviewResult;
      if (review === "PASS" || review === "FAIL") resolved += count;
      final[(review ?? row.result) as InspectionResult] += count;
    }
    const decided = final.PASS + final.FAIL;
    return {
      total,
      machine,
      final,
      resolved,
      pending: final.REVIEW + final.ERROR,
      passRate: decided ? final.PASS / decided : null,
    };
  }

  @Post(":id/check") async check(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      captureSchema.omit({ deviceId: true, taskId: true, batchId: true }),
      body,
    );
    const batch = await this.db.inspectionBatch.findUniqueOrThrow({
      where: { id },
    });
    return this.samples.capture(
      { ...dto, deviceId: batch.deviceId, taskId: batch.taskId, batchId: id },
      req.actor.id,
      req.id,
    );
  }

  @Roles("ADMIN", "ENGINEER") @Post(":id/close") async close(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    parse(z.object({ confirm: z.literal(true) }).strict(), body);
    await this.db.inspectionBatch.updateMany({
      where: { id, status: "OPEN" },
      data: { status: "CLOSED", closedAt: new Date() },
    });
    const batch = await this.db.inspectionBatch.findUniqueOrThrow({
      where: { id },
    });
    this.events.emit("batch.closed", id, batch, "SERVER", req.id);
    return batch;
  }
}
