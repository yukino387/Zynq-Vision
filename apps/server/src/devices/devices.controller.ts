import { isLinuxTerminal } from "./terminal-state.js";
import { terminalRequest } from "./terminal-client.js";
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
import { Roles, type Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { terminalCapabilities, terminalStatus } from "./terminal-state.js";
import { DevicesService } from "./devices.service.js";
import { CommandsService } from "./commands.service.js";
import { baseCapabilities } from "./transport.js";
import { config } from "../config.js";
import { planRulesSchema, acceptanceSchema } from "@vision/contracts";
import { mqttConfigSchema } from "@vision/contracts";
import { productClassesMatch } from "@vision/shared";
import { manifestSchema } from "@vision/contracts";
import { AssetsService } from "../assets/assets.service.js";
import { deployTerminalModel } from "../deployments/terminal-deployment.js";
@Controller("api/devices")
export class DevicesController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(DevicesService) private devices: DevicesService,
    @Inject(CommandsService) private commands: CommandsService,
    @Inject(AssetsService) private assets: AssetsService,
  ) {}
  @Roles("ADMIN", "ENGINEER") @Get(":id/mqtt") async mqtt(
    @Param("id") id: string,
    @Req() req: Request,
  ) {
    const device = await this.db.device.findUniqueOrThrow({ where: { id } });
    return (
      await terminalRequest(device, "/mqtt", req.headers.authorization ?? "")
    ).json();
  }
  @Roles("ADMIN") @Post(":id/mqtt") async configureMqtt(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const config = parse(mqttConfigSchema, body);
    const device = await this.db.device.findUniqueOrThrow({ where: { id } });
    return (
      await terminalRequest(
        device,
        "/mqtt/config",
        req.headers.authorization ?? "",
        config,
      )
    ).json();
  }
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
    const device = await this.db.device.create({
      data: {
        ...dto,
        protocolVersion: dto.type === "ZYNQ" ? null : "SIMULATED-v1",
        capabilities: (dto.type === "ZYNQ"
          ? terminalCapabilities
          : baseCapabilities) as unknown as Prisma.InputJsonValue,
        reportedState:
          dto.type === "SIMULATOR"
            ? {
                modelVersion: "SIM-V1",
                planVersion: "SIM-P1",
                inspectionEnabled: true,
              }
            : {},
        metadata: {
          ...(dto.type === "ZYNQ" ? { runtimeProfile: "LINUX_TERMINAL" } : {}),
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
      const device = await this.db.device.findUniqueOrThrow({ where: { id } });
      if (!isLinuxTerminal(device)) {
        await this.devices.transport(id).connect();
        return this.devices.transport(id).getStatus();
      }
      return (
        await terminalRequest(
          device,
          "/control",
          req.headers.authorization ?? "",
          { type: "CONNECT" },
        )
      ).json();
    });
  }
  @Roles("ADMIN", "ENGINEER") @Post(":id/disconnect") disconnect(
    @Param("id") id: string,
    @Req() req: Request,
  ) {
    return this.commands.run(id, "DISCONNECT", req.id, async () => {
      const device = await this.db.device.findUniqueOrThrow({ where: { id } });
      if (isLinuxTerminal(device)) return { disconnected: true };
      await this.devices.transport(id).disconnect();
      return { disconnected: true };
    });
  }
  /** 把产品规则分配给终端；生产中必须显式确认停止。 */
  @Roles("ADMIN", "ENGINEER") @Post(":id/product") async product(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          planId: z.string().min(1),
          modelId: z.string().min(1).optional(),
          start: z.boolean().optional(),
          acceptance: acceptanceSchema.optional(),
          confirm: z.boolean().optional(),
        })
        .strict(),
      body,
    );
    const device = await this.db.device.findUniqueOrThrow({ where: { id } });
    if (!isLinuxTerminal(device))
      throw new DomainError("NO_CAPABILITY", "该设备不支持产品分配", 422);
    const status = await terminalStatus(this.db, device);
    if (!status.online || !status.state)
      throw new DomainError("UNAVAILABLE", "设备未连接，请等待设备上线", 409);
    if (!status.state.model && !dto.modelId)
      throw new DomainError("INVALID_STATE", "请先下发模型，再分配产品", 409);
    const plan = await this.db.inspectionPlan.findUniqueOrThrow({
      where: { id: dto.planId },
    });
    if (plan.deletedAt)
      throw new DomainError("INVALID_STATE", "产品已删除", 409);
    const rules = parse(planRulesSchema, plan.rules);
    const selectedModel = dto.modelId
      ? await this.db.model.findUniqueOrThrow({ where: { id: dto.modelId } })
      : null;
    if (selectedModel && selectedModel.status !== "APPROVED")
      throw new DomainError(
        "INVALID_STATE",
        "请先在模型仓库批准此模型用于生产",
        409,
      );
    const classes = selectedModel
      ? parse(manifestSchema, selectedModel.manifest).classes
      : status.state.model!.classes;
    if (!productClassesMatch(rules.classes, classes))
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "所选模型的类别及顺序与产品不匹配，请重新选择兼容模型",
        422,
      );
    if (!rules.checks.some((check) => check.min > 0))
      throw new DomainError(
        "VALIDATION_ERROR",
        "自动过件需要至少一个必需类别；请把产品主体加入识别类别",
        422,
      );
    if (selectedModel && selectedModel.id !== status.state.model?.id) {
      if (req.actor.role !== "ADMIN")
        throw new DomainError("FORBIDDEN", "更换设备模型需要管理员操作", 403);
      const installed = await deployTerminalModel(
        this.db,
        this.assets,
        this.commands,
        device,
        selectedModel.id,
        req.actor.id,
        req.headers.authorization ?? "",
        req.id,
        dto.confirm ?? false,
      );
      if (!installed.state)
        throw new DomainError(
          "UNAVAILABLE",
          "模型尚未确认生效。请查看应用记录，确认模型状态后再应用产品",
          503,
        );
      status.state = installed.state as typeof status.state;
    }
    const current = status.state.product;
    const acceptance =
      dto.acceptance ??
      (current?.id === plan.id && current.version === plan.version
        ? current.acceptance
        : { confidence: 0.7, qualityGate: true });
    const unchanged = !!(
      current &&
      current.id === plan.id &&
      current.version === plan.version &&
      current.acceptance.confidence === acceptance.confidence &&
      current.acceptance.qualityGate === acceptance.qualityGate
    );
    if (!unchanged && status.state.production && !dto.confirm)
      throw new DomainError(
        "DEVICE_BUSY",
        "请先停止自动检测并确认当前件已处理，再切换产品",
        409,
      );
    let installed = unchanged
      ? status.state
      : await (
          await terminalRequest(
            device,
            "/runtime/product",
            req.headers.authorization ?? "",
            {
              planId: plan.id,
              planName: rules.product,
              planVersion: plan.version,
              product: rules.product,
              rules,
              acceptance,
              confirm: dto.confirm ?? false,
            },
            30000,
          )
        ).json();
    if (dto.start && !installed.production) {
      installed = await this.commands.run(
        id,
        "START_INSPECTION",
        req.id,
        async () =>
          (
            await terminalRequest(
              device,
              "/control",
              req.headers.authorization ?? "",
              {
                type: "START_INSPECTION",
              },
            )
          ).json(),
      );
    }
    const metadata = device.metadata as Prisma.JsonObject;
    const previous = metadata.terminal as Prisma.JsonObject;
    const reported = Object.fromEntries(
      [
        "model",
        "product",
        "production",
        "productionRunId",
        "paused",
        "fresh",
        "runCounts",
        "runTotal",
        "total",
        "counts",
        "pendingSync",
        "pendingRequestId",
        "passagePhase",
        "last",
        "error",
        "syncError",
      ]
        .filter((key) => key in installed)
        .map((key) => [key, installed[key]]),
    );
    await this.db.device.update({
      where: { id },
      data: {
        metadata: {
          ...metadata,
          terminal: {
            ...previous,
            ...reported,
            receivedAt: new Date().toISOString(),
          },
        } as Prisma.InputJsonValue,
      },
    });
    return installed;
  }
  /** 停止状态下的单件补检/调试；自动生产中由引擎拒绝。 */
  @Roles("ADMIN", "ENGINEER", "OPERATOR") @Post(":id/check") async check(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z.object({ requestId: z.string().uuid().optional() }).strict(),
      body,
    );
    const device = await this.db.device.findUniqueOrThrow({ where: { id } });
    if (!isLinuxTerminal(device))
      throw new DomainError("NO_CAPABILITY", "该设备不支持单件检查", 422);
    const status = await terminalStatus(this.db, device);
    if (!status.online || !status.state)
      throw new DomainError("UNAVAILABLE", "设备未连接，请等待设备上线", 409);
    // The engine can confirm a previously saved request even after production resumes.
    const requestId = dto.requestId ?? crypto.randomUUID();
    return this.commands.run(id, "CHECK_ONE", req.id, async () =>
      (
        await terminalRequest(
          device,
          "/control",
          req.headers.authorization ?? "",
          { type: "CHECK_ONE", requestId },
          15000,
        )
      ).json(),
    );
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
  @Roles("ADMIN", "ENGINEER", "OPERATOR") @Post(":id/commands") async command(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          type: z.enum(["GET_STATUS", "START_INSPECTION", "STOP_INSPECTION"]),
        })
        .strict(),
      body,
    );
    const device = await this.db.device.findUniqueOrThrow({ where: { id } });
    return this.commands.run(id, dto.type, req.id, async () => {
      if (!isLinuxTerminal(device))
        return this.devices.transport(id).sendCommand(dto.type);
      return (
        await terminalRequest(
          device,
          "/control",
          req.headers.authorization ?? "",
          dto,
        )
      ).json();
    });
  }
}
