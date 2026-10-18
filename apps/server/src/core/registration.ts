import {
  Body,
  Controller,
  Get,
  Inject,
  Param,
  Patch,
  Post,
  Req,
  Query,
} from "@nestjs/common";
import { JwtService } from "@nestjs/jwt";
import { createHash, randomBytes } from "node:crypto";
import { hash } from "bcryptjs";
import type { FastifyRequest } from "fastify";
import { z } from "zod";
import { Db } from "./db.js";
import { Public, Roles, type Request } from "./auth.js";
import { DomainError, parse } from "./errors.js";

const codeSchema = z.string().trim().min(1).max(100);
/** 注册码永远发不出管理员账号；管理员只能由现有管理员直接创建。 */
const codeRoles = ["OPERATOR", "ENGINEER"] as const;
const digest = (code: string) =>
  createHash("sha256").update(code.trim().toUpperCase()).digest("hex");
const projection = {
  id: true,
  prefix: true,
  label: true,
  role: true,
  issuedById: true,
  expiresAt: true,
  usedAt: true,
  usedById: true,
  revokedAt: true,
  createdAt: true,
} as const;

@Controller("api")
export class RegistrationController {
  private attempts = new Map<string, { count: number; until: number }>();
  constructor(
    @Inject(Db) private db: Db,
    @Inject(JwtService) private jwt: JwtService,
  ) {}

  private limit(ip: string) {
    const now = Date.now();
    for (const [key, item] of this.attempts)
      if (item.until < now) this.attempts.delete(key);
    const item = this.attempts.get(ip) ?? { count: 0, until: now + 60_000 };
    if (++item.count > 20)
      throw new DomainError(
        "RATE_LIMITED",
        "尝试次数过多，请一分钟后重试",
        429,
      );
    this.attempts.set(ip, item);
  }
  private async available(code: string) {
    const record = await this.db.registrationCode.findUnique({
      where: { codeHash: digest(code) },
    });
    if (
      !record ||
      record.usedAt ||
      record.revokedAt ||
      record.expiresAt.getTime() <= Date.now()
    )
      throw new DomainError(
        "INVALID_REGISTRATION_CODE",
        "注册码无效、已使用或已过期，请联系管理员重新签发",
        400,
      );
    return record;
  }

  @Public() @Post("auth/registration/verify") async verify(
    @Body() body: unknown,
    @Req() req: FastifyRequest,
  ) {
    this.limit(req.ip);
    const { code } = parse(z.object({ code: codeSchema }).strict(), body);
    const record = await this.available(code);
    return {
      valid: true,
      expiresAt: record.expiresAt,
      role: record.role,
    };
  }

  @Public() @Post("auth/register") async register(
    @Body() body: unknown,
    @Req() req: FastifyRequest,
  ) {
    this.limit(req.ip);
    const dto = parse(
      z
        .object({
          code: codeSchema,
          name: z.string().trim().min(1).max(60),
          username: z
            .string()
            .trim()
            .regex(/^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,39}$/),
          password: z.string().min(8).max(100),
        })
        .strict(),
      body,
    );
    const invitation = await this.available(dto.code);
    const passwordHash = await hash(dto.password, 12);
    const user = await this.db.$transaction(async (tx) => {
      const claimed = await tx.registrationCode.updateMany({
        where: {
          id: invitation.id,
          usedAt: null,
          revokedAt: null,
          expiresAt: { gt: new Date() },
        },
        data: { usedAt: new Date() },
      });
      if (claimed.count !== 1)
        throw new DomainError(
          "INVALID_REGISTRATION_CODE",
          "注册码已失效，请联系管理员",
          400,
        );
      const created = await tx.user.create({
        data: {
          name: dto.name,
          username: dto.username,
          passwordHash,
          role: invitation.role,
        },
        select: { id: true, name: true, username: true, role: true },
      });
      await tx.registrationCode.update({
        where: { id: invitation.id },
        data: { usedById: created.id },
      });
      await tx.auditLog.create({
        data: {
          userId: created.id,
          action: "REGISTER",
          entityId: created.id,
          requestId: req.id,
          result: "SUCCESS",
          after: {
            name: created.name,
            role: created.role,
            registrationId: invitation.id,
          },
        },
      });
      return created;
    });
    return {
      token: await this.jwt.signAsync({ sub: user.id, sessionVersion: 0 }),
      user,
    };
  }

  @Roles("ADMIN") @Get("registration-codes") async list(
    @Query() query: unknown,
  ) {
    const q = parse(
      z.object({
        page: z.coerce.number().int().positive().default(1),
        pageSize: z.coerce.number().int().min(1).max(100).default(20),
        search: z.string().max(100).optional(),
      }),
      query,
    );
    const where = q.search ? { label: { contains: q.search } } : {};
    const [items, total] = await Promise.all([
      this.db.registrationCode.findMany({
        where,
        orderBy: { createdAt: "desc" },
        skip: (q.page - 1) * q.pageSize,
        take: q.pageSize,
        select: projection,
      }),
      this.db.registrationCode.count({ where }),
    ]);
    return { items, total, page: q.page, pageSize: q.pageSize };
  }

  @Roles("ADMIN") @Post("registration-codes") async issue(
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          label: z.string().trim().min(1).max(100),
          days: z.number().int().min(1).max(30).default(7),
          role: z.enum(codeRoles).default("OPERATOR"),
        })
        .strict(),
      body,
    );
    const code = `VSN-${randomBytes(18).toString("hex").toUpperCase().match(/.{6}/g)!.join("-")}`;
    const record = await this.db.registrationCode.create({
      data: {
        codeHash: digest(code),
        prefix: code.slice(0, 10),
        label: dto.label,
        role: dto.role,
        issuedById: req.actor.id,
        expiresAt: new Date(Date.now() + dto.days * 86400_000),
      },
      select: projection,
    });
    return { ...record, code };
  }

  @Roles("ADMIN") @Patch("registration-codes/:id/revoke") async revoke(
    @Param("id") id: string,
  ) {
    const result = await this.db.registrationCode.updateMany({
      where: { id, usedAt: null, revokedAt: null },
      data: { revokedAt: new Date() },
    });
    if (!result.count)
      throw new DomainError("INVALID_STATE", "该注册码已使用或已撤销");
    return { id, revoked: true };
  }
}
