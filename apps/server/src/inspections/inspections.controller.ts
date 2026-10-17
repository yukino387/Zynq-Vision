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
import type { Request } from "../core/auth.js";
import { parse } from "../core/errors.js";
import { listing, page } from "../core/list.js";
@Controller("api/inspections")
export class InspectionsController {
  constructor(@Inject(Db) private db: Db) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "createdAt",
      "deviceId",
      "taskId",
      "stationId",
      "result",
      "source",
      "status",
    ]);
    if (q.reviewed)
      args.where.reviews = q.reviewed === "false" ? { none: {} } : { some: {} };
    return page(
      await this.db.inspection.findMany({
        ...args,
        include: {
          detections: true,
          sample: { include: { assets: true } },
          reviews: true,
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
        reviews: { include: { user: { select: { name: true } } } },
      },
    });
  }
}
@Controller("api/reviews")
export class ReviewsController {
  constructor(@Inject(Db) private db: Db) {}
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
        })
        .strict(),
      body,
    );
    return this.db.$transaction(async (tx) => {
      const inspection = await tx.inspection.findUniqueOrThrow({
        where: { id: dto.inspectionId },
      });
      const review = await tx.review.create({
        data: { ...dto, sampleId: inspection.sampleId, userId: req.actor.id },
      });
      await tx.sample.update({
        where: { id: inspection.sampleId },
        data: { ...(dto.hard ? { hard: true } : {}) },
      });
      return review;
    });
  }
}
