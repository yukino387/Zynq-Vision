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
import { Prisma } from "@prisma/client";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { Roles, type Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { ModelsService } from "../models/models.service.js";
import { DevicesService } from "../devices/devices.service.js";
import { CommandsService } from "../devices/commands.service.js";
import { FIRMWARE_BUSY_STATES } from "../firmware/firmware.service.js";
@Roles("ADMIN", "ENGINEER")
@Controller("api/deployments")
export class DeploymentsController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(ModelsService) private models: ModelsService,
    @Inject(DevicesService) private devices: DevicesService,
    @Inject(CommandsService) private commands: CommandsService,
    @Inject(Events) private events: Events,
  ) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "createdAt",
      "updatedAt",
      "status",
      "deviceId",
      "source",
    ]);
    return page(
      await this.db.deployment.findMany({
        ...args,
        include: { model: true, device: true },
      }),
      await this.db.deployment.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN") @Post() async create(@Body() body: unknown) {
    const dto = parse(
      z.object({ deviceId: z.string(), modelId: z.string() }).strict(),
      body,
    );
    const { model, transport } = await this.models.check(
      dto.modelId,
      dto.deviceId,
    );
    if (model.status !== "APPROVED")
      throw new DomainError(
        "INVALID_STATE",
        "Benchmark and approve model first",
      );
    return this.db.$transaction(async (tx) => {
      const busy = await tx.deployment.count({
        where: {
          deviceId: dto.deviceId,
          status: {
            in: [
              "APPROVED",
              "DOWNLOADING",
              "VERIFYING",
              "VERIFIED",
              "ACTIVATING",
              "SELF_TEST",
            ],
          },
        },
      });
      if (busy)
        throw new DomainError(
          "DEVICE_BUSY",
          "A deployment is already queued for this device",
        );
      const firmwareBusy = await tx.firmwareDeployment.count({
        where: { deviceId: dto.deviceId, status: { in: FIRMWARE_BUSY_STATES } },
      });
      if (firmwareBusy)
        throw new DomainError(
          "DEVICE_BUSY",
          "设备正在更新固件，请完成后再部署模型",
          409,
        );
      const deployment = await tx.deployment.create({
        data: {
          ...dto,
          name:
            model.source === "SIMULATION"
              ? `SIMULATED ${model.version}`
              : model.version,
          source: model.source === "SIMULATION" ? "SIMULATION" : "BOARD",
          previousVersion: transport.getCurrentModel(),
          receipt: {
            previousPayloadSha256:
              transport.getCurrentConfig().modelPayloadSha256 ?? null,
          },
        },
      });
      await tx.job.create({
        data: { type: "DEPLOYMENT", entityId: deployment.id, payload: {} },
      });
      const device = await tx.device.findUniqueOrThrow({
        where: { id: dto.deviceId },
      });
      await tx.device.update({
        where: { id: dto.deviceId },
        data: {
          desiredState: {
            ...(device.desiredState as Record<string, Prisma.InputJsonValue>),
            modelVersion: model.version,
          },
        },
      });
      return deployment;
    });
  }
  @Roles("ADMIN") @Post(":id/rollback") async rollback(
    @Param("id") id: string,
    @Req() req: Request,
  ) {
    const deployment = await this.db.deployment.findUniqueOrThrow({
      where: { id },
    });
    if (
      !["ACTIVE", "FAILED"].includes(deployment.status) ||
      !deployment.previousVersion
    )
      throw new DomainError(
        "INVALID_STATE",
        "No previous active model available for rollback",
      );
    const candidates = await this.db.model.findMany({
      where: {
        version: deployment.previousVersion,
        source: deployment.source === "BOARD" ? "IMPORT" : deployment.source,
      },
    });
    let previous: (typeof candidates)[number] | undefined;
    for (const candidate of candidates) {
      if (deployment.source !== "BOARD") {
        previous = candidate;
        break;
      }
      const artifact = await this.models.artifact(candidate.id);
      if (
        artifact.weights.subarray(88, 120).toString("hex") ===
        (deployment.receipt as { previousPayloadSha256?: string })
          .previousPayloadSha256
      ) {
        previous = candidate;
        break;
      }
    }
    if (!previous)
      throw new DomainError(
        "INVALID_STATE",
        "The exact previous model artifact is unavailable for rollback",
      );
    const { manifest, weights, transport } = await this.models.check(
      previous.id,
      deployment.deviceId,
    );
    return this.commands.run(
      deployment.deviceId,
      "ROLLBACK",
      req.id,
      async () => {
        await this.db.deployment.update({
          where: { id },
          data: { status: "ROLLBACK" },
        });
        try {
          const receipt = await transport.deployModel(
            previous.version,
            manifest,
            weights,
            async () => {},
          );
          if (
            !receipt.selfTest ||
            !receipt.active ||
            transport.getCurrentModel() !== previous.version
          )
            throw new Error("Rollback not confirmed by device");
          const device = await this.db.device.findUniqueOrThrow({
            where: { id: deployment.deviceId },
          });
          await this.db.device.update({
            where: { id: device.id },
            data: {
              desiredState: {
                ...(device.desiredState as Record<
                  string,
                  Prisma.InputJsonValue
                >),
                modelVersion: previous.version,
              },
              reportedState:
                transport.getCurrentConfig() as Prisma.InputJsonValue,
            },
          });
          await this.db.deployment.updateMany({
            where: {
              deviceId: deployment.deviceId,
              modelId: previous.id,
              status: "SUPERSEDED",
            },
            data: { status: "ACTIVE" },
          });
          const result = await this.db.deployment.update({
            where: { id },
            data: {
              status: "ROLLED_BACK",
              receipt: {
                rollback: receipt as unknown as Prisma.InputJsonValue,
              },
            },
          });
          this.events.emit(
            "deployment.completed",
            id,
            result,
            deployment.source,
            req.id,
          );
          return result;
        } catch (error) {
          await this.db.deployment.update({
            where: { id },
            data: { status: "FAILED", error: String(error) },
          });
          throw error;
        }
      },
    );
  }
}
