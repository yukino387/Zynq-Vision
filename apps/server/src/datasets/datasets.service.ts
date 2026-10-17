import { Injectable, Inject } from "@nestjs/common";
import { Prisma } from "@prisma/client";
import { createHash } from "node:crypto";
import { PassThrough } from "node:stream";
import archiver from "archiver";
import { Db } from "../core/db.js";
import { AssetsService } from "../assets/assets.service.js";
import { DomainError } from "../core/errors.js";
@Injectable()
export class DatasetsService {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(AssetsService) private assets: AssetsService,
  ) {}
  async add(id: string, sampleIds: string[]) {
    return this.db.$transaction(async (tx) => {
      const dataset = await tx.dataset.findUniqueOrThrow({ where: { id } });
      if (dataset.status !== "DRAFT")
        throw new DomainError(
          "INVALID_STATE",
          "Only DRAFT datasets can be changed",
        );
      for (const sampleId of sampleIds) {
        const sample = await tx.sample.findUniqueOrThrow({
          where: { id: sampleId, deletedAt: null },
          include: {
            task: { include: { plan: true } },
            assets: true,
            annotations: {
              where: { status: "COMPLETE" },
              orderBy: { version: "desc" },
              take: 1,
              include: { boxes: true },
            },
          },
        });
        const annotation = sample.annotations[0];
        if (!annotation)
          throw new DomainError(
            "INVALID_STATE",
            "Complete annotations before adding sample",
          );
        const preview = sample.assets.find((a) => a.kind === "PREVIEW");
        if (!preview)
          throw new DomainError(
            "ASSET_NOT_FOUND",
            "Sample preview missing",
            404,
          );
        await tx.datasetItem.upsert({
          where: { datasetId_sampleId: { datasetId: id, sampleId } },
          create: {
            datasetId: id,
            sampleId,
            annotationSetId: annotation.id,
            snapshot: {
              ...(sample.task?.plan
                ? {
                    planId: sample.task.plan.id,
                    classes:
                      (sample.task.plan.rules as { classes?: string[] })
                        .classes ?? [],
                  }
                : {}),
              source: sample.source,
              hard: sample.hard,
              previewId: preview.id,
              width: preview.width,
              height: preview.height,
              sha256: preview.sha256,
              assets: sample.assets.map((a) => ({
                id: a.id,
                kind: a.kind,
                sha256: a.sha256,
              })),
              boxes: annotation.boxes,
            } as unknown as Prisma.InputJsonValue,
          },
          update: {},
        });
      }
      return tx.dataset.findUniqueOrThrow({
        where: { id },
        include: { items: true },
      });
    });
  }
  async freeze(id: string) {
    return this.db.$transaction(async (tx) => {
      const dataset = await tx.dataset.findUniqueOrThrow({
        where: { id },
        include: {
          items: { orderBy: { sampleId: "asc" }, include: { sample: true } },
        },
      });
      if (dataset.status === "FROZEN") return dataset;
      if (!dataset.items.length)
        throw new DomainError("INVALID_STATE", "Cannot freeze empty dataset");
      if (
        dataset.items.some(
          (item) => item.sample.status !== "REVIEWED" || item.sample.deletedAt,
        )
      )
        throw new DomainError(
          "INVALID_STATE",
          "请先由管理员审核通过全部样本，再冻结训练版本",
        );
      if (dataset.status === "DRAFT") {
        await tx.dataset.update({ where: { id }, data: { status: "READY" } });
      }
      const checksum = createHash("sha256")
        .update(
          JSON.stringify(
            dataset.items.map((i) => ({
              sampleId: i.sampleId,
              annotationSetId: i.annotationSetId,
              split: i.split,
              snapshot: i.snapshot,
            })),
          ),
        )
        .digest("hex");
      return tx.dataset.update({
        where: { id },
        data: { status: "FROZEN", checksum, frozenAt: new Date() },
      });
    });
  }
  async clone(id: string) {
    const old = await this.db.dataset.findUniqueOrThrow({
      where: { id },
      include: { items: true },
    });
    return this.db.$transaction(async (tx) => {
      const last = await tx.dataset.findFirst({
        where: { name: old.name },
        orderBy: { version: "desc" },
      });
      return tx.dataset.create({
        data: {
          name: old.name,
          version: (last?.version ?? 0) + 1,
          items: {
            create: old.items.map((i) => ({
              sampleId: i.sampleId,
              annotationSetId: i.annotationSetId,
              split: i.split,
              snapshot: i.snapshot as Prisma.InputJsonValue,
            })),
          },
        },
        include: { items: true },
      });
    });
  }
  async export(id: string) {
    const dataset = await this.db.dataset.findUniqueOrThrow({
      where: { id },
      include: {
        items: {
          include: {
            sample: { include: { assets: true } },
            annotationSet: { include: { boxes: true } },
          },
        },
      },
    });
    if (dataset.status !== "FROZEN")
      throw new DomainError("INVALID_STATE", "Freeze dataset before export");
    const zip = archiver("zip", { zlib: { level: 5 } }),
      output = new PassThrough();
    zip.on("error", (e) => output.destroy(e));
    zip.pipe(output);
    void (async () => {
      try {
        zip.append(
          JSON.stringify(
            {
              id: dataset.id,
              name: dataset.name,
              version: dataset.version,
              checksum: dataset.checksum,
              items: dataset.items.map((i) => ({
                sampleId: i.sampleId,
                split: i.split,
                snapshot: i.snapshot,
              })),
            },
            null,
            2,
          ),
          { name: "manifest.json" },
        );
        for (const item of dataset.items) {
          for (const asset of item.sample.assets) {
            const data = await this.assets.read(asset.storageKey);
            if (
              createHash("sha256").update(data).digest("hex") !== asset.sha256
            )
              throw new Error("Asset checksum mismatch");
            zip.append(data, {
              name:
                asset.kind === "PREVIEW"
                  ? `images/${item.sampleId}.jpg`
                  : `originals/${item.sampleId}/${asset.id}${asset.mimeType === "image/jpeg" ? ".jpg" : ".raw"}`,
            });
          }
          zip.append(JSON.stringify(item.snapshot), {
            name: `metadata/${item.sampleId}.json`,
          });
          const snapshot = item.snapshot as {
            width: number;
            height: number;
            boxes: {
              classId: number;
              x1: number;
              y1: number;
              x2: number;
              y2: number;
            }[];
          };
          zip.append(
            snapshot.boxes
              .map((b) =>
                [
                  b.classId,
                  (b.x1 + b.x2) / 2 / snapshot.width,
                  (b.y1 + b.y2) / 2 / snapshot.height,
                  (b.x2 - b.x1) / snapshot.width,
                  (b.y2 - b.y1) / snapshot.height,
                ].join(" "),
              )
              .join("\n"),
            { name: `labels/${item.sampleId}.txt` },
          );
        }
        await zip.finalize();
      } catch (error) {
        output.destroy(
          error instanceof Error ? error : new Error(String(error)),
        );
      }
    })();
    return output;
  }
}
