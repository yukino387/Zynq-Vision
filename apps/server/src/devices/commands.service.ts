import { Injectable, Inject } from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { Db } from "../core/db.js";
import { DomainError } from "../core/errors.js";
import { DevicesService } from "./devices.service.js";
@Injectable()
export class CommandsService {
  private tails = new Map<string, Promise<unknown>>();
  private sizes = new Map<string, number>();
  constructor(
    @Inject(Db) private db: Db,
    @Inject(DevicesService) private devices: DevicesService,
  ) {}
  async run<T>(
    deviceId: string,
    type: string,
    requestId: string,
    action: () => Promise<T>,
  ): Promise<T> {
    const size = this.sizes.get(deviceId) ?? 0;
    if (size >= 8)
      throw new DomainError(
        "QUEUE_OVERFLOW",
        "Device command queue is full",
        429,
      );
    this.sizes.set(deviceId, size + 1);
    const ready = this.db.command.create({
      data: { deviceId, type, requestId },
    });
    void ready.catch(() => undefined);
    const previous = this.tails.get(deviceId) ?? Promise.resolve();
    const next = previous
      .catch(() => undefined)
      .then(async () => {
        let id: string | null = null;
        try {
          const command = await ready;
          id = command.id;
          const claim = await this.db.command.updateMany({
            where: { id, status: "QUEUED" },
            data: { status: "RUNNING", attempts: 1 },
          });
          if (!claim.count)
            throw new DomainError(
              "COMMAND_CANCELLED",
              "Queued command was cancelled",
            );
          let result: T | undefined;
          for (
            let attempt = 1;
            attempt <= (type === "GET_STATUS" ? 2 : 1);
            attempt++
          ) {
            await this.db.command.update({
              where: { id },
              data: { status: "RUNNING", attempts: attempt },
            });
            try {
              result = await action();
              break;
            } catch (error) {
              if (
                !(error instanceof DomainError) ||
                type !== "GET_STATUS" ||
                attempt === 2 ||
                error.getStatus() !== 504
              )
                throw error;
            }
          }
          await this.db.command.update({
            where: { id },
            data: {
              status: "COMPLETED",
              completedAt: new Date(),
              result:
                result === undefined
                  ? Prisma.JsonNull
                  : (JSON.parse(
                      JSON.stringify(
                        type === "CAPTURE" ? { captured: true } : result,
                      ),
                    ) as Prisma.InputJsonValue),
            },
          });
          await this.devices.persist();
          return result as T;
        } catch (error) {
          if (id)
            await this.db.command.updateMany({
              where: { id, status: { not: "CANCELLED" } },
              data: {
                status: "FAILED",
                error: String(error),
                completedAt: new Date(),
              },
            });
          throw error;
        } finally {
          this.sizes.set(deviceId, (this.sizes.get(deviceId) ?? 1) - 1);
        }
      });
    this.tails.set(deviceId, next);
    try {
      return await next;
    } finally {
      if (this.tails.get(deviceId) === next) this.tails.delete(deviceId);
    }
  }
}
