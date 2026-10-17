import {
  Injectable,
  Inject,
  type OnModuleInit,
  type OnModuleDestroy,
} from "@nestjs/common";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { TrainingService } from "../models/training.service.js";
import { ModelsService } from "../models/models.service.js";
import { DevicesService } from "../devices/devices.service.js";
import { CommandsService } from "../devices/commands.service.js";
import { Prisma } from "@prisma/client";
import { FileJobsService } from "../datasets/file-jobs.service.js";
@Injectable()
export class JobsService implements OnModuleInit, OnModuleDestroy {
  private timer: ReturnType<typeof setInterval> | null = null;
  private current: Promise<void> | null = null;
  private stopping = false;
  constructor(
    @Inject(Db) private db: Db,
    @Inject(Events) private events: Events,
    @Inject(TrainingService) private training: TrainingService,
    @Inject(ModelsService) private models: ModelsService,
    @Inject(DevicesService) private devices: DevicesService,
    @Inject(CommandsService) private commands: CommandsService,
    @Inject(FileJobsService) private fileJobs: FileJobsService,
  ) {}
  async onModuleInit() {
    const interrupted = await this.db.job.findMany({
      where: { status: "RUNNING" },
    });
    for (const job of interrupted) {
      await this.fail(
        job,
        "Server restarted during job; verify device before retry",
      );
    }
    this.timer = setInterval(() => {
      if (!this.current && !this.stopping) {
        this.current = this.tick()
          .catch((error) =>
            console.error(
              JSON.stringify({
                timestamp: new Date().toISOString(),
                level: "error",
                module: "jobs",
                message: String(error),
              }),
            ),
          )
          .finally(() => {
            this.current = null;
          });
      }
    }, 250);
  }
  private async fail(
    job: { id: string; entityId: string; type: string },
    error: string,
  ) {
    if (
      job.type === "TRAINING" &&
      (await this.db.trainingJob.findUnique({ where: { id: job.entityId } }))
        ?.status === "CANCELLED"
    ) {
      await this.db.job.update({
        where: { id: job.id },
        data: { status: "CANCELLED", completedAt: new Date() },
      });
      return;
    }
    await this.db.job.update({
      where: { id: job.id },
      data: { status: "FAILED", error, completedAt: new Date() },
    });
    if (job.type === "TRAINING")
      await this.db.trainingJob.update({
        where: { id: job.entityId },
        data: { status: "FAILED", error },
      });
    if (job.type === "DEPLOYMENT")
      await this.db.deployment.update({
        where: { id: job.entityId },
        data: { status: "FAILED", error },
      });
    if (job.type === "SYNC")
      await this.db.syncJob.update({
        where: { id: job.entityId },
        data: { status: "FAILED", error, completedAt: new Date() },
      });
    this.events.emit("job.failed", job.entityId, { error });
  }
  private async tick() {
    const job = await this.db.job.findFirst({
      where: { status: "QUEUED" },
      orderBy: { createdAt: "asc" },
    });
    if (!job) return;
    const claim = await this.db.job.updateMany({
      where: { id: job.id, status: "QUEUED" },
      data: {
        status: "RUNNING",
        attempts: { increment: 1 },
        startedAt: new Date(),
      },
    });
    if (!claim.count) return;
    try {
      let output: Prisma.InputJsonValue | undefined;
      if (job.type === "TRAINING")
        await this.training.run(job.entityId, job.payload, () => this.stopping);
      else if (job.type === "DEPLOYMENT") await this.deploy(job.entityId);
      else
        output = await this.fileJobs.process(
          job.type,
          job.entityId,
          job.payload,
        );
      const cancelled =
        job.type === "TRAINING" &&
        (
          await this.db.trainingJob.findUniqueOrThrow({
            where: { id: job.entityId },
          })
        ).status === "CANCELLED";
      await this.db.job.update({
        where: { id: job.id },
        data: {
          status: cancelled ? "CANCELLED" : "COMPLETED",
          completedAt: new Date(),
          ...(output === undefined
            ? {}
            : {
                payload: {
                  input: job.payload,
                  output,
                } as Prisma.InputJsonValue,
              }),
        },
      });
      this.events.emit("job.completed", job.entityId, {
        id: job.id,
        type: job.type,
        status: cancelled ? "CANCELLED" : "COMPLETED",
        output,
      });
    } catch (error) {
      await this.fail(job, String(error));
    }
  }
  private async deploy(id: string) {
    const deployment = await this.db.deployment.findUniqueOrThrow({
      where: { id },
    });
    await this.commands.run(
      deployment.deviceId,
      "DEPLOY_MODEL",
      id,
      async () => {
        const { model, manifest, weights, transport } = await this.models.check(
          deployment.modelId,
          deployment.deviceId,
        );
        const receipt = await transport.deployModel(
          model.version,
          manifest,
          weights,
          async (stage) => {
            const status = stage as
              | "DOWNLOADING"
              | "VERIFYING"
              | "VERIFIED"
              | "ACTIVATING"
              | "SELF_TEST";
            const progress = {
              DOWNLOADING: 15,
              VERIFYING: 35,
              VERIFIED: 50,
              ACTIVATING: 70,
              SELF_TEST: 85,
            }[status];
            await this.db.deployment.update({
              where: { id },
              data: { status, progress },
            });
            this.events.emit(
              "deployment.progress",
              id,
              { status, progress },
              deployment.source,
            );
          },
        );
        if (
          // 模型已经躺在设备 SD 卡上时只做切换，没有传输阶段。
          (!receipt.downloaded && !receipt.resident) ||
          !receipt.verified ||
          !receipt.loaded ||
          !receipt.selfTest ||
          !receipt.active ||
          receipt.sha256 !== manifest.weights.sha256 ||
          transport.getCurrentModel() !== model.version
        )
          throw new Error("Device did not confirm all deployment stages");
        await this.db.$transaction([
          this.db.deployment.updateMany({
            where: {
              deviceId: deployment.deviceId,
              id: { not: id },
              status: "ACTIVE",
            },
            data: { status: "SUPERSEDED" },
          }),
          this.db.deployment.update({
            where: { id },
            data: {
              status: "ACTIVE",
              progress: 100,
              receipt: {
                ...(deployment.receipt as Prisma.JsonObject),
                ...receipt,
              } as unknown as Prisma.InputJsonValue,
            },
          }),
          this.db.device.update({
            where: { id: deployment.deviceId },
            data: {
              reportedState:
                transport.getCurrentConfig() as Prisma.InputJsonValue,
            },
          }),
        ]);
        this.events.emit(
          "deployment.completed",
          id,
          { status: "ACTIVE", receipt },
          deployment.source,
        );
      },
    );
  }
  async onModuleDestroy() {
    this.stopping = true;
    if (this.timer) clearInterval(this.timer);
    await this.current;
  }
}
