import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";

async function main() {
  const output = resolve(
    "temporary/training_usability_20261018",
    `run-${Date.now()}`,
  );
  mkdirSync(output, { recursive: true });
  process.env.DATABASE_URL = `file:${resolve(output, "app.db").replaceAll("\\", "/")}`;
  process.env.STORAGE_ROOT = resolve(output, "storage");
  process.env.JWT_SECRET = "isolated-training-usability-secret-2026";
  process.env.TRAINING_PYTHON = resolve(
    "data/training-venv/Scripts/python.exe",
  );
  process.env.ZYNQ_LOCAL_PORT = "15028";
  execFileSync(
    process.execPath,
    [
      resolve("apps/server/node_modules/prisma/build/index.js"),
      "migrate",
      "deploy",
      "--schema",
      resolve("apps/server/prisma/schema.prisma"),
    ],
    { env: process.env, stdio: "pipe" },
  );
  const { createApp } = await import("../../apps/server/src/bootstrap.js");
  const { Db } = await import("../../apps/server/src/core/db.js");
  const { AssetsService } =
    await import("../../apps/server/src/assets/assets.service.js");
  const { hash } =
    await import("../../apps/server/node_modules/bcryptjs/index.js");
  const { default: sharp } =
    await import("../../apps/server/node_modules/sharp/lib/index.js");
  const app = await createApp(false),
    db = app.get(Db),
    assets = app.get(AssetsService);
  try {
    const admin = await db.user.create({
      data: {
        username: "admin",
        name: "训练流程验证",
        role: "ADMIN",
        passwordHash: await hash("Training-Test-2026!", 4),
      },
    });
    const login = await app.inject({
      method: "POST",
      url: "/api/auth/login",
      payload: { username: "admin", password: "Training-Test-2026!" },
    });
    const token = login.json().token;
    async function call(
      method: "POST" | "GET",
      path: string,
      payload?: unknown,
      expected = method === "POST" ? 201 : 200,
    ) {
      const response = await app.inject({
        method,
        url: `/api${path}`,
        headers: { authorization: `Bearer ${token}` },
        payload: payload as any,
      });
      assert.equal(response.statusCode, expected, `${path}: ${response.body}`);
      return response.json();
    }
    const plan = await db.inspectionPlan.create({
      data: {
        name: "隔离正反面方案",
        version: 1,
        rules: {
          product: "验证件",
          purpose: "APPEARANCE",
          classes: ["正面", "反面"],
          instructions: "分别拍摄正反面",
          coordinateSpace: "NORMALIZED_FRAME",
          region: { x: 0, y: 0, width: 1, height: 1 },
          checks: [
            { classId: 0, min: 0, max: 1 },
            { classId: 1, min: 0, max: 1 },
          ],
        },
      },
    });
    const task = await db.task.create({
      data: { name: "隔离采样任务", target: 3, planId: plan.id },
    });
    const draft = await call("POST", "/datasets", {
      name: "未准备好的草稿",
      version: 1,
    });
    await call(
      "POST",
      "/trainings",
      { name: "不应排队", datasetId: draft.id },
      409,
    );
    const dataset = await call("POST", "/datasets", {
      name: "真实来源训练流程验证",
      version: 1,
    });
    const sampleIds: string[] = [];
    for (let i = 0; i < 3; i++) {
      const image = await sharp(
        Buffer.from(
          `<svg width="416" height="416"><rect width="416" height="416" fill="#c8c8c8"/><rect x="100" y="90" width="180" height="210" fill="${i % 2 ? "#333333" : "#dddddd"}"/></svg>`,
        ),
      )
        .png()
        .toBuffer();
      const stored = await assets.store(
        image,
        "PREVIEW",
        "IMPORT",
        `fixture-${i}.png`,
        "image/png",
        416,
        416,
      );
      const sample = await db.sample.create({
        data: {
          name: `隔离验证图片 ${i}`,
          source: "IMPORT",
          clientId: "training-usability",
          localSequence: i,
          idempotencyKey: `training-usability-${i}`,
          capturedAt: new Date(),
          taskId: task.id,
          assets: { create: stored },
        },
      });
      sampleIds.push(sample.id);
      await call("POST", `/samples/${sample.id}/annotations`, {
        status: "COMPLETE",
        boxes: [
          {
            classId: i % 2,
            label: i % 2 ? "反面" : "正面",
            confidence: 1,
            x1: 100,
            y1: 90,
            x2: 280,
            y2: 300,
          },
        ],
      });
      await call("POST", `/samples/${sample.id}/review`, {
        verdict: "ACCEPT",
        note: "隔离测试数据",
        hard: false,
      });
    }
    await call("POST", `/datasets/${dataset.id}/items`, { sampleIds });
    await db.datasetItem.updateMany({
      where: { datasetId: dataset.id, sampleId: sampleIds[2] },
      data: { split: "val" },
    });
    await call("POST", `/datasets/${dataset.id}/freeze`);
    const frozen = await db.dataset.findUniqueOrThrow({
      where: { id: dataset.id },
    });
    await db.dataset.update({
      where: { id: dataset.id },
      data: { checksum: "broken" },
    });
    const rejected = await call(
      "POST",
      "/trainings",
      { name: "不应排队的损坏快照", datasetId: dataset.id },
      409,
    );
    assert.match(rejected.message, /快照校验失败/);
    assert.equal(await db.trainingJob.count(), 0);
    await db.dataset.update({
      where: { id: dataset.id },
      data: { checksum: frozen.checksum },
    });
    await db.sample.update({
      where: { id: sampleIds[0] },
      data: { source: "SIMULATION" },
    });
    await call(
      "POST",
      "/trainings",
      { name: "不应排队的演示数据", datasetId: dataset.id },
      409,
    );
    assert.equal(await db.trainingJob.count(), 0);
    await db.sample.update({
      where: { id: sampleIds[0] },
      data: { source: "IMPORT" },
    });
    const training = await call("POST", "/trainings", {
      name: "CUDA 一轮流程验证",
      datasetId: dataset.id,
      options: {
        epochs: 1,
        batchSize: 2,
        device: "cuda",
        workers: 0,
        amp: true,
      },
    });
    console.log(
      JSON.stringify({
        trainingId: training.id,
        output,
        preflight:
          "draft, corrupt snapshot, simulation all rejected before queueing",
      }),
    );
    const deadline = Date.now() + 180000;
    let stage = "";
    while (Date.now() < deadline) {
      const row = await db.trainingJob.findUniqueOrThrow({
        where: { id: training.id },
        include: {
          models: { include: { artifacts: { include: { asset: true } } } },
        },
      });
      if (row.stage !== stage) {
        stage = row.stage;
        console.log(
          JSON.stringify({ stage, progress: row.progress, status: row.status }),
        );
      }
      if (row.status === "FAILED")
        throw new Error(row.error ?? "Training failed");
      if (row.status === "COMPLETED") {
        assert.equal(row.models.length, 1);
        const model = row.models[0]!;
        assert.equal(model.artifacts.length, 6);
        const reportAsset = model.artifacts.find(
          (a) => a.kind === "TRAINING_REPORT",
        )!.asset;
        const report = JSON.parse(
          (await assets.read(reportAsset.storageKey)).toString("utf8"),
        );
        const result = {
          ok: true,
          trainingId: row.id,
          modelId: model.id,
          status: row.status,
          artifactKinds: model.artifacts.map((a) => a.kind),
          runtime: report.runtime,
          epochs: report.history.length,
          preflight: "passed",
          output,
        };
        writeFileSync(
          resolve(output, "verification.json"),
          JSON.stringify(result, null, 2),
        );
        console.log(JSON.stringify(result));
        return;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    throw new Error("Training verification timed out");
  } finally {
    await app.close();
  }
}
void main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
