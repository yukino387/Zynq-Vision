import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  Query,
  Body,
  Res,
  Inject,
} from "@nestjs/common";
import type { FastifyReply } from "fastify";
import { z } from "zod";
import { Db } from "../core/db.js";
import { Roles } from "../core/auth.js";
import { parse, DomainError } from "../core/errors.js";
import { listing, page } from "../core/list.js";
import { DatasetsService } from "./datasets.service.js";
@Roles("ADMIN", "ENGINEER")
@Controller("api/datasets")
export class DatasetsController {
  constructor(
    @Inject(Db) private db: Db,
    @Inject(DatasetsService) private datasets: DatasetsService,
  ) {}
  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query);
    if (q.realOnly === "true")
      args.where.items = { none: { sample: { source: "SIMULATION" } } };
    const rows = await this.db.dataset.findMany({
      ...args,
      include: {
        _count: { select: { items: true } },
        items: { select: { sample: { select: { source: true } } } },
      },
    });
    return page(
      rows.map(({ items, ...dataset }) => ({
        ...dataset,
        sourceCounts: items.reduce<Record<string, number>>((counts, item) => {
          counts[item.sample.source] = (counts[item.sample.source] ?? 0) + 1;
          return counts;
        }, {}),
      })),
      await this.db.dataset.count({ where: args.where }),
      q,
    );
  }
  @Post() create(@Body() body: unknown) {
    return this.db.dataset.create({
      data: parse(
        z
          .object({
            name: z.string().trim().min(1).max(120),
            version: z.number().int().positive(),
          })
          .strict(),
        body,
      ),
    });
  }
  @Roles("ADMIN") @Delete(":id") async remove(
    @Param("id") id: string,
    @Body() body: unknown,
  ) {
    parse(z.object({ confirm: z.literal(true) }).strict(), body);
    return this.db.$transaction(async (tx) => {
      const dataset = await tx.dataset.findUniqueOrThrow({
        where: { id },
        include: { _count: { select: { trainings: true, benchmarks: true } } },
      });
      if (dataset._count.trainings || dataset._count.benchmarks)
        throw new DomainError(
          "INVALID_STATE",
          "此数据集已被训练或评估使用，不能删除",
        );
      const exporting = await tx.job.count({
        where: {
          type: "DATASET_EXPORT",
          entityId: id,
          status: { in: ["QUEUED", "RUNNING"] },
        },
      });
      if (exporting)
        throw new DomainError(
          "INVALID_STATE",
          "此数据集正在导出，请等待导出完成后删除",
        );
      await tx.datasetItem.deleteMany({ where: { datasetId: id } });
      await tx.dataset.delete({ where: { id } });
      return { id };
    });
  }
  @Get(":id") async detail(@Param("id") id: string) {
    const dataset = await this.db.dataset.findUniqueOrThrow({
      where: { id },
      include: {
        items: {
          include: {
            sample: {
              include: {
                quality: true,
                assets: true,
                annotations: { orderBy: { version: "desc" }, take: 1 },
              },
            },
            annotationSet: { include: { boxes: true } },
          },
        },
        trainings: { include: { models: { include: { deployments: true } } } },
      },
    });
    const sourceCounts: Record<string, number> = {},
      classes: Record<string, number> = {};
    let warnings = 0;
    const hashes = new Set<string>();
    let duplicates = 0;
    for (const i of dataset.items) {
      sourceCounts[i.sample.source] = (sourceCounts[i.sample.source] ?? 0) + 1;
      for (const box of i.annotationSet.boxes)
        classes[box.label] = (classes[box.label] ?? 0) + 1;
      if (i.sample.quality?.status === "WARNING") warnings++;
      const hash = i.sample.assets.find((a) => a.kind === "RAW")?.sha256;
      if (hash) {
        if (hashes.has(hash)) duplicates++;
        hashes.add(hash);
      }
    }
    return {
      ...dataset,
      items: dataset.items.map((item) => ({
        ...item,
        needsUpdate:
          item.sample.annotations[0]?.id !== item.annotationSetId ||
          item.sample.annotations[0]?.status !== "COMPLETE",
      })),
      quality: {
        sourceCounts,
        classes,
        warnings,
        duplicates,
        hardSamples: dataset.items.filter((i) => i.sample.hard).length,
      },
    };
  }
  @Post(":id/items") add(@Param("id") id: string, @Body() body: unknown) {
    const dto = parse(
      z.object({ sampleIds: z.array(z.string()).min(1).max(100) }).strict(),
      body,
    );
    return this.datasets.add(id, dto.sampleIds);
  }
  @Roles("ADMIN") @Post(":id/freeze") freeze(@Param("id") id: string) {
    return this.datasets.freeze(id);
  }
  @Delete(":id/items/:sampleId") removeItem(
    @Param("id") id: string,
    @Param("sampleId") sampleId: string,
  ) {
    return this.datasets.removeItem(id, sampleId);
  }
  @Post(":id/clone") clone(@Param("id") id: string) {
    return this.datasets.clone(id);
  }
  @Post(":id/export") async export(
    @Param("id") id: string,
    @Res() reply: FastifyReply,
  ) {
    return reply
      .header("Content-Disposition", `attachment; filename="dataset-${id}.zip"`)
      .type("application/zip")
      .send(await this.datasets.export(id));
  }
  @Post(":id/export-jobs") async queuedExport(@Param("id") id: string) {
    const dataset = await this.db.dataset.findUniqueOrThrow({ where: { id } });
    if (dataset.status !== "FROZEN")
      throw new DomainError("INVALID_STATE", "Freeze dataset before export");
    return this.db.job.create({
      data: {
        type: "DATASET_EXPORT",
        entityId: id,
        payload: { datasetId: id },
      },
    });
  }
}
