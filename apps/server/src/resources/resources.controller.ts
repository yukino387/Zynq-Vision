import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Param,
  Query,
  Body,
  Inject,
  Req,
} from "@nestjs/common";
import { hash } from "bcryptjs";
import { z } from "zod";
import { roles, createPlanSchema, planRulesSchema } from "@vision/contracts";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { root } from "../config.js";
import { Prisma } from "@prisma/client";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { Roles, newPasswordSchema, type Request } from "../core/auth.js";
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
          password: z.string().min(8).max(100),
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
  @Post(":id/password") async resetPassword(
    @Param("id") id: string,
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    if (id === req.actor.id)
      throw new DomainError(
        "INVALID_STATE",
        "请到账号设置中验证当前密码后修改自己的密码",
        400,
      );
    const dto = parse(
      z.object({ newPassword: newPasswordSchema }).strict(),
      body,
    );
    const user = await this.db.user.update({
      where: { id },
      data: {
        passwordHash: await hash(dto.newPassword, 12),
        sessionVersion: { increment: 1 },
      },
      select: safeUser,
    });
    this.events.closeUser(id, "Password changed");
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
    const conditions: Prisma.TaskWhereInput[] = [
      { status: { not: "DELETED" } },
    ];
    args.where.AND = conditions;
    if (q.realOnly === "true") {
      const plans = await this.db.inspectionPlan.findMany({
        select: { id: true, rules: true },
      });
      const simulatedPlans = plans
        .filter(
          (plan) => (plan.rules as { source?: string }).source === "SIMULATION",
        )
        .map((plan) => plan.id);
      if (simulatedPlans.length)
        conditions.push({
          OR: [{ planId: null }, { planId: { notIn: simulatedPlans } }],
        });
    }
    return page(
      await this.db.task.findMany({
        ...args,
        include: {
          plan: true,
          station: true,
          _count: { select: { samples: { where: { deletedAt: null } } } },
        },
      }),
      await this.db.task.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN") @Post() async create(@Body() body: unknown) {
    const data = parse(
      z
        .object({
          name: z.string().trim().min(1).max(120),
          target: z.number().int().positive(),
          stationId: z.string().optional(),
          planId: z.string().optional(),
        })
        .strict(),
      body,
    );
    if (data.planId)
      await this.db.inspectionPlan.findUniqueOrThrow({
        where: { id: data.planId, deletedAt: null },
      });
    return this.db.task.create({ data });
  }
  @Get(":id") detail(@Param("id") id: string) {
    return this.db.task.findUniqueOrThrow({
      where: { id, status: { not: "DELETED" } },
      include: {
        plan: true,
        station: true,
        _count: { select: { samples: { where: { deletedAt: null } } } },
      },
    });
  }
  @Roles("ADMIN") @Patch(":id") update(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    const data = parse(
      z
        .object({
          name: z.string().trim().min(1).max(120),
          target: z.number().int().positive(),
          status: z.enum(["OPEN", "COMPLETED"]),
        })
        .strict(),
      body,
    );
    return this.db.task.update({
      where: { id, status: { not: "DELETED" } },
      data,
    });
  }
  @Roles("ADMIN") @Delete(":id") async remove(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    parse(z.object({ confirm: z.literal(true) }).strict(), body);
    // Preserve task/plan links needed by existing annotations and inspection history.
    await this.db.task.update({ where: { id }, data: { status: "DELETED" } });
    return { id };
  }
}
@Roles("ADMIN", "ENGINEER")
@Controller("api/plans")
export class PlansController {
  constructor(@Inject(Db) private db: Db) {}
  @Get("scenarios") async scenarios() {
    // Reload editable server configuration; applying a template still creates a normal plan version.
    const content = await readFile(
      resolve(root, "config/inspection-scenarios.json"),
      "utf8",
    );
    return parse(
      z
        .array(
          z
            .object({
              id: z.string().min(1).max(64),
              name: z.string().min(1).max(120),
              description: z.string().max(1000),
              rules: planRulesSchema,
            })
            .strict(),
        )
        .max(32)
        .refine(
          (items) =>
            new Set(items.map((item) => item.id)).size === items.length,
        ),
      JSON.parse(content),
    );
  }
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, ["name", "createdAt", "version"]);
    args.where.deletedAt = null;
    return page(
      await this.db.inspectionPlan.findMany(args),
      await this.db.inspectionPlan.count({ where: args.where }),
      q,
    );
  }
  @Roles("ADMIN") @Post() async create(@Body() body: unknown) {
    const dto = parse(createPlanSchema, body);
    return this.db.$transaction(async (tx) => {
      const latest = await tx.inspectionPlan.findFirst({
        where: { name: dto.name },
        orderBy: { version: "desc" },
      });
      return tx.inspectionPlan.create({
        data: {
          name: dto.name,
          version: (latest?.version ?? 0) + 1,
          rules: dto.rules as Prisma.InputJsonValue,
        },
      });
    });
  }
  @Roles("ADMIN") @Delete(":id") async remove(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    parse(z.object({ confirm: z.literal(true) }).strict(), body);
    await this.db.inspectionPlan.update({
      where: { id },
      data: { deletedAt: new Date() },
    });
    return { id };
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
