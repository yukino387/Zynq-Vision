import "@fastify/multipart";
import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  Body,
  Query,
  Req,
  Res,
  Inject,
} from "@nestjs/common";
import { z } from "zod";
import { Prisma } from "@prisma/client";
import { boxSchema } from "@vision/contracts";
import type { FastifyReply } from "fastify";
import { Db } from "../core/db.js";
import { Roles, type Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { AssetsService } from "../assets/assets.service.js";
import {
  SamplesService,
  captureSchema,
  uploadSchema,
} from "./samples.service.js";
@Controller("api/samples")
export class SamplesController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(SamplesService) private samples: SamplesService,
  ) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "status",
      "source",
      "taskId",
      "planId",
      "createdAt",
      "updatedAt",
    ]);
    args.where.deletedAt = null;
    if (q.realOnly === "true") args.where.NOT = { source: "SIMULATION" };
    if (q.annotation === "pending") args.where.status = { not: "REJECTED" };
    if (q.annotation) {
      const completed = await this.db.$queryRaw<
        Array<{ sampleId: string }>
      >(Prisma.sql`
        SELECT a.sampleId FROM AnnotationSet a
        WHERE a.status = 'COMPLETE' AND NOT EXISTS (
          SELECT 1 FROM AnnotationSet newer
          WHERE newer.sampleId = a.sampleId AND newer.version > a.version
        )
      `);
      const ids = completed.map((row) => row.sampleId);
      args.where.id =
        q.annotation === "complete" ? { in: ids } : { notIn: ids };
    }
    if (q.reviewed === "false")
      args.where.AND = [{ status: { in: ["PENDING", "NEEDS_WORK"] } }];
    if (q.reviewed === "true") args.where.AND = [{ status: "REVIEWED" }];
    if (q.qualityStatus) args.where.quality = { status: q.qualityStatus };
    return page(
      await this.db.sample.findMany({
        ...args,
        include: {
          assets: true,
          quality: true,
          reviews: { orderBy: { createdAt: "desc" } },
          _count: {
            select: { annotations: { where: { status: "COMPLETE" } } },
          },
          annotations: {
            orderBy: { version: "desc" },
            take: 1,
            include: { boxes: true },
          },
        },
      }),
      await this.db.sample.count({ where: args.where }),
      q,
    );
  }
  @Post("capture") capture(@Body() body: unknown, @Req() req: Request) {
    return this.samples.capture(
      parse(captureSchema, body),
      req.actor.id,
      req.id,
      req.headers.authorization ?? "",
    );
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/process") async process(
    @Param("id") id: string,
  ) {
    await this.db.sample.findUniqueOrThrow({ where: { id, deletedAt: null } });
    return this.db.job.create({
      data: {
        type: "ASSET_PROCESSING",
        entityId: id,
        payload: { sampleId: id },
      },
    });
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/review") async review(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          verdict: z.enum(["ACCEPT", "REJECT", "NEEDS_WORK"]),
          note: z.string().max(2000).default(""),
          hard: z.boolean().default(false),
        })
        .strict(),
      body,
    );
    return this.db.$transaction(async (tx) => {
      await tx.sample.findUniqueOrThrow({ where: { id, deletedAt: null } });
      const review = await tx.review.create({
        data: { sampleId: id, userId: req.actor.id, ...dto },
      });
      await tx.sample.update({
        where: { id },
        data: {
          status:
            dto.verdict === "REJECT"
              ? "REJECTED"
              : dto.verdict === "ACCEPT"
                ? "REVIEWED"
                : "NEEDS_WORK",
          hard: dto.hard,
        },
      });
      return review;
    });
  }
  @Post("upload") async upload(@Req() req: Request) {
    const parts = req.parts();
    let file: Buffer | null = null,
      name = "",
      mime = "";
    let metadata: unknown = null;
    for await (const part of parts) {
      if (part.type === "file") {
        if (file)
          throw new DomainError(
            "VALIDATION_ERROR",
            "Only one image allowed",
            400,
          );
        file = await part.toBuffer();
        if (part.file.truncated)
          throw new DomainError("VALIDATION_ERROR", "Image exceeds 20MB", 413);
        name = part.filename;
        mime = part.mimetype;
      } else if (part.fieldname === "metadata")
        metadata = JSON.parse(String(part.value));
    }
    if (!file) throw new DomainError("VALIDATION_ERROR", "Image required", 400);
    return this.samples.upload(
      parse(uploadSchema, metadata),
      file,
      name,
      mime,
      req.actor.id,
    );
  }
  @Get("export") async exportFrames(
    @Query("ids") ids: string,
    @Res() reply: FastifyReply,
  ) {
    const list = [
      ...new Set(
        String(ids ?? "")
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
      ),
    ];
    if (!list.length || list.length > 200)
      throw new DomainError("INVALID_STATE", "请选择 1–200 张图片导出", 422);
    const stream = await this.samples.frameExport(list);
    return reply
      .header(
        "Content-Disposition",
        `attachment; filename="frames-${Date.now()}.zip"`,
      )
      .type("application/zip")
      .send(stream);
  }
  @Get(":id") detail(@Param("id") id: string) {
    return this.db.sample.findUniqueOrThrow({
      where: { id, deletedAt: null },
      include: {
        task: { include: { plan: true } },
        plan: true,
        assets: true,
        quality: true,
        reviews: { orderBy: { createdAt: "desc" } },
        annotations: { include: { boxes: true }, orderBy: { version: "desc" } },
        inspections: { include: { detections: true, reviews: true } },
        captureSet: { include: { samples: true } },
      },
    });
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/annotations") async annotate(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          boxes: z.array(boxSchema).max(500),
          status: z.enum(["DRAFT", "COMPLETE"]),
        })
        .strict(),
      body,
    );
    const asset = await this.db.asset.findFirstOrThrow({
      where: { sampleId: id, kind: "PREVIEW" },
    });
    const sample = await this.db.sample.findUniqueOrThrow({
      where: { id, deletedAt: null },
      include: { plan: true },
    });
    const classes = (sample.plan?.rules as { classes?: string[] } | undefined)
      ?.classes;
    if (!classes?.length)
      throw new DomainError("INVALID_STATE", "请先为图片选择产品");
    if (classes?.length) {
      if (dto.boxes.some((box) => !classes[box.classId]))
        throw new DomainError(
          "VALIDATION_ERROR",
          "标注类别不属于当前采样方案",
          400,
        );
      dto.boxes = dto.boxes.map((box) => ({
        ...box,
        label: classes[box.classId]!,
      }));
    }
    if (
      dto.boxes.some(
        (b) => b.x2 > (asset.width ?? 0) || b.y2 > (asset.height ?? 0),
      )
    )
      throw new DomainError(
        "VALIDATION_ERROR",
        "Box exceeds image bounds",
        400,
      );
    return this.db.$transaction(async (tx) => {
      const last = await tx.annotationSet.findFirst({
        where: { sampleId: id },
        orderBy: { version: "desc" },
      });
      await tx.sample.update({
        where: { id },
        data: { status: dto.status === "COMPLETE" ? "REVIEWED" : "PENDING" },
      });
      if (dto.status === "COMPLETE")
        await tx.review.create({
          data: {
            sampleId: id,
            userId: req.actor.id,
            verdict: "ACCEPT",
            hard: sample.hard,
            note: "标注完成并确认可用于训练",
          },
        });
      return tx.annotationSet.create({
        data: {
          sampleId: id,
          userId: req.actor.id,
          version: (last?.version ?? 0) + 1,
          status: dto.status,
          boxes: { create: dto.boxes },
        },
        include: { boxes: true },
      });
    });
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/product") async assignProduct(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    const { planId } = parse(
      z.object({ planId: z.string().min(1) }).strict(),
      body,
    );
    return this.db.$transaction(async (tx) => {
      await tx.inspectionPlan.findUniqueOrThrow({
        where: { id: planId, deletedAt: null },
      });
      const sample = await tx.sample.findUniqueOrThrow({
        where: { id, deletedAt: null },
        include: { _count: { select: { annotations: true } } },
      });
      if (sample._count.annotations && sample.planId !== planId)
        throw new DomainError(
          "INVALID_STATE",
          "已有标注的图片不能更换产品类别",
        );
      return tx.sample.update({
        where: { id },
        data: { planId, taskId: null },
      });
    });
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/task") async assignTask(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    const { taskId } = parse(
      z.object({ taskId: z.string().min(1) }).strict(),
      body,
    );
    return this.db.$transaction(async (tx) => {
      const task = await tx.task.findUniqueOrThrow({
        where: { id: taskId, status: { not: "DELETED" } },
        include: { plan: true },
      });
      const classes = (task.plan?.rules as { classes?: string[] } | undefined)
        ?.classes;
      if (!classes?.length)
        throw new DomainError(
          "INVALID_STATE",
          "请选择已关联检查方案的采样任务",
        );
      const sample = await tx.sample.findUniqueOrThrow({
        where: { id, deletedAt: null },
        include: { task: true, _count: { select: { annotations: true } } },
      });
      if (sample._count.annotations && sample.planId !== task.planId)
        throw new DomainError(
          "INVALID_STATE",
          "此图片已有标注，不能更换到不同检查方案",
        );
      return tx.sample.update({
        where: { id },
        data: { taskId, planId: task.planId },
      });
    });
  }
  @Roles("ADMIN") @Delete(":id") async remove(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    parse(z.object({ confirm: z.literal(true) }).strict(), body);
    return this.db.sample.update({
      where: { id },
      data: { deletedAt: new Date() },
    });
  }
}
@Controller("api/assets")
export class AssetsController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(AssetsService) private assets: AssetsService,
  ) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, ["createdAt", "source"]);
    args.where.deletedAt = null;
    if (q.reviewed === "false")
      args.where.AND = [{ status: { in: ["PENDING", "NEEDS_WORK"] } }];
    if (q.reviewed === "true") args.where.AND = [{ status: "REVIEWED" }];
    return page(
      await this.db.asset.findMany(args),
      await this.db.asset.count({ where: args.where }),
      q,
    );
  }
  @Get(":id/content") async content(
    @Param("id") id: string,
    @Res() reply: FastifyReply,
  ) {
    const asset = await this.db.asset.findUniqueOrThrow({
      where: { id, deletedAt: null },
    });
    reply.header("Cache-Control", "private, max-age=3600");
    reply.header("X-Content-Type-Options", "nosniff");
    return reply
      .type(asset.mimeType)
      .send(await this.assets.read(asset.storageKey));
  }
}
