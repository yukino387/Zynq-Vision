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
  @Get("stats") async stats(@Query() query: unknown) {
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
    const end = new Date(to ?? Date.now()),
      start = new Date(from ?? end.getTime() - 24 * 3600_000);
    if (start.getTime() >= end.getTime())
      throw new DomainError("VALIDATION_ERROR", "时间范围无效", 400);
    const where = {
      createdAt: { gte: start, lte: end },
      ...(deviceId ? { deviceId } : {}),
    };
    const span = end.getTime() - start.getTime(),
      bucket: "hour" | "day" = span <= 48 * 3600_000 ? "hour" : "day",
      bucketMs = bucket === "hour" ? 3600_000 : 24 * 3600_000;
    const origin = new Date(start);
    if (bucket === "hour") origin.setMinutes(0, 0, 0);
    else origin.setHours(0, 0, 0, 0);
    const bucketCount =
      Math.floor((end.getTime() - origin.getTime()) / bucketMs) + 1;
    const series = Array.from({ length: bucketCount }, (_, index) => ({
      at: new Date(origin.getTime() + index * bucketMs).toISOString(),
      total: 0,
      pass: 0,
      fail: 0,
      review: 0,
      error: 0,
      passRate: null as number | null,
    }));
    const rows = await this.db.inspection.findMany({
      where,
      orderBy: { createdAt: "asc" },
      select: {
        createdAt: true,
        result: true,
        reviewResult: true,
        latency: true,
      },
    });
    const totals = {
      total: 0,
      pass: 0,
      fail: 0,
      review: 0,
      error: 0,
      decided: 0,
      latencySum: 0,
      latencyCount: 0,
    };
    for (const row of rows) {
      const final =
        row.reviewResult === "PASS" || row.reviewResult === "FAIL"
          ? row.reviewResult
          : row.result;
      totals.total++;
      if (final === "PASS") {
        totals.pass++;
        totals.decided++;
      } else if (final === "FAIL") {
        totals.fail++;
        totals.decided++;
      } else if (final === "REVIEW") totals.review++;
      else if (final === "ERROR") totals.error++;
      if (row.latency != null) {
        totals.latencySum += row.latency;
        totals.latencyCount++;
      }
      const index = Math.floor(
        (row.createdAt.getTime() - origin.getTime()) / bucketMs,
      );
      const point = series[index];
      if (!point) continue;
      point.total++;
      if (final === "PASS") point.pass++;
      else if (final === "FAIL") point.fail++;
      else if (final === "REVIEW") point.review++;
      else if (final === "ERROR") point.error++;
    }
    for (const point of series) {
      const decided = point.pass + point.fail;
      point.passRate = decided ? point.pass / decided : null;
    }
    const classRows = await this.db.detection.groupBy({
      by: ["label"],
      where: {
        inspection: {
          createdAt: { gte: start, lte: end },
          ...(deviceId ? { deviceId } : {}),
        },
      },
      _count: { _all: true },
    });
    const classes = classRows
      .map((row) => ({ label: row.label, count: row._count._all }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
    const batchRows = await this.db.inspectionBatch.findMany({
      where: {
        createdAt: { gte: start, lte: end },
        ...(deviceId ? { deviceId } : {}),
      },
      orderBy: { createdAt: "desc" },
      take: 8,
      include: { _count: { select: { inspections: true } } },
    });
    const batchIds = batchRows.map((batch) => batch.id);
    const batchCounts = batchIds.length
      ? await this.db.inspection.groupBy({
          by: ["batchId", "result", "reviewResult"],
          where: { batchId: { in: batchIds } },
          _count: { _all: true },
        })
      : [];
    const batchTotals = new Map<
      string,
      { total: number; pass: number; fail: number }
    >();
    for (const row of batchCounts) {
      if (!row.batchId) continue;
      const entry = batchTotals.get(row.batchId) ?? {
        total: 0,
        pass: 0,
        fail: 0,
      };
      entry.total += row._count._all;
      const final =
        row.reviewResult === "PASS" || row.reviewResult === "FAIL"
          ? row.reviewResult
          : row.result;
      if (final === "PASS") entry.pass += row._count._all;
      else if (final === "FAIL") entry.fail += row._count._all;
      batchTotals.set(row.batchId, entry);
    }
    const recentRows = await this.db.inspection.findMany({
      where,
      orderBy: { createdAt: "desc" },
      take: 10,
      select: {
        id: true,
        result: true,
        reviewResult: true,
        createdAt: true,
        planVersion: true,
        latency: true,
        deviceId: true,
        batchId: true,
      },
    });
    const deviceRows = await this.db.device.findMany({
      select: {
        id: true,
        name: true,
        type: true,
        connectionState: true,
        runtimeState: true,
        lastSeenAt: true,
        reportedState: true,
      },
    });
    const deviceNames = new Map(deviceRows.map((d) => [d.id, d.name]));
    const hours = Math.max(1, span / 3600_000);
    return {
      range: { from: start.toISOString(), to: end.toISOString(), bucket },
      totals: {
        ...totals,
        passRate: totals.decided ? totals.pass / totals.decided : null,
        avgLatencyMs: totals.latencyCount
          ? totals.latencySum / totals.latencyCount
          : null,
        perHour: totals.total / hours,
      },
      series,
      classes,
      batches: batchRows.map((batch) => {
        const counts = batchTotals.get(batch.id) ?? {
          total: batch._count.inspections,
          pass: 0,
          fail: 0,
        };
        const decided = counts.pass + counts.fail;
        return {
          id: batch.id,
          name: batch.name,
          status: batch.status,
          deviceName: deviceNames.get(batch.deviceId) ?? null,
          createdAt: batch.createdAt.toISOString(),
          closedAt: batch.closedAt?.toISOString() ?? null,
          total: counts.total,
          pass: counts.pass,
          fail: counts.fail,
          passRate: decided ? counts.pass / decided : null,
        };
      }),
      recent: recentRows.map((row) => ({
        ...row,
        createdAt: row.createdAt.toISOString(),
        deviceName: row.deviceId
          ? (deviceNames.get(row.deviceId) ?? null)
          : null,
      })),
      devices: deviceRows.map((device) => ({
        id: device.id,
        name: device.name,
        type: device.type,
        connectionState: device.connectionState,
        runtimeState: device.runtimeState,
        lastSeenAt: device.lastSeenAt?.toISOString() ?? null,
        modelVersion:
          (device.reportedState as Record<string, unknown>)?.modelVersion ??
          null,
        planVersion:
          (device.reportedState as Record<string, unknown>)?.planVersion ??
          null,
      })),
      onlineDevices: deviceRows.filter(
        (device) => device.connectionState === "ONLINE",
      ).length,
    };
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
