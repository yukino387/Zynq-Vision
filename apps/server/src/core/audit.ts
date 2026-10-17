import {
  Injectable,
  Inject,
  type NestInterceptor,
  type ExecutionContext,
  type CallHandler,
} from "@nestjs/common";
import { from, type Observable, concatMap, catchError, throwError } from "rxjs";
import { Prisma } from "@prisma/client";
import { Db } from "./db.js";
import type { Request } from "./auth.js";
function summary(value: unknown): Prisma.InputJsonValue {
  if (!value || typeof value !== "object") return {};
  const object = value as Record<string, unknown>;
  const keys = [
    "id",
    "name",
    "status",
    "role",
    "source",
    "version",
    "modelId",
    "deviceId",
    "sampleId",
    "result",
    "hard",
    "disabled",
    "desiredState",
    "reportedState",
    "checksum",
    "deletedAt",
  ];
  return JSON.parse(
    JSON.stringify(
      Object.fromEntries(
        keys.filter((k) => object[k] !== undefined).map((k) => [k, object[k]]),
      ),
    ),
  ) as Prisma.InputJsonValue;
}
@Injectable()
export class Audit implements NestInterceptor {
  constructor(@Inject(Db) private db: Db) {}
  async intercept(
    ctx: ExecutionContext,
    next: CallHandler,
  ): Promise<Observable<unknown>> {
    const req = ctx.switchToHttp().getRequest<Request>();
    if (
      ["GET", "HEAD", "OPTIONS"].includes(req.method) ||
      req.url.startsWith("/api/auth")
    )
      return next.handle();
    const id = (req.params as Record<string, string>)?.id;
    let before: Prisma.InputJsonValue = {};
    if (id) {
      if (req.url.startsWith("/api/devices/"))
        before = summary(await this.db.device.findUnique({ where: { id } }));
      else if (req.url.startsWith("/api/datasets/"))
        before = summary(await this.db.dataset.findUnique({ where: { id } }));
      else if (req.url.startsWith("/api/samples/"))
        before = summary(await this.db.sample.findUnique({ where: { id } }));
      else if (req.url.startsWith("/api/users/"))
        before = summary(
          await this.db.user.findUnique({
            where: { id },
            select: { id: true, role: true, disabled: true },
          }),
        );
      else if (req.url.startsWith("/api/deployments/"))
        before = summary(
          await this.db.deployment.findUnique({ where: { id } }),
        );
    }
    const record = async (result: string, value: unknown) => {
      await this.db.auditLog.create({
        data: {
          userId: req.actor?.id,
          action: `${req.method} ${req.routeOptions.url ?? req.url}`,
          entityId:
            id ??
            (value && typeof value === "object" && "id" in value
              ? String(value.id)
              : req.url),
          requestId: req.id,
          result,
          before,
          after: summary(value),
        },
      });
    };
    return next.handle().pipe(
      concatMap((value) => from(record("SUCCESS", value).then(() => value))),
      catchError((error: unknown) =>
        from(record("FAILED", null)).pipe(
          concatMap(() => throwError(() => error)),
        ),
      ),
    );
  }
}
