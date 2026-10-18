import { Injectable, Inject } from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { createHash } from "node:crypto";
import { PassThrough } from "node:stream";
import archiver from "archiver";
import { manifestSchema } from "@vision/contracts";
import { compatibility } from "@vision/shared";
import { Db } from "../core/db.js";
import { DomainError } from "../core/errors.js";
import { AssetsService } from "../assets/assets.service.js";
import { DevicesService } from "../devices/devices.service.js";
import { simulatorManifest, simulatedWeights } from "./profile.js";
@Injectable()
export class ModelsService {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(AssetsService) private assets: AssetsService,
    @Inject(DevicesService) private devices: DevicesService,
  ) {}
  async artifact(id: string) {
    const model = await this.db.model.findUniqueOrThrow({
      where: { id },
      include: { artifacts: { include: { asset: true } } },
    });
    const manifest = manifestSchema.parse(model.manifest);
    const artifact = model.artifacts.find((a) => a.kind === "WEIGHTS");
    if (!artifact)
      throw new DomainError("ASSET_NOT_FOUND", "No model weights", 404);
    const weights = await this.assets.read(artifact.asset.storageKey);
    const sha256 = createHash("sha256").update(weights).digest("hex");
    if (
      sha256 !== manifest.weights.sha256 ||
      sha256 !== artifact.asset.sha256 ||
      weights.length !== manifest.weights.size
    )
      throw new DomainError(
        "CHECKSUM_ERROR",
        "Model artifact verification failed",
        422,
      );
    return { model, manifest, weights };
  }
  async check(id: string, deviceId: string) {
    const transport = this.devices.transport(deviceId);
    if (!transport.capabilities.modelUpdate)
      throw new DomainError(
        "NO_CAPABILITY",
        "Device firmware does not support model deployment",
        422,
      );
    const { model, manifest, weights } = await this.artifact(id);
    const device = await this.db.device.findUniqueOrThrow({
      where: { id: deviceId },
    });
    if (device.type !== "SIMULATOR" || model.source !== "SIMULATION")
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "Only SIMULATED models can run on SimulatorTransport",
        422,
      );
    const differences = compatibility(simulatorManifest(weights), manifest);
    if (differences.length)
      throw new DomainError("MODEL_INCOMPATIBLE", "Manifest mismatch", 422, {
        fields: differences,
      });
    return { model, manifest, weights, transport };
  }
  async simulatedModel(trainingId: string) {
    const version = `SIM-${trainingId}`,
      weights = simulatedWeights(version),
      manifest = simulatorManifest(weights);
    const assetData = await this.assets.store(
      weights,
      "MODEL_ARTIFACT",
      "SIMULATION",
      `${version}.simulated-weights`,
      "application/octet-stream",
    );
    return this.db.model.create({
      data: {
        name: "SIMULATED defect model",
        version,
        architecture: "SIMULATOR_DEFECT_V1",
        trainingId,
        source: "SIMULATION",
        manifest: manifest as unknown as Prisma.InputJsonValue,
        metrics: { accuracy: null, precision: null, recall: null, mAP: null },
        artifacts: {
          create: { kind: "WEIGHTS", asset: { create: assetData } },
        },
      },
    });
  }
  async export(id: string) {
    const { model, manifest, weights } = await this.artifact(id);
    const zip = archiver("zip"),
      out = new PassThrough();
    zip.on("error", (e) => out.destroy(e));
    zip.pipe(out);
    zip.append(JSON.stringify(manifest, null, 2), { name: "manifest.json" });
    zip.append(weights, {
      name: model.source === "SIMULATION" ? "weights.simulated" : "weights.bin",
    });
    zip.append(
      JSON.stringify({
        id: model.id,
        source: model.source,
        trainingId: model.trainingId,
        version: model.version,
        sha256: manifest.weights.sha256,
      }),
      { name: "metadata.json" },
    );
    void zip.finalize();
    return out;
  }
}
