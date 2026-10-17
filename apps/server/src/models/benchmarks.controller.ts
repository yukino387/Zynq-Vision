import { randomUUID } from "node:crypto";
import { CommandsService } from "../devices/commands.service.js";
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
    @Inject(CommandsService) private commands: CommandsService,
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
    const { model, transport, manifest, weights } = await this.models.check(
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
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: dto.deviceId },
    });
    const real = device.type === "ZYNQ";
    const before = transport.getStatus();
    const previousVersion = transport.getCurrentModel();
    const previousModels =
      real && previousVersion && previousVersion !== model.version
        ? await this.db.model.findMany({
            where: { version: previousVersion, source: "IMPORT" },
          })
        : [];
    let previousModel: (typeof previousModels)[number] | null = null;
    for (const candidate of previousModels) {
      const artifact = await this.models.artifact(candidate.id);
      if (
        artifact.weights.subarray(88, 120).toString("hex") ===
        before.reportedState.modelPayloadSha256
      ) {
        previousModel = candidate;
        break;
      }
    }
    if (real && previousVersion !== model.version && !previousModel)
      throw new DomainError(
        "INVALID_STATE",
        "Import the active model before evaluating a replacement so it can be restored",
      );
    const frame = real
      ? await this.commands.run(
          dto.deviceId,
          "BENCHMARK",
          randomUUID(),
          async () => {
            try {
              await transport.deployModel(
                model.version,
                manifest,
                weights,
                async () => {},
              );
              await transport.sendCommand("CAMERA_ONLY", 0);
              await transport.sendCommand("START_INSPECTION");
              const deadline = Date.now() + 15000;
              while (Date.now() < deadline) {
                try {
                  const frame = await transport.captureOnce();
                  if (
                    frame.modelState.modelVersion === model.version &&
                    frame.outputs &&
                    frame.telemetry &&
                    frame.telemetry.errorCode === 0
                  )
                    return frame;
                } catch (error) {
                  if (
                    !(error instanceof DomainError) ||
                    error.getStatus() !== 409
                  )
                    throw error;
                }
                await new Promise((resolve) => setTimeout(resolve, 50));
              }
              throw new DomainError(
                "DEVICE_TIMEOUT",
                "No complete inference frame confirmed for candidate model",
                504,
              );
            } finally {
              if (previousModel) {
                const previous = await this.models.artifact(previousModel.id);
                await transport.deployModel(
                  previous.model.version,
                  previous.manifest,
                  previous.weights,
                  async () => {},
                );
              }
              await transport.sendCommand(
                "CAMERA_ONLY",
                Number(before.reportedState.cameraOnly),
              );
              await transport.sendCommand(
                before.runtimeState === "RUNNING"
                  ? "START_INSPECTION"
                  : "STOP_INSPECTION",
              );
            }
          },
        )
      : await transport.captureOnce();
    return this.db.$transaction(async (tx) => {
      const benchmark = await tx.benchmark.create({
        data: {
          ...dto,
          source: real ? "BOARD" : "SIMULATION",
          metrics: {
            label: real ? "BOARD INFERENCE CHECK" : "SIMULATED BENCHMARK",
            candidateExecuted: real,
            frameId: frame.frameId,
            restoredModelVersion: real ? previousVersion : null,
            inferenceUs: frame.telemetry?.inferenceUs ?? null,
            cycleUs: frame.telemetry?.cycleUs ?? null,
            fps: frame.telemetry?.fps ?? null,
            accuracy: null,
            precision: null,
            recall: null,
            mAP: null,
            purpose: real
              ? "Candidate inference on real hardware; unlabeled capture, no accuracy evaluation"
              : "Simulator profile compatibility and current telemetry; no candidate accuracy evaluation",
            input: model.manifest as PrismaJson,
          },
        },
      });
      return benchmark;
    });
  }
}
type PrismaJson = import("@prisma/client").Prisma.InputJsonValue;
