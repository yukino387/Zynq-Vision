import {
  Controller,
  Post,
  Get,
  Patch,
  Body,
  Req,
  Injectable,
  Inject,
  SetMetadata,
  UnauthorizedException,
  ForbiddenException,
  type CanActivate,
  type ExecutionContext,
} from "@nestjs/common";
import { Reflector } from "@nestjs/core";
import { JwtService } from "@nestjs/jwt";
import { compare, hash } from "bcryptjs";
import { z } from "zod";
import type { FastifyRequest } from "fastify";
import type { Role } from "@vision/contracts";
import { Db } from "./db.js";
import { parse, DomainError } from "./errors.js";
import { Events } from "./events.js";
export const newPasswordSchema = z
  .string()
  .min(8)
  .max(72)
  .refine(
    (value) => Buffer.byteLength(value, "utf8") <= 72,
    "密码的 UTF-8 长度不能超过 72 字节",
  );
const profileFields = {
  id: true,
  name: true,
  username: true,
  role: true,
  createdAt: true,
} as const;
export interface Actor {
  id: string;
  name: string;
  role: Role;
}
export type Request = FastifyRequest & { actor: Actor };
export const Public = () => SetMetadata("public", true);
export const Roles = (...roles: Role[]) => SetMetadata("roles", roles);
@Injectable()
export class AuthGuard implements CanActivate {
  constructor(
    @Inject(Reflector) private reflector: Reflector,
    @Inject(JwtService) private jwt: JwtService,
    @Inject(Db) private db: Db,
  ) {}
  async canActivate(ctx: ExecutionContext) {
    if (
      this.reflector.getAllAndOverride("public", [
        ctx.getHandler(),
        ctx.getClass(),
      ])
    )
      return true;
    const req = ctx.switchToHttp().getRequest<Request>();
    const token = req.headers.authorization?.replace(/^Bearer /, "");
    if (!token) throw new UnauthorizedException();
    try {
      const claims = await this.jwt.verifyAsync<{
        sub: string;
        sessionVersion?: number;
      }>(token);
      const user = await this.db.user.findUnique({ where: { id: claims.sub } });
      if (
        !user ||
        user.disabled ||
        user.sessionVersion !== (claims.sessionVersion ?? 0)
      )
        throw new Error("Invalid session");
      req.actor = { id: user.id, name: user.name, role: user.role };
    } catch {
      throw new UnauthorizedException();
    }
    const roles = this.reflector.getAllAndOverride<Role[]>("roles", [
      ctx.getHandler(),
      ctx.getClass(),
    ]);
    if (roles && !roles.includes(req.actor.role))
      throw new ForbiddenException();
    return true;
  }
}
@Controller("api/auth")
export class AuthController {
  private attempts = new Map<string, { count: number; until: number }>();
  constructor(
    @Inject(Db) private db: Db,
    @Inject(JwtService) private jwt: JwtService,
    @Inject(Events) private events: Events,
  ) {}
  private limit(key: string) {
    const now = Date.now();
    for (const [stored, attempt] of this.attempts)
      if (attempt.until < now) this.attempts.delete(stored);
    const attempt = this.attempts.get(key) ?? { count: 0, until: now + 60000 };
    if (attempt.count >= 20)
      throw new DomainError(
        "RATE_LIMITED",
        "尝试次数过多，请一分钟后重试",
        429,
      );
    attempt.count++;
    this.attempts.set(key, attempt);
  }
  @Public() @Post("login") async login(
    @Body() body: unknown,
    @Req() req: FastifyRequest,
  ) {
    const dto = parse(
      z
        .object({
          username: z.string().min(1).max(80),
          password: z.string().min(1).max(200),
        })
        .strict(),
      body,
    );
    const attemptKey = `login:${req.ip}`;
    this.limit(attemptKey);
    const user = await this.db.user.findUnique({
      where: { username: dto.username },
    });
    if (
      !user ||
      user.disabled ||
      !(await compare(dto.password, user.passwordHash))
    )
      throw new UnauthorizedException("Invalid credentials");
    this.attempts.delete(attemptKey);
    return {
      token: await this.jwt.signAsync({
        sub: user.id,
        sessionVersion: user.sessionVersion,
      }),
      user: { id: user.id, name: user.name, role: user.role },
    };
  }
  @Get("me") me(@Req() req: Request) {
    return req.actor;
  }
  @Get("profile") profile(@Req() req: Request) {
    return this.db.user.findUniqueOrThrow({
      where: { id: req.actor.id },
      select: profileFields,
    });
  }
  @Patch("profile") async updateProfile(
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z.object({ name: z.string().trim().min(1).max(60) }).strict(),
      body,
    );
    return this.db.$transaction(async (tx) => {
      const user = await tx.user.update({
        where: { id: req.actor.id },
        data: dto,
        select: profileFields,
      });
      await tx.auditLog.create({
        data: {
          userId: req.actor.id,
          action: "UPDATE_PROFILE",
          entityId: req.actor.id,
          requestId: req.id,
          result: "SUCCESS",
          after: { name: user.name },
        },
      });
      return user;
    });
  }
  @Post("password") async changePassword(
    @Body() body: unknown,
    @Req() req: Request,
  ) {
    const dto = parse(
      z
        .object({
          currentPassword: z.string().min(1).max(200),
          newPassword: newPasswordSchema,
        })
        .strict(),
      body,
    );
    const attemptKey = `password:${req.actor.id}`;
    this.limit(attemptKey);
    const user = await this.db.user.findUniqueOrThrow({
      where: { id: req.actor.id },
    });
    if (!(await compare(dto.currentPassword, user.passwordHash)))
      throw new DomainError(
        "PASSWORD_INCORRECT",
        "当前密码不正确，请重新输入",
        400,
      );
    if (await compare(dto.newPassword, user.passwordHash))
      throw new DomainError(
        "PASSWORD_UNCHANGED",
        "新密码不能与当前密码相同",
        400,
      );
    const passwordHash = await hash(dto.newPassword, 12);
    await this.db.$transaction(async (tx) => {
      const changed = await tx.user.updateMany({
        where: {
          id: user.id,
          passwordHash: user.passwordHash,
          disabled: false,
        },
        data: { passwordHash, sessionVersion: { increment: 1 } },
      });
      if (!changed.count)
        throw new DomainError(
          "PASSWORD_CHANGED",
          "账号状态已变化，请重新登录后再修改密码",
          409,
        );
      await tx.auditLog.create({
        data: {
          userId: user.id,
          action: "CHANGE_PASSWORD",
          entityId: user.id,
          requestId: req.id,
          result: "SUCCESS",
        },
      });
    });
    this.attempts.delete(attemptKey);
    this.events.closeUser(user.id, "Password changed");
    return { changed: true };
  }
}
