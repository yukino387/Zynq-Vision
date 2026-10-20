import {
  Controller,
  Get,
  Post,
  Param,
  Body,
  Query,
  Req,
  Inject,
} from "@nestjs/common";
import { z } from "zod";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import type { Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
@Controller("api/inspections")
export class InspectionsController {
  constructor(@Inject(Db) private db: Db) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "createdAt",
      "deviceId",
      "taskId",
      "batchId",
      "stationId",
      "result",
      "source",
      "status",
    ]);
    if (q.reviewed) {
      if (q.reviewed === "true")
        args.where.OR = [{ reviewResult: { in: ["PASS", "FAIL"] } }];
      else
        args.where.AND = [
          {
            OR: [{ reviewResult: null }, { reviewResult: "REVIEW" }],
          },
        ];
    }
    if (q.result === "REVIEW" && q.reviewed === "false") {
      delete args.where.result;
      args.where.AND = [
        {
          OR: [
            { result: { in: ["REVIEW", "ERROR"] }, reviewResult: null },
            { reviewResult: "REVIEW" },
          ],
        },
      ];
    }
    if (q.realOnly === "true") args.where.NOT = { source: "SIMULATION" };
    return page(
      await this.db.inspection.findMany({
        ...args,
        include: {
          detections: true,
          sample: { include: { assets: true } },
          reviews: { orderBy: [{ createdAt: "desc" }, { id: "desc" }] },
        },
      }),
      await this.db.inspection.count({ where: args.where }),
      q,
    );
  }
  @Get(":id") detail(@Param("id") id: string) {
    return this.db.inspection.findUniqueOrThrow({
      where: { id },
      include: {
        sample: { include: { assets: true, quality: true } },
        device: true,
        model: {
          include: {
            training: { include: { dataset: true } },
            artifacts: true,
          },
        },
        detections: true,
        reviews: {
          orderBy: [{ createdAt: "desc" }, { id: "desc" }],
          include: { user: { select: { name: true } } },
        },
      },
    });
  }
}
@Controller("api/reviews")
export class ReviewsController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(Events) private events: Events,
  ) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, ["createdAt"]);
    return page(
      await this.db.review.findMany({ ...args, include: { inspection: true } }),
      await this.db.review.count({ where: args.where }),
      q,
    );
  }
  @Post() async create(@Body() body: unknown, @Req() req: Request) {
    const dto = parse(
      z
        .object({
          inspectionId: z.string(),
          verdict: z.enum([
            "CORRECT",
            "FALSE_POSITIVE",
            "MISSED",
            "LOW_CONFIDENCE",
            "LIGHTING",
            "OCCLUSION",
            "OTHER",
          ]),
          note: z.string().max(2000).default(""),
          hard: z.boolean().default(false),
          finalResult: z.enum(["PASS", "FAIL", "REVIEW"]).optional(),
        })
        .strict(),
      body,
    );
    const review = await this.db.$transaction(async (tx) => {
      const inspection = await tx.inspection.findUniqueOrThrow({
        where: { id: dto.inspectionId },
      });
      if (dto.finalResult === "REVIEW" && !dto.note.trim())
        throw new DomainError(
          "VALIDATION_ERROR",
          "保持待复核时请填写原因",
          400,
        );
      const review = await tx.review.create({
        data: { ...dto, sampleId: inspection.sampleId, userId: req.actor.id },
      });
      if (dto.finalResult)
        await tx.inspection.update({
          where: { id: inspection.id },
          data: { reviewResult: dto.finalResult },
        });
      await tx.sample.update({
        where: { id: inspection.sampleId },
        data: { ...(dto.hard ? { hard: true } : {}) },
      });
      return review;
    });
    this.events.emit(
      "inspection.reviewed",
      dto.inspectionId,
      { id: review.id, finalResult: review.finalResult },
      "SERVER",
      req.id,
    );
    return review;
  }
}
