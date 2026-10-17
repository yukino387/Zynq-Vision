import { Injectable, Inject } from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { createHash } from "node:crypto";
import { Db } from "../core/db.js";
import { AssetsService } from "../assets/assets.service.js";
import { DatasetsService } from "./datasets.service.js";
@Injectable()
export class FileJobsService {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(AssetsService) private assets: AssetsService,
    @Inject(DatasetsService) private datasets: DatasetsService,
  ) {}
  async process(
    type: string,
    entityId: string,
    payload: Prisma.JsonValue,
  ): Promise<Prisma.InputJsonValue> {
    if (type === "DATASET_EXPORT") {
      return this.assets.exportStream(
        await this.datasets.export(entityId),
        `dataset-${entityId}.zip`,
      );
    }
    if (type === "ASSET_PROCESSING") {
      const asset = await this.db.asset.findFirstOrThrow({
        where: { sampleId: entityId, kind: "PREVIEW", deletedAt: null },
      });
      const data = await this.assets.read(asset.storageKey);
      if (createHash("sha256").update(data).digest("hex") !== asset.sha256)
        throw new Error("Asset checksum mismatch");
      const report = await this.assets.quality(data);
      await this.db.qualityReport.upsert({
        where: { sampleId: entityId },
        create: { sampleId: entityId, ...report },
        update: report,
      });
      return { sampleId: entityId, status: report.status };
    }
    if (type === "SYNC") {
      const sync = await this.db.syncJob.findUniqueOrThrow({
        where: { id: entityId },
      });
      const input = payload as {
        clientId: string;
        sampleKeys: string[];
        userId: string;
      };
      await this.db.syncJob.update({
        where: { id: entityId },
        data: {
          status: "RUNNING",
          attempts: { increment: 1 },
          startedAt: new Date(),
        },
      });
      const samples = await this.db.sample.findMany({
        where: {
          clientId: input.clientId,
          idempotencyKey: { in: input.sampleKeys },
        },
      });
      const accepted = samples
        .filter(
          (s) =>
            (s.metadata as Record<string, unknown>).uploadedBy === input.userId,
        )
        .map((s) => ({ id: s.id, idempotencyKey: s.idempotencyKey }));
      await this.db.syncJob.update({
        where: { id: sync.id },
        data: {
          status: "COMPLETED",
          completedAt: new Date(),
          payload: { accepted },
        },
      });
      return { accepted };
    }
    if (type === "CLEANUP") {
      const result = await this.db.pairingToken.deleteMany({
        where: { expiresAt: { lt: new Date() } },
      });
      return { expiredPairingTokens: result.count, originalAssetsDeleted: 0 };
    }
    throw new Error(`Unsupported job type ${type}`);
  }
}
