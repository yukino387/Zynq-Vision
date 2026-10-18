import "@fastify/multipart";
import {
  Body,
  Controller,
  Get,
  Inject,
  Param,
  Post,
  Query,
  Req,
} from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { z } from "zod";
import { Db } from "../core/db.js";
import { Roles, type Request } from "../core/auth.js";
import { DomainError, parse } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { AssetsService } from "../assets/assets.service.js";
import { FirmwareService } from "./firmware.service.js";
import { validateFirmwarePackage } from "./package.js";

@Roles("ADMIN", "ENGINEER")
@Controller("api")
export class FirmwareController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(AssetsService) private assets: AssetsService,
    @Inject(FirmwareService) private firmware: FirmwareService,
  ) {}

  @Get("firmware") async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "version",
      "status",
      "createdAt",
      "updatedAt",
    ]);
    return page(
      await this.db.firmware.findMany({
        ...args,
        include: { asset: true, _count: { select: { deployments: true } } },
      }),
      await this.db.firmware.count({ where: args.where }),
      q,
    );
  }

  @Roles("ADMIN") @Post("firmware/upload") async upload(@Req() req: Request) {
    let content: Buffer | null = null,
      name = "",
      notes = "",
      originalName = "firmware.fw";
    for await (const part of req.parts()) {
      if (part.type === "file") {
        content = await part.toBuffer();
        originalName = part.filename || originalName;
        if (part.file.truncated)
          throw new DomainError(
            "VALIDATION_ERROR",
            "Firmware package exceeds the 20MB upload limit",
            413,
          );
      } else if (part.fieldname === "name") name = String(part.value);
      else if (part.fieldname === "notes") notes = String(part.value);
    }
    if (!content)
      throw new DomainError("VALIDATION_ERROR", "Firmware package required", 400);
    const packageValue = validateFirmwarePackage(content);
    const trimmedNotes = notes.trim();
    if (trimmedNotes.length > 500)
      throw new DomainError(
        "VALIDATION_ERROR",
        "Firmware notes must be at most 500 characters",
        400,
      );
    if (
      await this.db.firmware.findUnique({
        where: { version: packageValue.version },
      })
    )
      throw new DomainError(
        "CONSTRAINT_VIOLATION",
        `固件版本 ${packageValue.version} 已存在`,
        409,
      );
    const asset = await this.assets.store(
      content,
      "FIRMWARE_PACKAGE",
      "IMPORT",
      originalName,
      "application/octet-stream",
    );
    try {
      return await this.db.firmware.create({
        data: {
          name: name.trim() || `PS 应用固件 ${packageValue.version}`,
          version: packageValue.version,
          sha256: packageValue.sha256,
          size: packageValue.size,
          imageSize: packageValue.imageSize,
          entry: packageValue.entry,
          segments: packageValue.segments as unknown as Prisma.InputJsonValue,
          notes: trimmedNotes || null,
          asset: { create: asset },
        },
        include: { asset: true },
      });
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === "P2002"
      )
        throw new DomainError(
          "CONSTRAINT_VIOLATION",
          `固件版本 ${packageValue.version} 已存在`,
          409,
        );
      throw error;
    }
  }

  @Get("firmware/:id") detail(@Param("id") id: string) {
    return this.db.firmware.findUniqueOrThrow({
      where: { id },
      include: {
        asset: true,
        deployments: {
          include: { device: true },
          orderBy: { createdAt: "desc" },
          take: 20,
        },
      },
    });
  }

  @Roles("ADMIN") @Post("firmware/:id/deploy") async deploy(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    const dto = parse(z.object({ deviceId: z.string().min(1) }).strict(), body);
    return this.firmware.createDeployment(id, dto.deviceId);
  }

  @Get("firmware-deployments") async deployments(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "createdAt",
      "updatedAt",
      "status",
      "deviceId",
    ]);
    return page(
      await this.db.firmwareDeployment.findMany({
        ...args,
        include: { firmware: true, device: true },
      }),
      await this.db.firmwareDeployment.count({ where: args.where }),
      q,
    );
  }

  @Roles("ADMIN") @Post("firmware-deployments/:id/rollback")
  async rollback(@Param("id") id: string, @Body() body: unknown) {
    const dto = parse(
      z.object({ target: z.enum(["PREVIOUS", "GOLDEN"]) }).strict(),
      body,
    );
    return this.firmware.rollback(id, dto.target);
  }

  @Get("devices/:id/firmware") info(@Param("id") id: string) {
    return this.firmware.info(id);
  }
}
