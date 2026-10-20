import { Prisma, type Device } from "@prisma/client";
import type { Db } from "../core/db.js";
import type { AssetsService } from "../assets/assets.service.js";
import { DomainError } from "../core/errors.js";
import { batchModel } from "../inspections/batch-package.js";
import { terminalStatus } from "../devices/terminal-state.js";
import { terminalRequest } from "../devices/terminal-client.js";
import type { CommandsService } from "../devices/commands.service.js";
import { FIRMWARE_BUSY_STATES } from "../firmware/firmware.service.js";

export async function deployTerminalModel(
  db: Db,
  assets: AssetsService,
  commands: CommandsService,
  device: Device,
  modelId: string,
  actor: string,
  authorization: string,
  requestId: string,
  confirm: boolean,
) {
  const status = await terminalStatus(db, device);
  if (!status.online)
    throw new DomainError("UNAVAILABLE", "设备未连接，请等待设备上线", 409);
  const artifact = await batchModel(db, assets, modelId);
  if (artifact.model.status !== "APPROVED")
    throw new DomainError("INVALID_STATE", "请先确认模型可用于生产", 409);
  const state = status.state;
  if (state?.production && !confirm)
    throw new DomainError(
      "DEVICE_BUSY",
      "请先停止自动检测并确认当前件已处理，再下发模型",
      409,
    );
  if (
    state?.model &&
    state.model.id === artifact.model.id &&
    state.model.payloadSha256 === artifact.payloadSha256
  )
    throw new DomainError("INVALID_STATE", "该模型已在设备上运行", 409);
  if (
    state?.product &&
    state.product.id &&
    !confirm &&
    JSON.stringify(state.model?.classes ?? []) !==
      JSON.stringify(artifact.manifest.classes)
  )
    throw new DomainError(
      "MODEL_INCOMPATIBLE",
      "新模型类别与当前产品不一致；请确认将停止生产并重新分配产品",
      409,
    );
  if (
    await db.firmwareDeployment.count({
      where: { deviceId: device.id, status: { in: FIRMWARE_BUSY_STATES } },
    })
  )
    throw new DomainError(
      "DEVICE_BUSY",
      "设备正在更新固件，请稍后下发模型",
      409,
    );
  if (
    await db.deployment.count({
      where: {
        deviceId: device.id,
        status: { in: ["DOWNLOADING", "VERIFYING", "ROLLBACK"] },
      },
    })
  )
    throw new DomainError("DEVICE_BUSY", "已有模型正在下发，请等待完成", 409);

  const previousVersion = state?.model?.version ?? null;
  const previousPayloadSha256 = state?.model?.payloadSha256 ?? null;
  const deployment = await db.deployment.create({
    data: {
      deviceId: device.id,
      modelId,
      name: artifact.model.version,
      source: "BOARD",
      previousVersion,
      status: "DOWNLOADING",
      progress: 10,
      receipt: {
        previousVersion,
        previousPayloadSha256,
        previousModelId: state?.model?.id ?? null,
        modelId: artifact.model.id,
        modelVersion: artifact.model.version,
        modelPayloadSha256: artifact.payloadSha256,
      },
    },
  });
  try {
    const installed = (await commands.run(
      device.id,
      "DEPLOY_MODEL",
      requestId,
      async () =>
        (
          await terminalRequest(
            device,
            "/runtime/model",
            authorization,
            {
              modelId: artifact.model.id,
              modelVersion: artifact.model.version,
              modelPayloadSha256: artifact.payloadSha256,
              weightsSha256: artifact.manifest.weights.sha256,
              manifest: artifact.manifest,
              classes: artifact.manifest.classes,
              confirm,
            },
            60000,
          )
        ).json(),
    )) as { model?: { version?: string }; product?: unknown };
    const receipt = deployment.receipt as Prisma.JsonObject;
    const active = await db.$transaction(async (tx) => {
      await tx.deployment.updateMany({
        where: {
          deviceId: device.id,
          id: { not: deployment.id },
          status: "ACTIVE",
        },
        data: { status: "SUPERSEDED" },
      });
      return tx.deployment.update({
        where: { id: deployment.id },
        data: {
          status: "ACTIVE",
          progress: 100,
          receipt: {
            ...receipt,
            modelVersion: installed.model?.version ?? artifact.model.version,
            verified: true,
            loaded: true,
            active: true,
            productCleared: installed.product === null,
            confirmedAt: new Date().toISOString(),
          },
        },
      });
    });
    return { deployment: active, state: installed };
  } catch (error) {
    if (
      error instanceof DomainError &&
      (error.getStatus() === 503 || error.getStatus() === 504)
    )
      return { deployment, state: undefined };
    await db.deployment.update({
      where: { id: deployment.id },
      data: { status: "FAILED", error: String(error) },
    });
    throw error;
  }
}
