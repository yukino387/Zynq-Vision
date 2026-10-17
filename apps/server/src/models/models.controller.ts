import "@fastify/multipart";
import { createHash } from "node:crypto";
import {
  Controller,
  Get,
  Post,
  Param,
  Body,
  Query,
  Req,
  Res,
  Inject,
} from "@nestjs/common";
import type { FastifyReply } from "fastify";
import { z } from "zod";
import { Prisma } from "@prisma/client";
import { manifestSchema, trainingOptionsSchema } from "@vision/contracts";
import { validateZynqPackage } from "./zynq-profile.js";
import { Db } from "../core/db.js";
import { Roles, type Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { ModelsService } from "./models.service.js";
import { AssetsService } from "../assets/assets.service.js";
@Roles("ADMIN", "ENGINEER")
@Controller("api/models")
export class ModelsController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(ModelsService) private models: ModelsService,
    @Inject(AssetsService) private assets: AssetsService,
  ) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "status",
      "createdAt",
      "updatedAt",
      "source",
    ]);
    return page(
      await this.db.model.findMany({
        ...args,
        include: {
          training: { include: { dataset: true } },
          artifacts: { include: { asset: true } },
          benchmarks: true,
        },
      }),
      await this.db.model.count({ where: args.where }),
      q,
    );
  }
  @Get(":id") detail(@Param("id") id: string) {
    return this.db.model.findUniqueOrThrow({
      where: { id },
      include: {
        training: { include: { dataset: true } },
        artifacts: { include: { asset: true } },
        benchmarks: true,
        deployments: { include: { device: true } },
        _count: { select: { inspections: true } },
      },
    });
  }
  @Post("import") async upload(@Req() req: Request) {
    let content: Buffer | null = null,
      metadata: unknown = null;
    for await (const part of req.parts()) {
      if (part.type === "file") {
        content = await part.toBuffer();
        if (part.file.truncated)
          throw new DomainError(
            "VALIDATION_ERROR",
            "Artifact exceeds 20MB",
            413,
          );
      } else if (part.fieldname === "metadata")
        metadata = JSON.parse(String(part.value));
    }
    if (!content)
      throw new DomainError("VALIDATION_ERROR", "Weights required", 400);
    const dto = parse(
      z
        .object({
          name: z.string().min(1),
          version: z.string().min(1),
          manifest: manifestSchema,
        })
        .strict(),
      metadata,
    );
    if (
      createHash("sha256").update(content).digest("hex") !==
        dto.manifest.weights.sha256 ||
      content.length !== dto.manifest.weights.size
    )
      throw new DomainError(
        "CHECKSUM_ERROR",
        "Manifest checksum mismatch",
        422,
      );
    validateZynqPackage(content, dto.version, dto.manifest);
    const asset = await this.assets.store(
      content,
      "MODEL_ARTIFACT",
      "IMPORT",
      "weights.bin",
      "application/octet-stream",
    );
    return this.db.model.create({
      data: {
        name: dto.name,
        version: dto.version,
        architecture: dto.manifest.networkTemplate,
        manifest: dto.manifest as unknown as Prisma.InputJsonValue,
        source: "IMPORT",
        artifacts: { create: { kind: "WEIGHTS", asset: { create: asset } } },
      },
    });
  }
  @Post(":id/compatibility") async check(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    const { deviceId } = parse(
      z.object({ deviceId: z.string() }).strict(),
      body,
    );
    await this.models.check(id, deviceId);
    return { compatible: true };
  }
  @Roles("ADMIN") @Post(":id/approve") async approve(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          confirm: z.literal(true),
          note: z.string().trim().min(1).max(1000),
        })
        .strict(),
      body,
    );
    await this.models.artifact(id);
    return this.db.$transaction(async (tx) => {
      const model = await tx.model.findUniqueOrThrow({
        where: { id },
        include: { benchmarks: true },
      });
      if (!model.benchmarks.length)
        throw new DomainError(
          "INVALID_STATE",
          "请先完成模型验证，再由管理员记录现场验收意见",
        );
      const metrics = model.metrics as Prisma.JsonObject;
      return tx.model.update({
        where: { id },
        data: {
          status: "APPROVED",
          metrics: {
            ...metrics,
            releaseApproval: {
              actorId: req.actor.id,
              at: new Date().toISOString(),
              note: dto.note,
              benchmarkIds: model.benchmarks.map((b) => b.id),
            },
          },
        },
      });
    });
  }
  @Post(":id/export") async export(
    @Param("id") id: string,
    @Res() reply: FastifyReply,
  ) {
    return reply
      .type("application/zip")
      .header("Content-Disposition", `attachment; filename="model-${id}.zip"`)
      .send(await this.models.export(id));
  }
}
@Roles("ADMIN", "ENGINEER")
@Controller("api/trainings")
export class TrainingsController {
  constructor(@Inject(Db) private db: Db) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query);
    const rows = await this.db.trainingJob.findMany({
      ...args,
      include: { dataset: true, models: true },
    });
    const jobs = await this.db.job.findMany({
      where: { type: "TRAINING", entityId: { in: rows.map((row) => row.id) } },
      select: { entityId: true, payload: true },
    });
    return page(
      rows.map((row) => ({
        ...row,
        options:
          (
            jobs.find((job) => job.entityId === row.id)?.payload as
              Prisma.JsonObject | undefined
          )?.options ?? null,
      })),
      await this.db.trainingJob.count({ where: args.where }),
      q,
    );
  }
  @Post() async create(@Body() body: unknown) {
    const dto = parse(
      z
        .object({
          datasetId: z.string(),
          name: z.string().min(1).max(120),
          options: trainingOptionsSchema.default({}),
        })
        .strict(),
      body,
    );
    return this.db.$transaction(async (tx) => {
      const dataset = await tx.dataset.findUniqueOrThrow({
        where: { id: dto.datasetId },
      });
      if (dataset.status !== "FROZEN")
        throw new DomainError(
          "INVALID_STATE",
          "Training requires frozen dataset",
        );
      const training = await tx.trainingJob.create({
        data: { name: dto.name, datasetId: dto.datasetId, source: "IMPORT" },
      });
      await tx.job.create({
        data: {
          type: "TRAINING",
          entityId: training.id,
          payload: { options: dto.options },
        },
      });
      return training;
    });
  }
  @Post(":id/cancel") async cancel(@Param("id") id: string) {
    const updated = await this.db.trainingJob.updateMany({
      where: { id, status: { in: ["QUEUED", "RUNNING"] } },
      data: { status: "CANCELLED" },
    });
    if (!updated.count)
      throw new DomainError(
        "INVALID_STATE",
        "Training cannot be cancelled in this state",
      );
    await this.db.job.updateMany({
      where: { entityId: id, status: "QUEUED" },
      data: { status: "CANCELLED", completedAt: new Date() },
    });
    return this.db.trainingJob.findUniqueOrThrow({ where: { id } });
  }
}
