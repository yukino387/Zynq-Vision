import {
  Catch,
  HttpException,
  type ExceptionFilter,
  type ArgumentsHost,
} from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { ZodError, type ZodTypeAny, type output } from "zod";
import type { FastifyRequest, FastifyReply } from "fastify";
export class DomainError extends HttpException {
  constructor(
    code: string,
    message: string,
    status = 409,
    details: unknown = null,
  ) {
    super({ code, message, details }, status);
  }
}
export function parse<T extends ZodTypeAny>(
  schema: T,
  value: unknown,
): output<T> {
  return schema.parse(value) as output<T>;
}
@Catch()
export class Errors implements ExceptionFilter {
  catch(error: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp(),
      req = ctx.getRequest<FastifyRequest>(),
      reply = ctx.getResponse<FastifyReply>();
    let status = 500,
      code = "INTERNAL_ERROR",
      message = "Internal server error",
      details: unknown = null;
    if (error instanceof SyntaxError) {
      status = 400;
      code = "VALIDATION_ERROR";
      message = "Invalid JSON";
    } else if (error instanceof ZodError) {
      status = 400;
      code = "VALIDATION_ERROR";
      message = "Invalid request";
      details = error.flatten();
    } else if (error instanceof HttpException) {
      status = error.getStatus();
      const data = error.getResponse();
      if (typeof data === "object" && data) {
        const e = data as Record<string, unknown>;
        code = String(
          e.code ??
            (status === 401
              ? "UNAUTHORIZED"
              : status === 403
                ? "FORBIDDEN"
                : "REQUEST_ERROR"),
        );
        message = String(e.message ?? error.message);
        details = e.details ?? null;
      }
    } else if (error instanceof Prisma.PrismaClientKnownRequestError) {
      status = error.code === "P2025" ? 404 : 409;
      code = error.code === "P2025" ? "NOT_FOUND" : "CONSTRAINT_VIOLATION";
      message = "Database constraint rejected the operation";
    }
    if (status === 500)
      console.error(
        JSON.stringify({
          timestamp: new Date().toISOString(),
          level: "error",
          module: "http",
          message: error instanceof Error ? error.message : String(error),
          requestId: req.id,
          entityId: req.url,
        }),
      );
    void reply.code(status).send({ code, message, requestId: req.id, details });
  }
}
