import { Controller, Get, Inject, Param, Query } from "@nestjs/common";
import type { BatchSummary, InspectionResult } from "@vision/contracts";
import { Db } from "../core/db.js";
import { listing, page } from "../core/list.js";

@Controller("api/batches")
export class BatchesController {
  constructor(@Inject(Db) private db: Db) {}

  @Get() async list(@Query() query: unknown) {
    const { q, args } = listing(query, [
      "name",
      "createdAt",
      "status",
      "deviceId",
      "taskId",
    ]);
    return page(
      await this.db.inspectionBatch.findMany({
        ...args,
        include: { _count: { select: { inspections: true } } },
      }),
      await this.db.inspectionBatch.count({ where: args.where }),
      q,
    );
  }

  @Get(":id") detail(@Param("id") id: string) {
    return this.db.inspectionBatch.findUniqueOrThrow({
      where: { id },
      include: { _count: { select: { inspections: true } } },
    });
  }

  @Get(":id/summary") async summary(
    @Param("id") id: string,
  ): Promise<BatchSummary> {
    await this.db.inspectionBatch.findUniqueOrThrow({ where: { id } });
    const rows = await this.db.inspection.groupBy({
      by: ["result", "reviewResult"],
      where: { batchId: id },
      _count: { _all: true },
    });
    const machine = { PASS: 0, FAIL: 0, REVIEW: 0, ERROR: 0 },
      final = { ...machine };
    let resolved = 0,
      total = 0;
    for (const row of rows) {
      const count = row._count._all;
      total += count;
      machine[row.result as InspectionResult] += count;
      const review = row.reviewResult;
      if (review === "PASS" || review === "FAIL") resolved += count;
      final[(review ?? row.result) as InspectionResult] += count;
    }
    const decided = final.PASS + final.FAIL;
    return {
      total,
      machine,
      final,
      resolved,
      pending: final.REVIEW + final.ERROR,
      passRate: decided ? final.PASS / decided : null,
    };
  }
}
