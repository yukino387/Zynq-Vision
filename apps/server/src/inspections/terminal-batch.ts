import { Prisma, type Device } from "@prisma/client";
import {
  planRulesSchema,
  type AcceptancePolicy,
  type BatchSnapshot,
  type TerminalStatus,
} from "@vision/contracts";
import type { Db } from "../core/db.js";
import type { Events } from "../core/events.js";
import type { AssetsService } from "../assets/assets.service.js";
import { DomainError } from "../core/errors.js";
import { batchModel } from "./batch-package.js";
import { productClassesMatch } from "@vision/shared";

type TerminalState = NonNullable<TerminalStatus["state"]>;

async function ensureTask(db: Db, planId: string, planName: string) {
  const open = await db.task.findFirst({
    where: { planId, status: "OPEN" },
    orderBy: { createdAt: "desc" },
  });
  if (open) return open.id;
  const created = await db.task.create({
    data: {
      name: planName,
      planId,
      target: 10000000,
      requirements: { automatic: true },
    },
  });
  return created.id;
}

export async function buildAssignmentSnapshot(
  db: Db,
  assets: AssetsService,
  modelId: string,
  planId: string,
  acceptance: AcceptancePolicy,
): Promise<BatchSnapshot> {
  const artifact = await batchModel(db, assets, modelId);
  if (artifact.model.status !== "APPROVED")
    throw new DomainError("INVALID_STATE", "请先确认模型可用于生产", 409);
  const plan = await db.inspectionPlan.findUniqueOrThrow({
    where: { id: planId },
  });
  const rules = planRulesSchema.parse(plan.rules);
  if (!productClassesMatch(rules.classes, artifact.manifest.classes))
    throw new DomainError(
      "MODEL_INCOMPATIBLE",
      "产品类别及顺序必须与设备当前模型一致",
      422,
    );
  return {
    formatVersion: 1,
    planId: plan.id,
    planName: plan.name,
    planVersion: plan.version,
    rules,
    acceptance,
    modelId: artifact.model.id,
    modelVersion: artifact.model.version,
    modelClasses: artifact.manifest.classes,
    modelPayloadSha256: artifact.payloadSha256,
  };
}

async function closeOpenBatches(db: Db, events: Events, deviceId: string) {
  const open = await db.inspectionBatch.findMany({
    where: { deviceId, status: "OPEN" },
  });
  for (const batch of open) {
    const closed = await db.inspectionBatch.update({
      where: { id: batch.id },
      data: { status: "CLOSED", closedAt: new Date() },
    });
    events.emit("batch.closed", closed.id, closed, "SERVER");
  }
}

export async function reconcileProductionBatch(
  db: Db,
  events: Events,
  assets: AssetsService,
  device: Device,
  state: TerminalState | null,
) {
  if (!state) return null;
  if (state.production && state.productionRunId) {
    if (!state.model || !state.product) return null;
    const existing = await db.inspectionBatch.findUnique({
      where: {
        deviceId_productionRunId: {
          deviceId: device.id,
          productionRunId: state.productionRunId,
        },
      },
    });
    if (existing) {
      if (existing.status === "OPEN") return existing;
      const reopened = await db.inspectionBatch.update({
        where: { id: existing.id },
        data: { status: "OPEN", closedAt: null },
      });
      events.emit("batch.opened", reopened.id, reopened, "SERVER");
      return reopened;
    }
    await closeOpenBatches(db, events, device.id);
    const snapshot = await buildAssignmentSnapshot(
      db,
      assets,
      state.model.id,
      state.product.id,
      state.product.acceptance,
    );
    const taskId = await ensureTask(db, snapshot.planId, snapshot.planName);
    try {
      const created = await db.inspectionBatch.create({
        data: {
          name: `${snapshot.planName} · ${new Date().toISOString()}`,
          deviceId: device.id,
          taskId,
          target: 10000000,
          productionRunId: state.productionRunId,
          snapshot: snapshot as unknown as Prisma.InputJsonValue,
          createdBy: "SYSTEM",
        },
      });
      events.emit("batch.opened", created.id, created, "SERVER");
      return created;
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === "P2002"
      )
        return db.inspectionBatch.findUnique({
          where: {
            deviceId_productionRunId: {
              deviceId: device.id,
              productionRunId: state.productionRunId,
            },
          },
        });
      throw error;
    }
  }
  if (!state.production && state.pendingSync === 0 && !state.pendingRequestId)
    await closeOpenBatches(db, events, device.id);
  return null;
}

export async function ensureBatchForRecord(
  db: Db,
  events: Events,
  assets: AssetsService,
  deviceId: string,
  record: {
    productionRunId?: string;
    planId: string;
    modelId: string;
    modelPayloadSha256: string;
    acceptance: AcceptancePolicy;
    capturedAt: string | null;
  },
) {
  if (!record.productionRunId) return null;
  const where = {
    deviceId_productionRunId: {
      deviceId,
      productionRunId: record.productionRunId,
    },
  };
  const existing = await db.inspectionBatch.findUnique({ where });
  if (existing) {
    const snapshot = existing.snapshot as unknown as BatchSnapshot;
    if (
      snapshot.modelPayloadSha256 !== record.modelPayloadSha256 ||
      snapshot.planId !== record.planId
    )
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "离线记录的产品或模型与该运行批次不一致",
        422,
      );
    return {
      batch: existing,
      late:
        !!existing.closedAt &&
        !!record.capturedAt &&
        new Date(record.capturedAt) > existing.closedAt,
    };
  }
  const snapshot = await buildAssignmentSnapshot(
    db,
    assets,
    record.modelId,
    record.planId,
    record.acceptance,
  );
  if (snapshot.modelPayloadSha256 !== record.modelPayloadSha256)
    throw new DomainError(
      "MODEL_INCOMPATIBLE",
      "离线记录的模型与平台模型制品不一致",
      422,
    );
  const taskId = await ensureTask(db, snapshot.planId, snapshot.planName);
  try {
    const created = await db.inspectionBatch.create({
      data: {
        name: `${snapshot.planName} · ${record.capturedAt ?? new Date().toISOString()}`,
        deviceId,
        taskId,
        target: 10000000,
        productionRunId: record.productionRunId,
        snapshot: snapshot as unknown as Prisma.InputJsonValue,
        createdBy: "SYSTEM",
        ...(record.capturedAt
          ? { createdAt: new Date(record.capturedAt) }
          : {}),
      },
    });
    events.emit("batch.opened", created.id, created, "SERVER");
    return { batch: created, late: false };
  } catch (error) {
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2002"
    ) {
      const saved = await db.inspectionBatch.findUnique({ where });
      return saved ? { batch: saved, late: false } : null;
    }
    throw error;
  }
}
