import "reflect-metadata";
import { LogController } from "fastify";
import { NestFactory } from "@nestjs/core";
import {
  FastifyAdapter,
  type NestFastifyApplication,
} from "@nestjs/platform-fastify";
import multipart from "@fastify/multipart";
import fastifyStatic from "@fastify/static";
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { AppModule } from "./app.js";
import { Errors } from "./core/errors.js";
import { Events } from "./core/events.js";
import { root } from "./config.js";
export async function createApp(logging = true) {
  const adapter = new FastifyAdapter({
    logger: logging
      ? {
          level: "info",
          messageKey: "message",
          timestamp: () => `,"timestamp":"${new Date().toISOString()}"`,
          formatters: {
            level: (label: string) => ({ level: label }),
            bindings: () => ({ module: "http" }),
          },
          redact: ["req.headers.authorization"],
        }
      : false,
    logController: new LogController({ disableRequestLogging: true }),
    bodyLimit: 1024 * 1024,
    genReqId: () => randomUUID(),
    requestIdHeader: false,
  });
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    adapter,
    { logger: false },
  );
  app.useGlobalFilters(new Errors());
  await app.register(multipart, {
    limits: { fileSize: 20 * 1024 * 1024, files: 1, fields: 2, parts: 3 },
  });
  const server = app.getHttpAdapter().getInstance();
  server.addHook("onResponse", async (req, reply) => {
    req.log.info(
      {
        requestId: req.id,
        entityId: req.routeOptions.url ?? req.url,
        statusCode: reply.statusCode,
      },
      "HTTP request completed",
    );
  });
  server.addHook("onSend", async (req, reply, payload) => {
    reply.header("X-Request-Id", req.id);
    reply.header("X-Content-Type-Options", "nosniff");
    return payload;
  });
  const web = resolve(root, "apps/web/dist"),
    mobile = resolve(root, "apps/mobile/dist/build/h5");
  if (existsSync(web))
    await app.register(fastifyStatic, {
      root: web,
      prefix: "/",
    });
  if (existsSync(mobile))
    await app.register(fastifyStatic, {
      root: mobile,
      prefix: "/mobile/",
      decorateReply: false,
    });
  app.get(Events).attach(app.getHttpServer());
  app.enableShutdownHooks();
  await app.init();
  await app.getHttpAdapter().getInstance().ready();
  return app;
}
