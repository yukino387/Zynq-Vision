import {
  Controller,
  Get,
  Post,
  Patch,
  Param,
  Query,
  Body,
  Inject,
  Req,
} from "@nestjs/common";
import { hash } from "bcryptjs";
import { z } from "zod";
import { roles } from "@vision/contracts";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { Roles, type Request } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
const names = z.string().min(1).max(120);
const safeUser = {
  id: true,
  username: true,
  name: true,
  role: true,
  disabled: true,
  createdAt: true,
  updatedAt: true,
} as const;
@Roles("ADMIN")
@Controller("api/users")
export class UsersController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(Events) private events: Events,
  ) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, ["name", "createdAt", "updatedAt"]);
    return page(
      await this.db.user.findMany({ ...args, select: safeUser }),
      await this.db.user.count({ where: args.where }),
      q,
    );
  }
  @Post() async create(@Body() body: unknown) {
    const dto = parse(
      z
        .object({
          name: names,
          username: names,
          password: z.string().min(12).max(100),
          role: z.enum(roles),
        })
        .strict(),
      body,
    );
    return this.db.user.create({
      data: {
        name: dto.name,
        username: dto.username,
        role: dto.role,
        passwordHash: await hash(dto.password, 12),
      },
      select: safeUser,
    });
  }
  @Patch(":id") async update(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          disabled: z.boolean().optional(),
          role: z.enum(roles).optional(),
        })
        .strict(),
      body,
    );
    if (
      req.actor.id === id &&
      (dto.disabled || (dto.role && dto.role !== "ADMIN"))
    )
      throw new DomainError(
        "INVALID_STATE",
        "不能停用或降低当前登录账号的权限",
      );
    const user = await this.db.$transaction(async (tx) => {
      const current = await tx.user.findUniqueOrThrow({ where: { id } });
      if (
        current.role === "ADMIN" &&
        !current.disabled &&
        (dto.disabled || (dto.role && dto.role !== "ADMIN")) &&
        (await tx.user.count({ where: { role: "ADMIN", disabled: false } })) <=
          1
      )
        throw new DomainError("INVALID_STATE", "至少需要保留一个启用的管理员");
      return tx.user.update({ where: { id }, data: dto, select: safeUser });
    });
    if (user.disabled || dto.role) this.events.closeUser(id);
    return user;
  }
}
@Controller("api/stations")
export class StationsController {
  constructor(@Inject(Db) private db: Db) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, ["name", "createdAt", "updatedAt"]);
    return page(
      await this.db.station.findMany({ ...args, include: { devices: true } }),
      await this.db.station.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN", "ENGINEER") @Post() create(@Body() body: unknown) {
    return this.db.station.create({
      data: parse(z.object({ name: names, code: names }).strict(), body),
    });
  }
}
@Controller("api/tasks")
export class TasksController {
  constructor(@Inject(Db) private db: Db) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "status",
      "createdAt",
      "updatedAt",
      "stationId",
    ]);
    return page(
      await this.db.task.findMany({
        ...args,
        include: { _count: { select: { samples: true } } },
      }),
      await this.db.task.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN", "ENGINEER") @Post() create(@Body() body: unknown) {
    return this.db.task.create({
      data: parse(
        z
          .object({
            name: names,
            target: z.number().int().positive(),
            stationId: z.string().optional(),
            planId: z.string().optional(),
          })
          .strict(),
        body,
      ),
    });
  }
  @Get(":id") detail(@Param("id") id: string) {
    return this.db.task.findUniqueOrThrow({
      where: { id },
      include: {
        plan: true,
        station: true,
        _count: { select: { samples: true } },
      },
    });
  }
}
@Controller("api/workpieces")
export class WorkpiecesController {
  constructor(@Inject(Db) private db: Db) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, ["name", "createdAt"]);
    return page(
      await this.db.workpiece.findMany(args),
      await this.db.workpiece.count({ where: args.where }),
      q,
    );
  }
  @Post() create(@Body() body: unknown) {
    return this.db.workpiece.create({
      data: parse(
        z.object({ name: names, serialNumber: names }).strict(),
        body,
      ),
    });
  }
}
