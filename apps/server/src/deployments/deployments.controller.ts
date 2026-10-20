import { AssetsService } from "../assets/assets.service.js";
import { deployTerminalModel } from "./terminal-deployment.js";
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
import { Roles, type Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { CommandsService } from "../devices/commands.service.js";
@Roles("ADMIN", "ENGINEER")
@Controller("api/deployments")
export class DeploymentsController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(AssetsService) private assets: AssetsService,
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
  @Roles("ADMIN") @Post() async create(
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          deviceId: z.string().min(1),
          modelId: z.string().min(1),
          confirm: z.boolean().optional(),
        })
        .strict(),
      body,
    );
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: dto.deviceId },
    });
    if (device.type !== "ZYNQ")
      throw new DomainError("NO_CAPABILITY", "该设备不支持模型下发", 422);
    const result = await deployTerminalModel(
      this.db,
      this.assets,
      this.commands,
      device,
      dto.modelId,
      req.actor.id,
      req.headers.authorization ?? "",
      req.id,
      dto.confirm ?? false,
    );
    if (result.deployment.status === "ACTIVE")
      this.events.emit(
        "deployment.completed",
        result.deployment.id,
        { status: "ACTIVE" },
        "SERVER",
        req.id,
      );
    return result.deployment;
  }
  @Roles("ADMIN") @Post(":id/rollback") async rollback(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    parse(z.object({ confirm: z.literal(true) }).strict(), body);
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
    const receipt = deployment.receipt as Record<string, unknown>;
    const previous =
      typeof receipt.previousModelId === "string"
        ? await this.db.model.findUnique({
            where: { id: receipt.previousModelId },
          })
        : null;
    if (previous && previous.version !== deployment.previousVersion)
      throw new DomainError("INVALID_STATE", "上一模型的版本信息不一致", 409);
    if (!previous)
      throw new DomainError(
        "INVALID_STATE",
        "The exact previous model artifact is unavailable for rollback",
      );
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: deployment.deviceId },
    });
    return deployTerminalModel(
      this.db,
      this.assets,
      this.commands,
      device,
      previous.id,
      req.actor.id,
      req.headers.authorization ?? "",
      req.id,
      true,
    );
  }
}
