import { Controller, Get, Post, Query, Body, Inject } from "@nestjs/common";
import { z } from "zod";
import { Db } from "../core/db.js";
import { Roles } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { ModelsService } from "./models.service.js";
@Roles("ADMIN", "ENGINEER")
@Controller("api/benchmarks")
export class BenchmarksController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(ModelsService) private models: ModelsService,
  ) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "createdAt",
      "source",
      "deviceId",
    ]);
    return page(
      await this.db.benchmark.findMany({
        ...args,
        include: { model: true, dataset: true },
      }),
      await this.db.benchmark.count({ where: args.where }),
      q,
    );
  }
  @Post() async create(@Body() body: unknown) {
    const dto = parse(
      z
        .object({
          name: z.string().min(1),
          modelId: z.string(),
          datasetId: z.string(),
          deviceId: z.string(),
        })
        .strict(),
      body,
    );
    const { model, transport } = await this.models.check(
      dto.modelId,
      dto.deviceId,
    );
    const dataset = await this.db.dataset.findUniqueOrThrow({
      where: { id: dto.datasetId },
    });
    if (dataset.status !== "FROZEN")
      throw new DomainError(
        "INVALID_STATE",
        "Benchmark requires frozen dataset",
      );
    const frame = await transport.captureOnce();
    return this.db.$transaction(async (tx) => {
      const benchmark = await tx.benchmark.create({
        data: {
          ...dto,
          source: "SIMULATION",
          metrics: {
            label: "SIMULATED BENCHMARK",
            candidateExecuted: false,
            inferenceUs: frame.telemetry?.inferenceUs ?? null,
            cycleUs: frame.telemetry?.cycleUs ?? null,
            fps: frame.telemetry?.fps ?? null,
            accuracy: null,
            precision: null,
            recall: null,
            mAP: null,
            purpose:
              "Simulator profile compatibility and current telemetry; no candidate accuracy evaluation",
            input: model.manifest as PrismaJson,
          },
        },
      });
      await tx.model.update({
        where: { id: model.id },
        data: { status: "APPROVED" },
      });
      return benchmark;
    });
  }
}
type PrismaJson = import("@prisma/client").Prisma.InputJsonValue;
