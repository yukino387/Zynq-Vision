import "reflect-metadata";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { readFileSync, writeFileSync } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { crc32 } from "node:zlib";
import { hash } from "../../apps/server/node_modules/bcryptjs/index.js";
import sharp from "../../apps/server/node_modules/sharp/lib/index.js";
import type { CapturedFrame } from "../../apps/server/src/devices/transport.js";

const out = resolve(
  "temporary/inspection_terminal_20261018",
  `run-${Date.now()}`,
);
mkdirSync(out, { recursive: true });
process.env.DATABASE_URL = `file:${resolve(out, "test.db").replaceAll("\\", "/")}`;
process.env.JWT_SECRET =
  "isolated-inspection-test-at-least-thirty-two-characters";
process.env.STORAGE_ROOT = resolve(out, "storage");
let app: Awaited<
  ReturnType<(typeof import("../../apps/server/src/bootstrap.js"))["createApp"]>
>;
let db: import("../../apps/server/src/core/db.js").Db;
let deviceId = "",
  taskId = "",
  admin = "",
  operator = "",
  modelId = "",
  frameId = 1;
let framePatch: Partial<CapturedFrame> = {},
  calls = 0;
async function request(
  method: "GET" | "POST" | "PATCH",
  path: string,
  body?: unknown,
  token = admin,
  status = method === "POST" ? 201 : 200,
) {
  const response = await app.inject({
    method,
    url: `/api${path}`,
    headers: token ? { authorization: `Bearer ${token}` } : {},
    payload: body as Record<string, unknown> | undefined,
  });
  assert.equal(
    response.statusCode,
    status,
    `${method} ${path}: ${response.body}`,
  );
  return response.json();
}
const requestId = (suffix: string) => ({
  clientId: "isolated-batch-tests",
  localSequence: ++frameId,
  idempotencyKey: `inspection-test-${frameId}-${suffix}`,
});
async function batch(
  name: string,
  policy = { confidence: 0.7, qualityGate: false },
) {
  await db.inspectionBatch.updateMany({
    where: { status: "OPEN" },
    data: { status: "CLOSED", closedAt: new Date() },
  });
  await db.task.update({ where: { id: taskId }, data: { status: "OPEN" } });
  framePatch = {};
  return request("POST", "/batches", {
    name,
    deviceId,
    taskId,
    target: 100,
    acceptance: policy,
  });
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
  const { createApp } = await import("../../apps/server/src/bootstrap.js"),
    { Db } = await import("../../apps/server/src/core/db.js"),
    { DevicesService } =
      await import("../../apps/server/src/devices/devices.service.js");
  app = await createApp(false);
  db = app.get(Db);
  for (const role of ["ADMIN", "OPERATOR"] as const) {
    await db.user.create({
      data: {
        username: role,
        name: role,
        role,
        passwordHash: await hash("test-password-2026", 4),
      },
    });
    const session = await request(
      "POST",
      "/auth/login",
      { username: role, password: "test-password-2026" },
      "",
    );
    if (role === "ADMIN") admin = session.token;
    else operator = session.token;
  }
  const device = await request("POST", "/devices", {
    name: "SIMULATED isolated test",
    serialNumber: "TEST-BATCH-DEVICE",
    type: "SIMULATOR",
  });
  deviceId = device.id;
  const plan = await request("POST", "/plans", {
    name: "包装配装",
    rules: {
      product: "牛奶",
      purpose: "COUNT",
      classes: ["牛奶"],
      instructions: "放入一个牛奶盒",
      region: { x: 0, y: 0, width: 1, height: 1 },
      coordinateSpace: "NORMALIZED_FRAME",
      checks: [{ classId: 0, min: 1, max: 1 }],
    },
  });
  const task = await request("POST", "/tasks", {
    name: "包装检查",
    target: 100,
    planId: plan.id,
  });
  taskId = task.id;
  const model = await db.model.create({
    data: {
      name: "SIMULATED test model",
      version: "SIM-V1",
      architecture: "FIXTURE",
      source: "SIMULATION",
      status: "APPROVED",
      manifest: {
        classes: [
          "牛奶",
          "未使用1",
          "未使用2",
          "未使用3",
          "未使用4",
          "未使用5",
        ],
      },
    },
  });
  modelId = model.id;
  const jpeg = await sharp({
    create: { width: 416, height: 416, channels: 3, background: "#888888" },
  })
    .jpeg()
    .toBuffer();
  app.get(DevicesService).transport(deviceId).captureOnce = async () => {
    calls++;
    return {
      frameId: ++frameId,
      receivedAt: new Date().toISOString(),
      raw: Buffer.alloc(416 * 416 * 2),
      preview: jpeg,
      width: 416,
      height: 416,
      format: "RGB565_LE",
      detections: [
        {
          classId: 0,
          label: "牛奶",
          confidence: 0.95,
          x1: 100,
          y1: 100,
          x2: 200,
          y2: 200,
        },
      ],
      modelState: { modelVersion: "SIM-V1" },
      telemetry: null,
      ...framePatch,
    };
  };
});
after(async () => app?.close());
test("authorization, model approval, class binding and a single open batch per device", async () => {
  const dto = {
    name: "TEST",
    deviceId,
    taskId,
    target: 10,
    acceptance: { confidence: 0.7, qualityGate: false },
  };
  await request("POST", "/batches", dto, "", 401);
  await request("POST", "/batches", dto, operator, 403);
  await db.model.update({
    where: { id: modelId },
    data: { status: "CANDIDATE" },
  });
  await request("POST", "/batches", dto, admin, 422);
  await db.model.update({
    where: { id: modelId },
    data: { status: "APPROVED" },
  });
  const b = await batch("single-open");
  assert.equal(b.snapshot.modelVersion, "SIM-V1");
  assert.equal(b.snapshot.rules.classes[0], "牛奶");
  await request("POST", "/batches", dto, admin, 409);
});
test("manual inspection is durable, concurrent retries do not recapture, late retry survives batch closure", async () => {
  const b = await batch("idempotency"),
    dto = requestId("retry"),
    beforeCalls = calls;
  const [one, two] = await Promise.all([
    request("POST", `/batches/${b.id}/check`, dto, operator),
    request("POST", `/batches/${b.id}/check`, dto, operator),
  ]);
  assert.equal(one.id, two.id);
  assert.equal(calls, beforeCalls + 1);
  assert.equal(one.inspections[0].result, "PASS");
  assert.equal(one.inspections[0].batchId, b.id);
  assert.equal(one.inspections[0].metadata.decision.findings[0].count, 1);
  await request("POST", `/batches/${b.id}/close`, { confirm: true });
  await db.task.update({
    where: { id: taskId },
    data: { status: "COMPLETED" },
  });
  const late = await request("POST", `/batches/${b.id}/check`, dto, operator);
  assert.equal(late.id, one.id);
  await request(
    "POST",
    `/batches/${b.id}/check`,
    requestId("closed"),
    operator,
    409,
  );
  const summary = await request("GET", `/batches/${b.id}/summary`);
  assert.equal(summary.total, 1);
  assert.equal(summary.passRate, 1);
});
test("uncertainty remains pending until an explicit human outcome; original result is immutable", async () => {
  const b = await batch("review");
  framePatch = { detections: null };
  const sample = await request(
      "POST",
      `/batches/${b.id}/check`,
      requestId("review"),
      operator,
    ),
    id = sample.inspections[0].id;
  assert.equal(sample.inspections[0].result, "REVIEW");
  await request(
    "POST",
    "/reviews",
    { inspectionId: id, verdict: "OTHER", note: "检查原始证据" },
    operator,
    400,
  );
  await request(
    "POST",
    "/reviews",
    {
      inspectionId: id,
      verdict: "OTHER",
      finalResult: "REVIEW",
      note: "等待现场重查",
    },
    operator,
  );
  let queue = await request(
    "GET",
    `/inspections?batchId=${b.id}&reviewed=false`,
  );
  assert.equal(queue.total, 1);
  await request(
    "POST",
    "/reviews",
    {
      inspectionId: id,
      verdict: "CORRECT",
      finalResult: "PASS",
      note: "现场复核符合要求",
    },
    operator,
  );
  const summary = await request("GET", `/batches/${b.id}/summary`);
  assert.equal(summary.machine.REVIEW, 1);
  assert.equal(summary.final.PASS, 1);
  assert.equal(summary.pending, 0);
  assert.equal((await request("GET", `/inspections/${id}`)).result, "REVIEW");
  queue = await request("GET", `/inspections?batchId=${b.id}&reviewed=false`);
  assert.equal(queue.total, 0);
  await request(
    "POST",
    "/reviews",
    {
      inspectionId: id,
      verdict: "OTHER",
      finalResult: "REVIEW",
      note: "新证据，重新复核",
    },
    operator,
  );
  assert.equal((await request("GET", `/batches/${b.id}/summary`)).pending, 1);
  queue = await request(
    "GET",
    `/inspections?batchId=${b.id}&result=REVIEW&reviewed=false`,
  );
  assert.equal(queue.total, 1);
  // A machine PASS can also be reopened for an explicit human recheck.
  await db.inspection.update({ where: { id }, data: { result: "PASS" } });
  queue = await request(
    "GET",
    `/inspections?batchId=${b.id}&result=REVIEW&reviewed=false`,
  );
  assert.equal(queue.total, 1);
  await db.inspection.update({ where: { id }, data: { result: "REVIEW" } });
  // Historical reviews without finalResult keep their original queue semantics.
  await db.inspection.update({
    where: { id },
    data: { reviewResult: null, batchId: null },
  });
  assert.equal(
    (
      await request("GET", `/inspections?result=REVIEW&reviewed=false`)
    ).items.some((item: { id: string }) => item.id === id),
    false,
  );
  await db.inspection.update({
    where: { id },
    data: { reviewResult: "REVIEW", batchId: b.id },
  });
});
test("model changes, stale frames, closed batches and duplicate frame IDs cannot be recorded as new production", async () => {
  const b = await batch("invalid-frame");
  framePatch = { modelState: { modelVersion: "DIFFERENT" } };
  await request(
    "POST",
    `/batches/${b.id}/check`,
    requestId("changed"),
    operator,
    422,
  );
  framePatch = { receivedAt: new Date(Date.now() - 10000).toISOString() };
  await request(
    "POST",
    `/batches/${b.id}/check`,
    requestId("stale"),
    operator,
    409,
  );
  framePatch = { frameId: 999999 };
  await request("POST", `/batches/${b.id}/check`, requestId("once"), operator);
  await request(
    "POST",
    `/batches/${b.id}/check`,
    requestId("duplicate"),
    operator,
    409,
  );
  assert.equal((await request("GET", `/batches/${b.id}/summary`)).total, 1);
});
test("quality warning goes to review; absent required objects fail with a saved explanation", async () => {
  let b = await batch("quality", { confidence: 0.7, qualityGate: true });
  let sample = await request(
    "POST",
    `/batches/${b.id}/check`,
    requestId("quality"),
    operator,
  );
  assert.equal(sample.inspections[0].result, "REVIEW");
  assert.match(sample.inspections[0].reason, /质量/);
  b = await batch("missing");
  framePatch = { detections: [] };
  sample = await request(
    "POST",
    `/batches/${b.id}/check`,
    requestId("missing"),
    operator,
  );
  assert.equal(sample.inspections[0].result, "FAIL");
  assert.match(sample.inspections[0].reason, /牛奶/);
});

test("offline terminal: approved job export, scoped credentials, evidence verification, recomputation and replay", async () => {
  const { zynqManifest } =
    await import("../../apps/server/src/models/zynq-profile.js");
  const { AssetsService } =
    await import("../../apps/server/src/assets/assets.service.js");
  const commands = JSON.parse(
    readFileSync("camera/training/graph.json", "utf8"),
  ).commands as number[][];
  const weights = Buffer.alloc(6416360),
    metadata = weights.subarray(128 + 6350208),
    version = "TEST-TERMINAL-V1";
  commands.forEach((command, i) =>
    command.forEach((v, j) => metadata.writeInt32LE(v, (i * 10 + j) * 4)),
  );
  for (const c of commands) {
    const offset = c[3]!,
      co = c[5]!,
      kernel = c[8]!;
    if (kernel === 1 || kernel === 3)
      for (let i = 0; i < co; i++)
        for (const scale of [1, 3]) {
          metadata.writeInt32LE(1, (offset + scale * co + i) * 4);
          metadata.writeInt32LE(1, (offset + (scale + 1) * co + i) * 4);
        }
    else if (kernel === 5) {
      metadata.writeInt32LE(1, offset * 4);
      metadata.writeInt32LE(1, (offset + 1) * 4);
    }
  }
  weights.writeUInt32LE(0x314e4e43, 0);
  weights.writeUInt32LE(1, 4);
  weights.writeUInt32LE(6350208, 8);
  weights.writeUInt32LE(66024, 12);
  weights.write(version, 24, "ascii");
  createHash("sha256").update(weights.subarray(128)).digest().copy(weights, 88);
  weights.writeUInt32LE(crc32(weights.subarray(0, 120)), 120);
  const asset = await app
    .get(AssetsService)
    .store(
      weights,
      "MODEL_ARTIFACT",
      "IMPORT",
      "test.bin",
      "application/octet-stream",
    );
  const manifest = zynqManifest(weights, 1, [
    "牛奶",
    "未使用1",
    "未使用2",
    "未使用3",
    "未使用4",
    "未使用5",
  ]);
  const model = await db.model.create({
    data: {
      name: "TEST terminal model",
      version,
      architecture: "ZYNQ7020_NEU_INT8_V1",
      source: "IMPORT",
      status: "APPROVED",
      manifest: JSON.parse(JSON.stringify(manifest)),
      artifacts: { create: { kind: "WEIGHTS", asset: { create: asset } } },
    },
  });
  const device = await db.device.create({
    data: {
      name: "TEST terminal (not connected)",
      serialNumber: "TEST-OFFLINE-TERMINAL",
      type: "ZYNQ",
      capabilities: {},
    },
  });
  const { DevicesService } =
    await import("../../apps/server/src/devices/devices.service.js");
  await app.get(DevicesService).attach(device.id);
  const b = await request("POST", "/batches", {
    name: "Offline test",
    deviceId: device.id,
    taskId,
    target: 10,
    execution: "TERMINAL",
    modelId: model.id,
    acceptance: { confidence: 0.7, qualityGate: false },
  });
  const exported = await app.inject({
    method: "GET",
    url: `/api/batches/${b.id}/package`,
    headers: { authorization: `Bearer ${admin}` },
  });
  assert.equal(exported.statusCode, 200);
  assert.equal(exported.rawPayload.readUInt32LE(0), 0x04034b50);
  const archivePath = resolve(out, "job.zip");
  writeFileSync(archivePath, exported.rawPayload);
  const installed = execFileSync(
    "python",
    [
      "camera/terminal/install_job.py",
      archivePath,
      "--state",
      resolve(out, "terminal-state"),
    ],
    { encoding: "utf8" },
  ).trim();
  assert.equal(
    readFileSync(resolve(installed, "model.bin")).length,
    weights.length,
  );
  assert.equal(
    execFileSync(
      "python",
      [
        "camera/terminal/install_job.py",
        archivePath,
        "--state",
        resolve(out, "terminal-state"),
      ],
      { encoding: "utf8" },
    ).trim(),
    installed,
  );
  await request(
    "POST",
    `/terminal/${device.id}/credential`,
    { confirm: true, server: "http://localhost:3000" },
    admin,
    400,
  );
  await request(
    "POST",
    `/terminal/${device.id}/credential`,
    { confirm: true, server: "http://169.254.140.109:3000" },
    operator,
    403,
  );
  const credential = await request(
    "POST",
    `/terminal/${device.id}/credential`,
    { confirm: true, server: "http://169.254.140.109:3000" },
  );
  const raw = Buffer.alloc(416 * 416 * 2),
    out0 = Buffer.alloc(1617, 128),
    out1 = Buffer.alloc(6468, 128);
  const record = {
    formatVersion: 1,
    batchId: b.id,
    bootId: randomUUID(),
    sequence: 1,
    frameId: 1,
    monotonicNs: "123456789",
    capturedAt: null,
    modelPayloadSha256: weights.subarray(88, 120).toString("hex"),
    raw: raw.toString("base64"),
    out0: out0.toString("base64"),
    out1: out1.toString("base64"),
    rawSha256: createHash("sha256").update(raw).digest("hex"),
    localResult: "FAIL",
  };
  await request("POST", "/terminal/records", record, "", 401);
  await request(
    "POST",
    "/terminal/records",
    { ...record, rawSha256: "0".repeat(64) },
    credential.token,
    422,
  );
  const one = await request(
    "POST",
    "/terminal/records",
    record,
    credential.token,
  );
  assert.equal(one.result, "FAIL");
  const replay = await request(
    "POST",
    "/terminal/records",
    record,
    credential.token,
  );
  assert.equal(one.inspectionId, replay.inspectionId);
  await request(
    "POST",
    "/terminal/records",
    { ...record, localResult: "PASS" },
    credential.token,
    409,
  );
  assert.equal((await request("GET", `/batches/${b.id}/summary`)).total, 1);
  const mismatch = await request(
    "POST",
    "/terminal/records",
    {
      ...record,
      sequence: 2,
      frameId: 2,
      monotonicNs: "123456790",
      localResult: "PASS",
    },
    credential.token,
  );
  assert.equal(mismatch.result, "REVIEW");
  const rotated = await request("POST", `/terminal/${device.id}/credential`, {
    confirm: true,
    server: "http://169.254.140.109:3000",
  });
  await request("POST", "/terminal/records", record, credential.token, 401);
  assert.equal(
    (await request("POST", "/terminal/records", record, rotated.token))
      .inspectionId,
    one.inspectionId,
  );
  await request("POST", `/batches/${b.id}/close`, { confirm: true });
  const late = await request(
    "POST",
    "/terminal/records",
    { ...record, sequence: 3, frameId: 3, monotonicNs: "123456791" },
    rotated.token,
  );
  assert.equal(late.result, "REVIEW");
});
