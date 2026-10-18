import { test, before, after } from "node:test";
import { inflateRawSync } from "node:zlib";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { readdir } from "node:fs/promises";
import { resolve } from "node:path";
import { randomUUID, createHash } from "node:crypto";
import sharp from "../../apps/server/node_modules/sharp/lib/index.js";
// Inspect archive entries rather than accepting a ZIP signature as a usable export.
function unzip(data: Buffer) {
  const end = data.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  assert.ok(end >= 0, "ZIP must have a central directory");
  const count = data.readUInt16LE(end + 10);
  let cursor = data.readUInt32LE(end + 16);
  const files = new Map<string, Buffer>();
  for (let i = 0; i < count; i++) {
    assert.equal(data.readUInt32LE(cursor), 0x02014b50);
    const method = data.readUInt16LE(cursor + 10);
    const compressedSize = data.readUInt32LE(cursor + 20);
    const nameLength = data.readUInt16LE(cursor + 28);
    const extraLength = data.readUInt16LE(cursor + 30);
    const commentLength = data.readUInt16LE(cursor + 32);
    const offset = data.readUInt32LE(cursor + 42);
    const name = data
      .subarray(cursor + 46, cursor + 46 + nameLength)
      .toString();
    assert.equal(data.readUInt32LE(offset), 0x04034b50);
    const start =
      offset +
      30 +
      data.readUInt16LE(offset + 26) +
      data.readUInt16LE(offset + 28);
    const compressed = data.subarray(start, start + compressedSize);
    assert.ok(method === 0 || method === 8);
    files.set(name, method === 8 ? inflateRawSync(compressed) : compressed);
    cursor += 46 + nameLength + extraLength + commentLength;
  }
  return files;
}
const output = resolve("temporary/iot_platform_test", `run-${Date.now()}`);
mkdirSync(output, { recursive: true });
process.env.DATABASE_URL = `file:${resolve(output, "app.db").replaceAll("\\", "/")}`;
process.env.JWT_SECRET = "test-only-secret-32-characters-do-not-reuse";
process.env.SEED_PASSWORD = "Vision-Test-Password-2026!";
process.env.WS_PATH = "/vision-test-ws";
process.env.STORAGE_ROOT = resolve(output, "storage");
let app: Awaited<
  ReturnType<(typeof import("../../apps/server/src/bootstrap.js"))["createApp"]>
>;
let token = "",
  operator = "",
  engineer = "";
async function call<T = Record<string, unknown>>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  url: string,
  body?: unknown,
  bearer = token,
  status = method === "POST" ? 201 : 200,
): Promise<T> {
  const response = await app.inject({
    method,
    url: `/api${url}`,
    headers: bearer ? { authorization: `Bearer ${bearer}` } : {},
    payload: body as Record<string, unknown> | undefined,
  });
  assert.equal(
    response.statusCode,
    status,
    `${method} ${url}: ${response.body}`,
  );
  return response.json<T>();
}
async function waitFor<T>(read: () => Promise<T>, done: (value: T) => boolean) {
  const deadline = Date.now() + 15000;
  let last: T;
  do {
    last = await read();
    if (done(last)) return last;
    await new Promise((r) => setTimeout(r, 150));
  } while (Date.now() < deadline);
  throw new Error(`Timed out: ${JSON.stringify(last!)}`);
}
before(async () => {
  const cli = resolve("apps/server/node_modules/prisma/build/index.js");
  execFileSync(
    process.execPath,
    [
      cli,
      "migrate",
      "deploy",
      "--schema",
      resolve("apps/server/prisma/schema.prisma"),
    ],
    { env: process.env, stdio: "pipe" },
  );
  const { createApp } = await import("../../apps/server/src/bootstrap.js");
  const { Db } = await import("../../apps/server/src/core/db.js");
  app = await createApp(false);
  const db = app.get(Db);
  const { hash } =
    await import("../../apps/server/node_modules/bcryptjs/index.js");
  for (const role of ["ADMIN", "ENGINEER", "OPERATOR"] as const)
    await db.user.create({
      data: {
        username: role.toLowerCase(),
        name: `TEST ${role}`,
        role,
        passwordHash: await hash(process.env.SEED_PASSWORD!, 4),
      },
    });
  token = (
    await call<{ token: string }>(
      "POST",
      "/auth/login",
      { username: "admin", password: process.env.SEED_PASSWORD },
      "",
      201,
    )
  ).token;
  operator = (
    await call<{ token: string }>(
      "POST",
      "/auth/login",
      { username: "operator", password: process.env.SEED_PASSWORD },
      "",
      201,
    )
  ).token;
  engineer = (
    await call<{ token: string }>(
      "POST",
      "/auth/login",
      { username: "engineer", password: process.env.SEED_PASSWORD },
      "",
      201,
    )
  ).token;
});
after(async () => {
  await app?.close();
});
test("API auth, role enforcement, validation and safe user projection", async () => {
  await call("GET", "/devices", undefined, "", 401);
  await call(
    "POST",
    "/users",
    { name: "bad", username: "bad", password: "abcdefghijklm", role: "ADMIN" },
    operator,
    403,
  );
  await call("GET", "/users", undefined, engineer, 403);
  const user = await call("POST", "/users", {
    name: "New test operator",
    username: "new-user",
    password: "temporary-test-pass",
    role: "OPERATOR",
  });
  assert.equal(user.passwordHash, undefined);
  await call("POST", "/stations", { name: "", code: "x" }, token, 400);
});
test("Simulator E2E: registration → capture → review → frozen dataset → fixture model → approval → deployment → self-test → rollback", async () => {
  const station = await call<{ id: string }>("POST", "/stations", {
    name: "TEST Station",
    code: randomUUID(),
  });
  const device = await call<{ id: string }>("POST", "/devices", {
    name: "SIMULATED E2E device",
    serialNumber: randomUUID(),
    type: "SIMULATOR",
    stationId: station.id,
  });
  const snapshot = await call<{ id: string; connectionState: string }[]>(
    "GET",
    "/devices/snapshot",
  );
  assert.equal(
    snapshot.find((d) => d.id === device.id)?.connectionState,
    "ONLINE",
  );
  const task = await call<{ id: string }>("POST", "/tasks", {
    name: "TEST task",
    target: 3,
    stationId: station.id,
  });
  const capture = {
    deviceId: device.id,
    taskId: task.id,
    idempotencyKey: randomUUID(),
    clientId: randomUUID(),
    localSequence: 0,
  };
  type Sample = {
    id: string;
    assets: { id: string; kind: string }[];
    inspections: { id: string; detections: unknown[] }[];
  };
  const [sample, replay] = await Promise.all([
    call<Sample>("POST", "/samples/capture", capture, operator),
    call<Sample>("POST", "/samples/capture", capture, operator),
  ]);
  assert.equal(sample.id, replay.id);
  assert.ok(sample.assets.some((a) => a.kind === "RAW"));
  assert.ok(sample.assets.some((a) => a.kind === "MODEL_INPUT"));
  assert.equal(sample.inspections.length, 1);
  await call(
    "POST",
    "/reviews",
    {
      inspectionId: sample.inspections[0]!.id,
      verdict: "FALSE_POSITIVE",
      hard: true,
      note: "TEST hard sample",
    },
    operator,
  );
  const reviewed = await call<{ hard: boolean }>(
    "GET",
    `/samples/${sample.id}`,
  );
  assert.equal(reviewed.hard, true);
  await call(
    "POST",
    `/samples/${sample.id}/annotations`,
    {
      status: "COMPLETE",
      boxes: [
        {
          classId: 5,
          label: "划痕",
          confidence: 1,
          x1: 80,
          y1: 80,
          x2: 150,
          y2: 320,
        },
      ],
    },
    token,
  );
  await call("POST", `/samples/${sample.id}/review`, { verdict: "ACCEPT" });
  const dataset = await call<{ id: string }>(
    "POST",
    "/datasets",
    { name: "TEST dataset", version: 1 },
    token,
  );
  await call(
    "POST",
    `/datasets/${dataset.id}/items`,
    { sampleIds: [sample.id] },
    token,
  );
  await call("POST", `/datasets/${dataset.id}/freeze`, {}, token);
  await call(
    "POST",
    `/datasets/${dataset.id}/items`,
    { sampleIds: [sample.id] },
    token,
    409,
  );
  const frozen = await call<{
    checksum: string;
    items: { snapshot: unknown }[];
  }>("GET", `/datasets/${dataset.id}`, undefined, token);
  await call(
    "POST",
    `/samples/${sample.id}/annotations`,
    { status: "COMPLETE", boxes: [] },
    token,
  );
  const frozenAfter = await call<typeof frozen>(
    "GET",
    `/datasets/${dataset.id}`,
    undefined,
    token,
  );
  assert.equal(frozen.checksum, frozenAfter.checksum);
  assert.deepEqual(frozen.items[0]!.snapshot, frozenAfter.items[0]!.snapshot);
  // GPU training produces PL models. Simulator deployment uses explicit fixtures.
  async function simulatorModel(name: string) {
    const { Db } = await import("../../apps/server/src/core/db.js");
    const { ModelsService } =
      await import("../../apps/server/src/models/models.service.js");
    const training = await app.get(Db).trainingJob.create({
      data: {
        datasetId: dataset.id,
        name,
        status: "COMPLETED",
        source: "SIMULATION",
        progress: 100,
        stage: "Fixture",
      },
    });
    return app.get(ModelsService).simulatedModel(training.id);
  }
  const model = await simulatorModel("SIMULATED fixture V1");
  // Evaluation is disabled; approval and deployment must work without it.
  await call("GET", "/benchmarks", undefined, token, 404);
  await call(
    "POST",
    "/benchmarks",
    {
      name: "SIMULATED Benchmark E2E",
      deviceId: device.id,
      modelId: model.id,
      datasetId: dataset.id,
    },
    token,
    404,
  );
  assert.equal(
    (await call<{ status: string }>("GET", `/models/${model.id}`)).status,
    "CANDIDATE",
  );
  await call("POST", `/models/${model.id}/approve`, {
    confirm: true,
    note: "SIMULATED fixture acceptance only",
  });
  const deployment = await call<{ id: string }>(
    "POST",
    "/deployments",
    { deviceId: device.id, modelId: model.id },
    token,
  );
  await waitFor(
    () =>
      call<{
        items: { id: string; status: string; receipt: { selfTest: boolean } }[];
      }>("GET", "/deployments", undefined, token),
    (r) =>
      r.items.some(
        (d) =>
          d.id === deployment.id && d.status === "ACTIVE" && d.receipt.selfTest,
      ),
  );
  const model2 = await simulatorModel("SIMULATED fixture V2");
  await call("POST", `/models/${model2.id}/approve`, {
    confirm: true,
    note: "SIMULATED fixture V2 acceptance only",
  });
  const deploy2 = await call<{ id: string }>(
    "POST",
    "/deployments",
    { deviceId: device.id, modelId: model2.id },
    token,
  );
  await waitFor(
    () =>
      call<{ items: { id: string; status: string }[] }>(
        "GET",
        "/deployments",
        undefined,
        token,
      ),
    (r) => r.items.some((d) => d.id === deploy2.id && d.status === "ACTIVE"),
  );
  const rolled = await call<{ status: string }>(
    "POST",
    `/deployments/${deploy2.id}/rollback`,
    {},
    token,
  );
  assert.equal(rolled.status, "ROLLED_BACK");
  const snapshots = await call<
    { id: string; reportedState: { modelVersion: string } }[]
  >("GET", "/devices/snapshot");
  assert.equal(
    snapshots.find((d) => d.id === device.id)?.reportedState.modelVersion,
    model.version,
  );
  const board = await call<{ id: string }>("POST", "/devices", {
    name: "TEST real adapter (not connected)",
    serialNumber: randomUUID(),
    type: "ZYNQ",
  });
  await call(
    "POST",
    "/deployments",
    { deviceId: board.id, modelId: model.id },
    token,
    422,
  );
  const audit = await call<{ total: number }>("GET", "/audit");
  assert.ok(audit.total >= 15);
  const zip = await app.inject({
    method: "POST",
    url: `/api/datasets/${dataset.id}/export`,
    headers: { authorization: `Bearer ${token}` },
  });
  assert.equal(zip.statusCode, 201);
  assert.equal(zip.rawPayload.subarray(0, 2).toString(), "PK");
  const files = unzip(zip.rawPayload);
  const imageName = `images/${sample.id}.jpg`,
    labelName = `labels/${sample.id}.txt`;
  assert.ok(
    files.has(imageName),
    "YOLO image must share its basename with the label",
  );
  const image = files.get(imageName)!;
  const imageMeta = await sharp(image).metadata();
  assert.equal(imageMeta.width, 416);
  assert.equal(imageMeta.height, 416);
  assert.deepEqual(files.get(labelName)!.toString().split(" ").map(Number), [
    5,
    115 / 416,
    200 / 416,
    70 / 416,
    240 / 416,
  ]);
  const original = sample.assets.find((a) => a.kind === "RAW")!;
  const rawPath = `originals/${sample.id}/${original.id}.raw`;
  const originalResponse = await app.inject({
    method: "GET",
    url: `/api/assets/${original.id}/content`,
    headers: { authorization: `Bearer ${token}` },
  });
  assert.deepEqual(files.get(rawPath), originalResponse.rawPayload);
  const modelExport = await app.inject({
    method: "POST",
    url: `/api/models/${model.id}/export`,
    headers: { authorization: `Bearer ${token}` },
  });
  assert.equal(modelExport.statusCode, 201);
  const modelFiles = unzip(modelExport.rawPayload);
  const modelManifest = JSON.parse(modelFiles.get("manifest.json")!.toString());
  const weights = modelFiles.get("weights.simulated")!;
  assert.equal(
    createHash("sha256").update(weights).digest("hex"),
    modelManifest.weights.sha256,
  );
  assert.equal(weights.length, modelManifest.weights.size);

  const queuedExport = await call<{ id: string }>(
    "POST",
    `/datasets/${dataset.id}/export-jobs`,
    {},
    token,
  );
  async function completedJob(id: string) {
    return waitFor(
      () =>
        call<{
          items: {
            id: string;
            status: string;
            payload: { output: Record<string, unknown> };
          }[];
        }>("GET", "/system/jobs"),
      (r) => r.items.some((j) => j.id === id && j.status === "COMPLETED"),
    );
  }
  const exportResult = await completedJob(queuedExport.id);
  const output = exportResult.items.find((j) => j.id === queuedExport.id)!
    .payload.output;
  const exported = await app.inject({
    method: "GET",
    url: `/api/system/jobs/${queuedExport.id}/content`,
    headers: { authorization: `Bearer ${token}` },
  });
  assert.equal(exported.statusCode, 200);
  assert.equal(
    createHash("sha256").update(exported.rawPayload).digest("hex"),
    output.sha256,
  );
  const processJob = await call<{ id: string }>(
    "POST",
    `/samples/${sample.id}/process`,
    {},
    token,
  );
  await completedJob(processJob.id);
  const syncJob = await call<{ id: string }>(
    "POST",
    "/system/sync-jobs",
    { clientId: capture.clientId, sampleKeys: [capture.idempotencyKey] },
    operator,
  );
  const syncResult = await completedJob(syncJob.id);
  assert.equal(
    (
      syncResult.items.find((j) => j.id === syncJob.id)!.payload.output
        .accepted as unknown[]
    ).length,
    1,
  );
  const cleanup = await call<{ id: string }>("POST", "/system/cleanup", {});
  await completedJob(cleanup.id);
  const health = await call<{
    database: { sizeBytes: number };
    storage: { exportsBytes: number };
  }>("GET", "/system");
  assert.ok(health.database.sizeBytes > 0);
  assert.ok(health.storage.exportsBytes > 0);
  await call(
    "POST",
    `/devices/${device.id}/commands`,
    { type: "FAULT", value: "DEPLOYMENT_FAILED" },
    token,
  );
  const failed = await call<{ id: string }>(
    "POST",
    "/deployments",
    { deviceId: device.id, modelId: model2.id },
    token,
  );
  await waitFor(
    () =>
      call<{ items: { id: string; status: string }[] }>(
        "GET",
        "/deployments",
        undefined,
        token,
      ),
    (r) => r.items.some((d) => d.id === failed.id && d.status === "FAILED"),
  );
  const retained = await call<typeof snapshots>("GET", "/devices/snapshot");
  assert.equal(
    retained.find((d) => d.id === device.id)?.reportedState.modelVersion,
    model.version,
  );
  await call(
    "POST",
    `/devices/${device.id}/commands`,
    { type: "FAULT", value: "NONE" },
    token,
  );
  await call("POST", `/deployments/${failed.id}/rollback`, {}, token);
});
test("one-time pairing expires through atomic consumption and WebSocket requires authentication", async () => {
  const pairing = await call<{ pairingToken: string }>(
    "POST",
    "/system/pairing",
    { serverUrl: "http://192.168.43.10:3000" },
    engineer,
  );
  await call(
    "POST",
    "/system/pairing/redeem",
    { token: pairing.pairingToken },
    "",
  );
  await call(
    "POST",
    "/system/pairing/redeem",
    { token: pairing.pairingToken },
    "",
    400,
  );
  await app.listen(0, "127.0.0.1");
  const address = app.getHttpServer().address();
  assert.ok(address && typeof address !== "string");
  const policy = await call<{ wsPath: string }>("GET", "/devices/policy");
  assert.equal(policy.wsPath, process.env.WS_PATH);
  const url = `ws://127.0.0.1:${address.port}${policy.wsPath}`;
  const ws = new WebSocket(url);
  const ready = new Promise<{ type: string }>((resolve, reject) => {
    ws.addEventListener("open", () =>
      ws.send(JSON.stringify({ token: engineer })),
    );
    ws.addEventListener(
      "message",
      (e) => resolve(JSON.parse(String(e.data)) as { type: string }),
      { once: true },
    );
    ws.addEventListener("error", reject);
  });
  assert.equal((await ready).type, "session.ready");
  ws.close();
  const invalid = new WebSocket(url);
  const closed = new Promise<number>((resolve) =>
    invalid.addEventListener("close", (e) => resolve(e.code)),
  );
  invalid.addEventListener("open", () =>
    invalid.send(JSON.stringify({ token: "invalid" })),
  );
  assert.equal(await closed, 1008);
});
test("mobile multipart uploads preserve bytes, retry idempotently and support sample-only review", async () => {
  const image = await sharp({
      create: { width: 32, height: 32, channels: 3, background: "#889988" },
    })
      .png()
      .toBuffer(),
    boundary = "vision-boundary-" + randomUUID();
  const metadata = {
    source: "MOBILE",
    clientId: randomUUID(),
    localSequence: 1,
    idempotencyKey: randomUUID(),
    capturedAt: new Date().toISOString(),
    metadata: { imuAvailable: false, label: "SIMULATED TEST FIXTURE" },
  };
  function payload(meta: unknown) {
    return Buffer.concat([
      Buffer.from(
        `--${boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n${JSON.stringify(meta)}\r\n--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="SIMULATED.png"\r\nContent-Type: image/png\r\n\r\n`,
      ),
      image,
      Buffer.from(`\r\n--${boundary}--\r\n`),
    ]);
  }
  async function upload(meta: unknown) {
    return app.inject({
      method: "POST",
      url: "/api/samples/upload",
      headers: {
        authorization: `Bearer ${operator}`,
        "content-type": `multipart/form-data; boundary=${boundary}`,
      },
      payload: payload(meta),
    });
  }
  const first = await upload(metadata),
    retry = await upload(metadata);
  assert.equal(first.statusCode, 201, first.body);
  assert.equal(retry.statusCode, 201, retry.body);
  type Sample = { id: string; assets: { id: string; kind: string }[] };
  const sample = first.json<Sample>();
  assert.equal(sample.id, retry.json<Sample>().id);
  const raw = sample.assets.find((a) => a.kind === "RAW")!;
  const file = await app.inject({
    method: "GET",
    url: `/api/assets/${raw.id}/content`,
    headers: { authorization: `Bearer ${operator}` },
  });
  assert.deepEqual(file.rawPayload, image);
  await call(
    "POST",
    `/samples/${sample.id}/review`,
    { verdict: "ACCEPT", note: "TEST sample-only review", hard: true },
    operator,
    403,
  );
  await call("POST", `/samples/${sample.id}/review`, {
    verdict: "ACCEPT",
    note: "Administrator approval",
    hard: true,
  });
  const reviewed = await call<{
    status: string;
    hard: boolean;
    inspections: unknown[];
  }>("GET", `/samples/${sample.id}`, undefined, operator);
  assert.equal(reviewed.status, "REVIEWED");
  assert.equal(reviewed.hard, true);
  assert.equal(reviewed.inspections.length, 0);
  const conflict = await upload({ ...metadata, localSequence: 2 });
  assert.equal(conflict.statusCode, 409);
});
test("plan versions guide sampling; worker feedback cannot approve data; only admin freezes and publishes", async () => {
  const rules = {
    product: "测试包装盒",
    purpose: "PRESENCE",
    classes: ["盒体", "标签"],
    instructions: "居中摆放，分别采集完整包装、缺标签、空场景。",
    conditions: "固定光照",
    referenceUrl: "",
    coordinateSpace: "NORMALIZED_FRAME",
    region: { x: 0, y: 0, width: 1, height: 1 },
    checks: [
      { classId: 0, min: 1, max: 1 },
      { classId: 1, min: 1, max: 1 },
    ],
  };
  const input = { name: "TEST product plan", rules };
  await call("POST", "/plans", input, operator, 403);
  await call("POST", "/plans", input, engineer, 403);
  await call(
    "POST",
    "/plans",
    { ...input, rules: { ...rules, classes: ["标签", "标签"] } },
    token,
    400,
  );
  await call(
    "POST",
    "/plans",
    {
      ...input,
      rules: { ...rules, region: { x: 0.9, y: 0, width: 0.5, height: 1 } },
    },
    token,
    400,
  );
  const plan = await call<{ id: string; version: number }>(
    "POST",
    "/plans",
    input,
  );
  const next = await call<{ id: string; version: number }>("POST", "/plans", {
    ...input,
    rules: { ...rules, instructions: "第二版摆放指引" },
  });
  assert.equal(next.version, plan.version + 1);
  const task = await call<{ id: string }>("POST", "/tasks", {
    name: "TEST guided sampling",
    target: 2,
    planId: plan.id,
  });
  const loaded = await call<{
    plan: { id: string; rules: { instructions: string } };
  }>("GET", `/tasks/${task.id}`, undefined, operator);
  assert.equal(loaded.plan.id, plan.id);
  assert.equal(loaded.plan.rules.instructions, rules.instructions);
  const device = await call<{ id: string }>("POST", "/devices", {
    name: "SIMULATED plan workflow",
    serialNumber: randomUUID(),
    type: "SIMULATOR",
  });
  const sample = await call<{ id: string; inspections: { id: string }[] }>(
    "POST",
    "/samples/capture",
    {
      deviceId: device.id,
      taskId: task.id,
      idempotencyKey: randomUUID(),
      clientId: randomUUID(),
      localSequence: 0,
    },
    operator,
  );
  const box = {
    classId: 0,
    label: "untrusted label",
    confidence: 1,
    x1: 10,
    y1: 10,
    x2: 100,
    y2: 100,
  };
  await call(
    "POST",
    `/samples/${sample.id}/annotations`,
    { status: "COMPLETE", boxes: [{ ...box, classId: 5 }] },
    engineer,
    400,
  );
  const annotation = await call<{ boxes: { label: string }[] }>(
    "POST",
    `/samples/${sample.id}/annotations`,
    { status: "COMPLETE", boxes: [box] },
    engineer,
  );
  assert.equal(annotation.boxes[0]!.label, "盒体");
  await call(
    "POST",
    "/reviews",
    { inspectionId: sample.inspections[0]!.id, verdict: "CORRECT" },
    operator,
  );
  assert.equal(
    (await call<{ status: string }>("GET", `/samples/${sample.id}`)).status,
    "PENDING",
  );
  await call(
    "POST",
    `/samples/${sample.id}/review`,
    { verdict: "ACCEPT" },
    operator,
    403,
  );
  await call(
    "POST",
    `/samples/${sample.id}/review`,
    { verdict: "ACCEPT" },
    engineer,
    403,
  );
  const dataset = await call<{ id: string }>(
    "POST",
    "/datasets",
    { name: "TEST plan dataset", version: 1 },
    engineer,
  );
  await call(
    "POST",
    `/datasets/${dataset.id}/items`,
    { sampleIds: [sample.id] },
    engineer,
  );
  await call("POST", `/datasets/${dataset.id}/freeze`, {}, token, 409);
  await call("POST", `/samples/${sample.id}/review`, { verdict: "ACCEPT" });
  await call("POST", `/datasets/${dataset.id}/freeze`, {}, engineer, 403);
  await call("POST", `/datasets/${dataset.id}/freeze`, {});
  const frozen = await call<{
    items: { snapshot: { classes: string[]; planId: string } }[];
  }>("GET", `/datasets/${dataset.id}`);
  assert.deepEqual(frozen.items[0]!.snapshot.classes, rules.classes);
  assert.equal(frozen.items[0]!.snapshot.planId, plan.id);
  await call(
    "POST",
    `/samples/${sample.id}/annotations`,
    { status: "COMPLETE", boxes: [] },
    engineer,
  );
  assert.equal(
    (await call<{ status: string }>("GET", `/samples/${sample.id}`)).status,
    "PENDING",
  );
  await call(
    "POST",
    "/deployments",
    { deviceId: device.id, modelId: "none" },
    operator,
    403,
  );
  await call(
    "POST",
    "/deployments",
    { deviceId: device.id, modelId: "none" },
    engineer,
    403,
  );
  await call("POST", "/deployments/none/rollback", {}, engineer, 403);
  await call(
    "POST",
    "/models/none/approve",
    { confirm: true, note: "no authority" },
    engineer,
    403,
  );
  await call(
    "POST",
    "/models/none/approve",
    { confirm: true, note: "no authority" },
    operator,
    403,
  );
});

test("command arbiter bounds concurrent work, serializes effects, cancels queued commands and only retries status reads", async () => {
  const device = await call<{ id: string }>("POST", "/devices", {
    name: "SIMULATED command test",
    serialNumber: randomUUID(),
    type: "SIMULATOR",
  });
  const { CommandsService } =
    await import("../../apps/server/src/devices/commands.service.js");
  const { Db } = await import("../../apps/server/src/core/db.js");
  const { DomainError } = await import("../../apps/server/src/core/errors.js");
  const commands = app.get(CommandsService),
    db = app.get(Db);
  let release: () => void = () => {},
    running = 0,
    peak = 0;
  const gate = new Promise<void>((r) => {
    release = r;
  });
  const work = Array.from({ length: 8 }, () =>
    commands.run(device.id, "TEST", randomUUID(), async () => {
      running++;
      peak = Math.max(peak, running);
      await gate;
      running--;
      return { done: true };
    }),
  );
  await assert.rejects(
    () =>
      commands.run(device.id, "TEST", randomUUID(), async () => ({
        done: false,
      })),
    /full/,
  );
  await waitFor(
    () => db.command.count({ where: { deviceId: device.id } }),
    (n) => n === 8,
  );
  await waitFor(
    () =>
      db.command.count({ where: { deviceId: device.id, status: "RUNNING" } }),
    (n) => n === 1,
  );
  const queued = await waitFor(
    () =>
      db.command.findFirst({
        where: { deviceId: device.id, status: "QUEUED" },
        orderBy: { createdAt: "desc" },
      }),
    (c) => c !== null,
  );
  assert.ok(queued);
  await call("POST", `/devices/${device.id}/commands/${queued.id}/cancel`, {});
  release();
  const settled = await Promise.allSettled(work);
  assert.equal(peak, 1);
  assert.equal(settled.filter((r) => r.status === "rejected").length, 1);
  let attempts = 0;
  await commands.run(device.id, "GET_STATUS", randomUUID(), async () => {
    if (++attempts === 1)
      throw new DomainError("DEVICE_TIMEOUT", "TEST timeout", 504);
    return { ok: true };
  });
  assert.equal(attempts, 2);
});
test("model import rejects mismatched weights without writing an orphan asset", async () => {
  const { simulatorManifest } =
    await import("../../apps/server/src/models/profile.js");
  const modelDir = resolve(output, "storage/models");
  mkdirSync(modelDir, { recursive: true });
  const before = (await readdir(modelDir)).sort();
  const boundary = "model-" + randomUUID(),
    metadata = {
      name: "SIMULATED invalid checksum fixture",
      version: randomUUID(),
      manifest: simulatorManifest(Buffer.from("expected fixture weights")),
    };
  const payload = Buffer.concat([
    Buffer.from(
      `--${boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n${JSON.stringify(metadata)}\r\n--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="invalid.bin"\r\nContent-Type: application/octet-stream\r\n\r\n`,
    ),
    Buffer.from("corrupted fixture weights"),
    Buffer.from(`\r\n--${boundary}--\r\n`),
  ]);
  const response = await app.inject({
    method: "POST",
    url: "/api/models/import",
    headers: {
      authorization: `Bearer ${engineer}`,
      "content-type": `multipart/form-data; boundary=${boundary}`,
    },
    payload,
  });
  assert.equal(response.statusCode, 422, response.body);
  assert.equal(response.json<{ code: string }>().code, "CHECKSUM_ERROR");
  assert.deepEqual((await readdir(modelDir)).sort(), before);
});

test("model import derives the manifest from a real model.bin", async (t) => {
  const fixture = resolve(
    "temporary/milk_model_import/board_model_20261017/model.bin",
  );
  if (!existsSync(fixture)) {
    t.skip("real model.bin fixture is unavailable");
    return;
  }
  const content = readFileSync(fixture);
  const classes = [
    "defect",
    "unused_1",
    "unused_2",
    "unused_3",
    "unused_4",
    "unused_5",
  ];
  const boundary = "model-" + randomUUID();
  const head = [
    `--${boundary}\r\nContent-Disposition: form-data; name="name"\r\n\r\nMilk defect\r\n`,
    `--${boundary}\r\nContent-Disposition: form-data; name="classes"\r\n\r\n${JSON.stringify(classes)}\r\n`,
    `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="model.bin"\r\nContent-Type: application/octet-stream\r\n\r\n`,
  ].join("");
  const payload = Buffer.concat([
    Buffer.from(head),
    content,
    Buffer.from(`\r\n--${boundary}--\r\n`),
  ]);
  const response = await app.inject({
    method: "POST",
    url: "/api/models/import",
    headers: {
      authorization: `Bearer ${engineer}`,
      "content-type": `multipart/form-data; boundary=${boundary}`,
    },
    payload,
  });
  assert.equal(response.statusCode, 201, response.body);
  const model = response.json<{
    version: string;
    manifest: { input: { channels: number }; classes: string[] };
  }>();
  assert.equal(model.version, "MILK-W8A8-20261017");
  assert.equal(model.manifest.input.channels, 1);
  assert.deepEqual(model.manifest.classes, classes);
});

test("overview withholds privileged counters from the operator and agrees with list counts", async () => {
  const admin = await call<{
    window: { from: string; to: string };
    inspections: {
      total: number;
      pass: number;
      fail: number;
      review: number;
      error: number;
    };
    pipeline: unknown;
    firmwareGaps: unknown;
  }>("GET", "/overview");
  const worker = await call<{
    inspections: typeof admin.inspections;
    pipeline: unknown;
    firmwareGaps: unknown;
  }>("GET", "/overview", undefined, operator);

  assert.equal(
    admin.inspections.total,
    admin.inspections.pass +
      admin.inspections.fail +
      admin.inspections.review +
      admin.inspections.error,
    "各结果分项之和应等于总数",
  );
  // 待办计数与固件缺口的数据源在 models/datasets/deployments 的类级 @Roles 后面，
  // 操作工点进去就是 403，所以总览必须返回 null 而不是先泄露一个数。
  assert.ok(admin.pipeline, "管理员应看到待办计数");
  assert.ok(admin.firmwareGaps, "管理员应看到固件缺口");
  assert.equal(worker.pipeline, null, "操作工不应看到待办计数");
  assert.equal(worker.firmwareGaps, null, "操作工不应看到固件缺口");
  assert.deepEqual(
    worker.inspections,
    admin.inspections,
    "产量计数对两个角色一致",
  );

  const window = `from=${encodeURIComponent(admin.window.from)}&to=${encodeURIComponent(admin.window.to)}`;
  const probe = await call<{ total: number }>(
    "GET",
    `/inspections?result=REVIEW&pageSize=1&${window}`,
  );
  assert.equal(
    admin.inspections.review,
    probe.total,
    "总览的待复核数应与同一时间窗的列表 total 一致",
  );
});
