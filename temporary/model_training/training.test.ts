import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import { crc32 } from "node:zlib";

const output = resolve("temporary/model_training", `run-${Date.now()}`);
mkdirSync(output, { recursive: true });
process.env.DATABASE_URL = `file:${resolve(output, "app.db").replaceAll("\\", "/")}`;
process.env.JWT_SECRET = "test-only-training-secret-at-least-32-characters";
process.env.STORAGE_ROOT = resolve(output, "storage");
process.env.TRAINING_PYTHON = "data/training-venv/Scripts/python.exe";
let app: Awaited<
  ReturnType<(typeof import("../../apps/server/src/bootstrap.js"))["createApp"]>
>;
let token = "",
  datasetId = "",
  draftId = "";
let db: InstanceType<(typeof import("../../apps/server/src/core/db.js"))["Db"]>;

async function call(
  method: "GET" | "POST",
  url: string,
  payload?: unknown,
  status = method === "POST" ? 201 : 200,
) {
  const response = await app.inject({
    method,
    url: `/api${url}`,
    headers: { authorization: `Bearer ${token}` },
    payload: payload as Record<string, unknown>,
  });
  assert.equal(response.statusCode, status, response.body);
  return response.json();
}
async function wait(id: string, terminal = true) {
  const deadline = Date.now() + 60000;
  do {
    const row = await db.trainingJob.findUniqueOrThrow({
      where: { id },
      include: {
        models: { include: { artifacts: { include: { asset: true } } } },
      },
    });
    if (
      terminal
        ? ["COMPLETED", "FAILED", "CANCELLED"].includes(row.status)
        : row.status === "RUNNING"
    )
      return row;
    await new Promise((r) => setTimeout(r, 150));
  } while (Date.now() < deadline);
  throw new Error(`Training ${id} timed out`);
}
before(async () => {
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
  const { DatasetsService } =
    await import("../../apps/server/src/datasets/datasets.service.js");
  const { JwtService } =
    await import("../../apps/server/node_modules/@nestjs/jwt/index.js");
  app = await createApp(false);
  db = app.get(Db);
  const user = await db.user.create({
    data: {
      username: "trainer",
      name: "Trainer",
      role: "ENGINEER",
      passwordHash: "unused",
    },
  });
  token = await app
    .get(JwtService)
    .signAsync({ sub: user.id, role: user.role });
  const dataset = await db.dataset.create({
    data: { name: "Training fixture", version: 1 },
  });
  datasetId = dataset.id;
  draftId = (await db.dataset.create({ data: { name: "Draft", version: 1 } }))
    .id;
  for (let i = 0; i < 3; i++) {
    const path = resolve(
      "temporary/model_training/artifacts",
      `image-${i}.png`,
    );
    const stored = await app
      .get(AssetsService)
      .store(
        readFileSync(path),
        "PREVIEW",
        "IMPORT",
        `image-${i}.png`,
        "image/png",
        416,
        416,
      );
    const sample = await db.sample.create({
      data: {
        name: `Sample ${i}`,
        clientId: "training-test",
        idempotencyKey: `training-test-${i}`,
        localSequence: i,
        source: "IMPORT",
        capturedAt: new Date(),
        assets: { create: stored },
      },
      include: { assets: true },
    });
    await db.annotationSet.create({
      data: {
        sampleId: sample.id,
        userId: user.id,
        version: 1,
        status: "COMPLETE",
        boxes: {
          create: {
            classId: i,
            label: ["龟裂", "夹杂", "斑块"][i]!,
            x1: 40 + i * 20,
            y1: 60,
            x2: 150 + i * 20,
            y2: 130,
          },
        },
      },
    });
    await app.get(DatasetsService).add(datasetId, [sample.id]);
    if (i === 2)
      await db.datasetItem.updateMany({
        where: { datasetId, sampleId: sample.id },
        data: { split: "val" },
      });
  }
  await app.get(DatasetsService).freeze(datasetId);
});
after(async () => {
  await app?.close();
});

test("training API validates options and requires frozen data", async () => {
  await call(
    "POST",
    "/trainings",
    { name: "invalid", datasetId, options: { colorMode: "BGR" } },
    400,
  );
  await call(
    "POST",
    "/trainings",
    { name: "invalid", datasetId, options: { epochs: 0 } },
    400,
  );
  await call("POST", "/trainings", { name: "draft", datasetId: draftId }, 409);
});

test("real gray and RGB jobs train, export, register artifacts and reject corruption", async () => {
  const { validateZynqPackage } =
    await import("../../apps/server/src/models/zynq-profile.js");
  const { AssetsService } =
    await import("../../apps/server/src/assets/assets.service.js");
  for (const mode of ["GRAY", "RGB"]) {
    const job = await call("POST", "/trainings", {
      name: `Real ${mode}`,
      datasetId,
      options: { colorMode: mode, epochs: 1, batchSize: 2, workers: 0 },
    });
    const training = await wait(job.id);
    assert.equal(training.status, "COMPLETED", training.error ?? "");
    assert.equal(training.models.length, 1);
    const model = training.models[0]!;
    assert.equal(model.source, "IMPORT");
    const reportAsset = model.artifacts.find(
      (a) => a.kind === "TRAINING_REPORT",
    )!.asset;
    const report = JSON.parse(
      (await app.get(AssetsService).read(reportAsset.storageKey)).toString(),
    );
    assert.equal(report.runtime.device, "cuda");
    assert.notEqual(report.runtime.precision, "torch.float32");
    assert.ok(report.runtime.peakAllocatedMiB > 0);
    assert.ok(report.history[0].imagesPerSecond > 0);
    const { manifestSchema } =
      await import("../../packages/contracts/src/index.js");
    const manifest = manifestSchema.parse(model.manifest);
    assert.equal(manifest.input.channels, mode === "GRAY" ? 1 : 3);
    assert.equal(model.artifacts.length, 6);
    const asset = model.artifacts.find((a) => a.kind === "WEIGHTS")!.asset;
    const content = await app.get(AssetsService).read(asset.storageKey);
    validateZynqPackage(content, model.version, manifest);
    assert.equal(content.length, 6416360);
    const bad = Buffer.from(content);
    bad[1000] = bad[1000]! ^ 1;
    assert.throws(() => validateZynqPackage(bad, model.version, manifest));
    // A valid SHA/CRC must not conceal an incompatible command table.
    const wrongGraph = Buffer.from(content);
    wrongGraph.writeInt32LE(999, 128 + 6350208 + 4);
    createHash("sha256")
      .update(wrongGraph.subarray(128))
      .digest()
      .copy(wrongGraph, 88);
    wrongGraph.writeUInt32LE(crc32(wrongGraph.subarray(0, 120)), 120);
    assert.throws(() =>
      validateZynqPackage(wrongGraph, model.version, {
        ...manifest,
        weights: {
          size: wrongGraph.length,
          sha256: createHash("sha256").update(wrongGraph).digest("hex"),
        },
      }),
    );
    const exported = await app.inject({
      method: "POST",
      url: `/api/models/${model.id}/export`,
      headers: { authorization: `Bearer ${token}` },
    });
    assert.equal(exported.statusCode, 201);
    for (const name of [
      "manifest.json",
      "checkpoint.pt",
      "report.json",
      "quantization.json",
      "model.bin",
      "pl/weights.bin",
      "pl/metadata.bin",
    ])
      assert.ok(exported.rawPayload.includes(Buffer.from(name)), name);
  }
});

test("running cancellation kills training and never registers a model", async () => {
  const created = await call("POST", "/trainings", {
    name: "Cancel running",
    datasetId,
    options: { epochs: 1000 },
  });
  await wait(created.id, false);
  await call("POST", `/trainings/${created.id}/cancel`);
  await new Promise((r) => setTimeout(r, 900));
  const row = await wait(created.id);
  assert.equal(row.status, "CANCELLED");
  assert.equal(row.models.length, 0);
  assert.equal(
    (await db.job.findFirstOrThrow({ where: { entityId: created.id } })).status,
    "CANCELLED",
  );
});

test("frozen snapshot tampering fails without model creation", async () => {
  const item = await db.datasetItem.findFirstOrThrow({ where: { datasetId } });
  await db.datasetItem.update({
    where: { id: item.id },
    data: { split: "test" },
  });
  const created = await call("POST", "/trainings", {
    name: "Tampered dataset",
    datasetId,
    options: { epochs: 1 },
  });
  const row = await wait(created.id);
  assert.equal(row.status, "FAILED");
  assert.match(row.error!, /Frozen dataset checksum mismatch/);
  assert.equal(row.models.length, 0);
});
