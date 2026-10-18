import { manifestSchema } from "@vision/contracts";
import { createHash } from "node:crypto";
import type { Db } from "../core/db.js";
import type { AssetsService } from "../assets/assets.service.js";
import { DomainError } from "../core/errors.js";
import { validateZynqPackage } from "../models/zynq-profile.js";

export async function batchModel(db: Db, assets: AssetsService, id: string) {
  const model = await db.model.findUniqueOrThrow({
    where: { id },
    include: { artifacts: { include: { asset: true } } },
  });
  const artifact = model.artifacts.find((a) => a.kind === "WEIGHTS");
  if (!artifact || model.source !== "IMPORT")
    throw new DomainError(
      "MODEL_INCOMPATIBLE",
      "独立终端需要真实板卡模型制品",
      422,
    );
  const manifest = manifestSchema.parse(model.manifest),
    weights = await assets.read(artifact.asset.storageKey);
  validateZynqPackage(weights, model.version, manifest);
  if (
    createHash("sha256").update(weights).digest("hex") !== artifact.asset.sha256
  )
    throw new DomainError("CHECKSUM_ERROR", "模型资产摘要不一致", 422);
  return {
    model,
    manifest,
    weights,
    payloadSha256: weights.subarray(88, 120).toString("hex"),
  };
}
