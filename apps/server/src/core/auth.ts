import {
  Controller,
  Post,
  Get,
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
import { compare } from "bcryptjs";
import { z } from "zod";
import type { FastifyRequest } from "fastify";
import type { Role } from "@vision/contracts";
import { Db } from "./db.js";
import { parse, DomainError } from "./errors.js";
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
      const claims = await this.jwt.verifyAsync<{ sub: string }>(token);
      const user = await this.db.user.findUnique({ where: { id: claims.sub } });
      if (!user || user.disabled) throw new Error("disabled");
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
  ) {}
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
    const now = Date.now();
    for (const [ip, a] of this.attempts)
      if (a.until < now) this.attempts.delete(ip);
    const attempt = this.attempts.get(req.ip) ?? {
      count: 0,
      until: now + 60000,
    };
    if (attempt.count >= 20)
      throw new DomainError(
        "RATE_LIMITED",
        "Too many login attempts; retry in one minute",
        429,
      );
    attempt.count++;
    this.attempts.set(req.ip, attempt);
    const user = await this.db.user.findUnique({
      where: { username: dto.username },
    });
    if (
      !user ||
      user.disabled ||
      !(await compare(dto.password, user.passwordHash))
    )
      throw new UnauthorizedException("Invalid credentials");
    this.attempts.delete(req.ip);
    return {
      token: await this.jwt.signAsync({ sub: user.id }),
      user: { id: user.id, name: user.name, role: user.role },
    };
  }
  @Get("me") me(@Req() req: Request) {
    return req.actor;
  }
}
