import {
  Controller,
  Get,
  Post,
  Patch,
  Param,
  Body,
  Query,
  Req,
  Inject,
  ForbiddenException,
} from "@nestjs/common";
import { z } from "zod";
import { Prisma } from "@prisma/client";
import { Db } from "../core/db.js";
import { Roles, type Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { DevicesService } from "./devices.service.js";
import { CommandsService } from "./commands.service.js";
import { baseCapabilities } from "./transport.js";
import { config } from "../config.js";
@Controller("api/devices")
export class DevicesController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(DevicesService) private devices: DevicesService,
    @Inject(CommandsService) private commands: CommandsService,
  ) {}
  @Get("snapshot") snapshots() {
    return this.devices.snapshots();
  }
  @Get("policy") policy() {
    return {
      staleMs: config.DEVICE_STALE,
      offlineMs: config.DEVICE_TIMEOUT,
      wsPath: config.WS_PATH,
    };
  }
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "createdAt",
      "updatedAt",
      "stationId",
    ]);
    return page(
      await this.db.device.findMany(args),
      await this.db.device.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN", "ENGINEER") @Post() async create(@Body() body: unknown) {
    const dto = parse(
      z
        .object({
          name: z.string().min(1).max(100),
          serialNumber: z.string().min(1).max(100),
          type: z.enum(["SIMULATOR", "ZYNQ"]),
          stationId: z.string().optional(),
        })
        .strict(),
      body,
    );
    if (
      dto.type === "ZYNQ" &&
      (await this.db.device.count({ where: { type: "ZYNQ" } }))
    )
      throw new DomainError(
        "INVALID_STATE",
        "This adapter currently supports one configured Zynq endpoint",
        409,
      );
    const device = await this.db.device.create({
      data: {
        ...dto,
        protocolVersion:
          dto.type === "ZYNQ"
            ? "CNC1/CST1/YLO1 (source verified)"
            : "SIMULATED-v1",
        capabilities: baseCapabilities as unknown as Prisma.InputJsonValue,
        reportedState:
          dto.type === "SIMULATOR"
            ? {
                modelVersion: "SIM-V1",
                planVersion: "SIM-P1",
                inspectionEnabled: true,
              }
            : {},
        metadata: {
          source:
            dto.type === "SIMULATOR"
              ? "SIMULATED"
              : "SOURCE_VERIFIED_NOT_DEVICE_REPORTED",
        },
      },
    });
    await this.devices.attach(device.id);
    return device;
  }
  @Get(":id") async detail(@Param("id") id: string) {
    return {
      ...(await this.db.device.findUniqueOrThrow({
        where: { id },
        include: {
          events: { take: 30, orderBy: { createdAt: "desc" } },
          commands: { take: 20, orderBy: { createdAt: "desc" } },
        },
      })),
      snapshot: (await this.devices.snapshots()).find((d) => d.id === id),
    };
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/connect") connect(
    @Param("id") id: string,
    @Req() req: Request,
  ) {
    return this.commands.run(id, "CONNECT", req.id, async () => {
      await this.devices.transport(id).connect();
      return this.devices.transport(id).getStatus();
    });
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/disconnect") disconnect(
    @Param("id") id: string,
    @Req() req: Request,
  ) {
    return this.commands.run(id, "DISCONNECT", req.id, async () => {
      await this.devices.transport(id).disconnect();
      return { disconnected: true };
    });
  }
  @Roles("ADMIN") @Patch(":id/desired") async desired(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    const dto = parse(
      z
        .object({
          modelVersion: z.string().min(1).optional(),
          planVersion: z.string().min(1).optional(),
          inspectionEnabled: z.boolean().optional(),
        })
        .strict(),
      body,
    );
    await this.db.device.update({ where: { id }, data: { desiredState: dto } });
    return (await this.devices.snapshots()).find((d) => d.id === id);
  }
  /** 删除设备 SD 模型库里的一个槽位。板端会拒绝删当前版本和上一版。 */
  @Roles("ADMIN", "ENGINEER") @Post(":id/models/delete") async removeModel(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z.object({ index: z.number().int().min(0) }).strict(),
      body,
    );
    await this.commands.run(id, "DELETE_MODEL", req.id, () =>
      this.devices.transport(id).deleteModel(dto.index),
    );
    return (await this.devices.snapshots()).find((d) => d.id === id);
  }
  @Roles("ADMIN", "ENGINEER")
  @Post(":id/commands/:commandId/cancel")
  async cancel(@Param("id") deviceId: string, @Param("commandId") id: string) {
    const result = await this.db.command.updateMany({
      where: { id, deviceId, status: "QUEUED" },
      data: { status: "CANCELLED", completedAt: new Date() },
    });
    if (!result.count)
      throw new DomainError(
        "INVALID_STATE",
        "Only queued commands can be cancelled",
      );
    return { id, status: "CANCELLED" };
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/commands") command(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          type: z.enum([
            "GET_STATUS",
            "START_INSPECTION",
            "STOP_INSPECTION",
            "SET_BRIGHTNESS",
            "CAMERA_ONLY",
            "SET_PLAN",
            "FAULT",
          ]),
          value: z.union([z.string(), z.number().int()]).optional(),
        })
        .strict(),
      body,
    );
    if (dto.type === "SET_PLAN" && req.actor.role !== "ADMIN")
      throw new ForbiddenException("只有管理员可以修改设备使用的方案");
    if (
      dto.type === "SET_BRIGHTNESS" &&
      (typeof dto.value !== "number" || dto.value < -4 || dto.value > 4)
    )
      throw new DomainError(
        "VALIDATION_ERROR",
        "Brightness range is -4..4",
        400,
      );
    if (dto.type === "CAMERA_ONLY" && dto.value !== 0 && dto.value !== 1)
      throw new DomainError("VALIDATION_ERROR", "Camera mode is 0 or 1", 400);
    if (dto.type === "FAULT")
      parse(
        z.enum([
          "NONE",
          "NETWORK_LOST",
          "DEVICE_TIMEOUT",
          "INVALID_MODEL",
          "CHECKSUM_ERROR",
          "INFERENCE_ERROR",
          "DEPLOYMENT_FAILED",
          "LOW_FPS",
          "HIGH_LATENCY",
          "QUEUE_OVERFLOW",
        ]),
        dto.value,
      );
    return this.commands.run(id, dto.type, req.id, () =>
      this.devices.transport(id).sendCommand(dto.type, dto.value),
    );
  }
}
