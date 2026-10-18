import { Inject, Injectable } from "@nestjs/common";
import { Prisma, type DeploymentStatus } from "@prisma/client";
import type { FirmwareInfo } from "@vision/contracts";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { DomainError } from "../core/errors.js";
import { AssetsService } from "../assets/assets.service.js";
import { DevicesService } from "../devices/devices.service.js";
import { CommandsService } from "../devices/commands.service.js";
import type { FirmwareStage } from "../devices/transport.js";
import { validateFirmwarePackage } from "./package.js";

/** 这些状态说明设备上已有一次固件更新在排队或执行。 */
export const FIRMWARE_BUSY_STATES = [
  "APPROVED",
  "DOWNLOADING",
  "VERIFYING",
  "VERIFIED",
  "WRITING",
  "REBOOTING",
  "SELF_TEST",
  "ROLLBACK",
];
const MODEL_BUSY_STATES: DeploymentStatus[] = [
  "APPROVED",
  "DOWNLOADING",
  "VERIFYING",
  "VERIFIED",
  "ACTIVATING",
  "SELF_TEST",
  "ROLLBACK",
];
const STAGE_PROGRESS: Record<FirmwareStage, number> = {
  DOWNLOADING: 15,
  VERIFYING: 35,
  VERIFIED: 50,
  WRITING: 65,
  REBOOTING: 80,
  SELF_TEST: 90,
};

@Injectable()
export class FirmwareService {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(Events) private events: Events,
    @Inject(AssetsService) private assets: AssetsService,
    @Inject(DevicesService) private devices: DevicesService,
    @Inject(CommandsService) private commands: CommandsService,
  ) {}

  async info(deviceId: string): Promise<FirmwareInfo> {
    return this.devices.transport(deviceId).getFirmwareInfo();
  }

  async createDeployment(firmwareId: string, deviceId: string) {
    const firmware = await this.db.firmware.findUniqueOrThrow({
      where: { id: firmwareId },
      include: { asset: true },
    });
    const transport = this.devices.transport(deviceId);
    const info = await transport.getFirmwareInfo();
    if (!info.supported)
      throw new DomainError(
        "NO_CAPABILITY",
        "设备固件不支持 PS 应用 OTA",
        422,
      );
    if (info.pendingSlot !== 0xffffffff)
      throw new DomainError(
        "DEVICE_BUSY",
        "设备上有待确认的固件试运行",
        409,
      );
    if (info.version === firmware.version && info.sha256 === firmware.sha256)
      throw new DomainError(
        "INVALID_STATE",
        "设备已经在运行这个固件版本",
        409,
      );
    return this.db.$transaction(async (tx) => {
      const firmwareBusy = await tx.firmwareDeployment.count({
        where: { deviceId, status: { in: FIRMWARE_BUSY_STATES } },
      });
      if (firmwareBusy)
        throw new DomainError(
          "DEVICE_BUSY",
          "该设备已有固件更新在排队或执行",
          409,
        );
      const modelBusy = await tx.deployment.count({
        where: { deviceId, status: { in: MODEL_BUSY_STATES } },
      });
      if (modelBusy)
        throw new DomainError(
          "DEVICE_BUSY",
          "该设备正在部署模型，请完成后再更新固件",
          409,
        );
      const deployment = await tx.firmwareDeployment.create({
        data: {
          deviceId,
          firmwareId,
          previousVersion: info.version,
          previousSha256: info.sha256,
          previousSlot: info.runningSlot,
          receipt: {
            previousSlot: info.runningSlot,
            previousAttempts: info.attempts,
          },
        },
      });
      await tx.job.create({
        data: { type: "FIRMWARE_UPDATE", entityId: deployment.id, payload: {} },
      });
      this.events.emit("firmware.progress", deployment.id, {
        status: "APPROVED",
        progress: 0,
        deviceId,
        version: firmware.version,
      });
      return deployment;
    });
  }

  async run(id: string) {
    const deployment = await this.db.firmwareDeployment.findUniqueOrThrow({
      where: { id },
      include: { firmware: { include: { asset: true } } },
    });
    const firmware = deployment.firmware,
      data = await this.assets.read(firmware.asset.storageKey),
      packageValue = validateFirmwarePackage(data);
    if (
      packageValue.version !== firmware.version ||
      packageValue.sha256 !== firmware.sha256 ||
      packageValue.size !== firmware.size
    )
      throw new DomainError(
        "CHECKSUM_ERROR",
        "Stored firmware package no longer matches its registry entry",
        422,
      );
    await this.commands.run(
      deployment.deviceId,
      "UPDATE_FIRMWARE",
      deployment.id,
      async () => {
        const transport = this.devices.transport(deployment.deviceId);
        try {
          const receipt = await transport.deployFirmware(
            firmware.version,
            firmware.sha256,
            data,
            async (stage) => {
              const progress = STAGE_PROGRESS[stage];
              await this.db.firmwareDeployment.update({
                where: { id },
                data: { status: stage, progress },
              });
              this.events.emit("firmware.progress", id, {
                deploymentId: id,
                deviceId: deployment.deviceId,
                status: stage,
                progress,
              });
            },
          );
          if (
            receipt.version !== firmware.version ||
            (firmware.sha256 && receipt.sha256 !== firmware.sha256) ||
            !receipt.confirmed ||
            receipt.golden ||
            receipt.runningSlot !== receipt.activeSlot
          )
            throw new Error("Device did not confirm the new firmware");
          await this.db.$transaction([
            this.db.firmwareDeployment.updateMany({
              where: {
                deviceId: deployment.deviceId,
                id: { not: id },
                status: "ACTIVE",
              },
              data: { status: "SUPERSEDED" },
            }),
            this.db.firmwareDeployment.update({
              where: { id },
              data: {
                status: "ACTIVE",
                progress: 100,
                error: null,
                receipt: {
                  ...(deployment.receipt as Prisma.JsonObject),
                  ...receipt,
                } as unknown as Prisma.InputJsonValue,
              },
            }),
            this.db.device.update({
              where: { id: deployment.deviceId },
              data: {
                firmwareVersion: receipt.version,
                reportedState:
                  transport.getCurrentConfig() as Prisma.InputJsonValue,
              },
            }),
          ]);
          this.events.emit("firmware.completed", id, {
            deploymentId: id,
            deviceId: deployment.deviceId,
            version: receipt.version,
            runningSlot: receipt.runningSlot,
          });
        } catch (error) {
          await this.db.firmwareDeployment.update({
            where: { id },
            data: { status: "FAILED", error: String(error) },
          });
          this.events.emit("firmware.failed", id, {
            deploymentId: id,
            deviceId: deployment.deviceId,
            error: String(error),
          });
          throw error;
        }
      },
    );
  }

  async rollback(id: string, target: "PREVIOUS" | "GOLDEN") {
    const deployment = await this.db.firmwareDeployment.findUniqueOrThrow({
      where: { id },
      include: { firmware: true },
    });
    if (!["ACTIVE", "FAILED"].includes(deployment.status))
      throw new DomainError(
        "INVALID_STATE",
        "只有已生效或失败的固件更新可以回滚",
        409,
      );
    if (target === "PREVIOUS" && !deployment.previousVersion)
      throw new DomainError(
        "INVALID_STATE",
        "没有可回滚的上一版固件，请回滚到 golden",
        409,
      );
    return this.commands.run(
      deployment.deviceId,
      "ROLLBACK_FIRMWARE",
      deployment.id,
      async () => {
        const transport = this.devices.transport(deployment.deviceId);
        await this.db.firmwareDeployment.update({
          where: { id },
          data: { status: "ROLLBACK", progress: 50, error: null },
        });
        this.events.emit("firmware.progress", id, {
          deploymentId: id,
          deviceId: deployment.deviceId,
          status: "ROLLBACK",
          progress: 50,
        });
        try {
          const receipt = await transport.rollbackFirmware(target);
          if (
            !receipt.confirmed ||
            (target === "PREVIOUS" &&
              receipt.version !== deployment.previousVersion) ||
            (target === "GOLDEN" && !receipt.golden)
          )
            throw new Error("Device did not confirm the firmware rollback");
          const previousFirmware = await this.db.firmware.findUnique({
            where: { version: receipt.version },
          });
          const [result] = await this.db.$transaction([
            this.db.firmwareDeployment.updateMany({
              where: {
                deviceId: deployment.deviceId,
                status: "ACTIVE",
                id: { not: id },
              },
              data: { status: "SUPERSEDED" },
            }),
            ...(previousFirmware
              ? [
                  this.db.firmwareDeployment.updateMany({
                    where: {
                      deviceId: deployment.deviceId,
                      firmwareId: previousFirmware.id,
                      status: "SUPERSEDED",
                    },
                    data: { status: "ACTIVE" },
                  }),
                ]
              : []),
            this.db.firmwareDeployment.update({
              where: { id },
              data: {
                status: "ROLLED_BACK",
                progress: 100,
                receipt: {
                  ...(deployment.receipt as Prisma.JsonObject),
                  rollback: receipt as unknown as Prisma.InputJsonValue,
                } as unknown as Prisma.InputJsonValue,
              },
            }),
            this.db.device.update({
              where: { id: deployment.deviceId },
              data: {
                firmwareVersion: receipt.version,
                reportedState:
                  transport.getCurrentConfig() as Prisma.InputJsonValue,
              },
            }),
          ]);
          this.events.emit("firmware.rolledback", id, {
            deploymentId: id,
            deviceId: deployment.deviceId,
            version: receipt.version,
            target,
          });
          return result;
        } catch (error) {
          await this.db.firmwareDeployment.update({
            where: { id },
            data: { status: "FAILED", error: String(error) },
          });
          this.events.emit("firmware.failed", id, {
            deploymentId: id,
            deviceId: deployment.deviceId,
            error: String(error),
          });
          throw error;
        }
      },
    );
  }
}
