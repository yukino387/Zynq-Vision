import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";

async function main() {
  const output = resolve(
    "temporary/task_permissions_20261018",
    `run-${Date.now()}`,
  );
  mkdirSync(output, { recursive: true });
  process.env.DATABASE_URL = `file:${resolve(output, "app.db").replaceAll("\\", "/")}`;
  process.env.STORAGE_ROOT = resolve(output, "storage");
  process.env.JWT_SECRET = "isolated-data-workflow-32-character-test-secret";
  process.env.ZYNQ_LOCAL_PORT = "15027";
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
  const tokens: Record<string, string> = {};
  const users: Record<string, string> = {};
  const password = "Data-Workflow-Test-2026!";
  for (const role of ["ADMIN", "ENGINEER", "OPERATOR"] as const) {
    const user = await db.user.create({
      data: {
        username: role.toLowerCase(),
        name: `隔离验证 ${role}`,
        role,
        passwordHash: await hash(password, 4),
      },
    });
    users[role] = user.id;
    const response = await app.inject({
      method: "POST",
      url: "/api/auth/login",
      payload: { username: role.toLowerCase(), password },
    });
    assert.equal(response.statusCode, 201);
    tokens[role] = response.json().token;
  }
  const checks: string[] = [];
  async function call(
    method: "GET" | "POST" | "DELETE",
    path: string,
    payload?: any,
    status = method === "POST" ? 201 : 200,
    role = "ADMIN",
  ) {
    const result = await app.inject({
      method,
      url: `/api${path}`,
      headers: { authorization: `Bearer ${tokens[role]}` },
      payload,
    });
    assert.equal(
      result.statusCode,
      status,
      `${method} ${path}: ${result.body}`,
    );
    return result.json();
  }
  const rules = {
    product: "饮品包装",
    purpose: "PRESENCE",
    classes: ["盒体", "吸管", "标签"],
    instructions: "将包装正面朝向镜头，分别框选盒体、吸管和标签。",
    conditions: "保持均匀光照",
    referenceUrl: "",
    coordinateSpace: "NORMALIZED_FRAME",
    region: { x: 0, y: 0, width: 1, height: 1 },
    checks: [{ classId: 0, min: 1, max: 1 }],
  };
  const plan = await db.inspectionPlan.create({
    data: { name: "包装完整性", version: 1, rules },
  });
  const otherPlan = await db.inspectionPlan.create({
    data: {
      name: "其他产品",
      version: 1,
      rules: { ...rules, product: "配件", classes: ["螺丝"] },
    },
  });
  const task = await db.task.create({
    data: { name: "饮品包装采样", target: 100, planId: plan.id },
  });
  const otherTask = await db.task.create({
    data: { name: "配件采样", target: 20, planId: otherPlan.id },
  });
  const independent = await db.task.create({
    data: { name: "独立采样", target: 20 },
  });
  const simulatedPlan = await db.inspectionPlan.create({
    data: {
      name: "旧模拟方案",
      version: 1,
      rules: { source: "SIMULATION", defectThreshold: 0.5 },
    },
  });
  await db.task.create({
    data: { name: "旧模拟任务", target: 10, planId: simulatedPlan.id },
  });
  const legacyPlan = await db.inspectionPlan.create({
    data: {
      name: "未配置类别的旧方案",
      version: 1,
      rules: { product: "旧产品" },
    },
  });
  await db.task.create({
    data: { name: "旧任务（缺少类别）", target: 10, planId: legacyPlan.id },
  });
  const image = await sharp(
    Buffer.from(
      '<svg width="416" height="416"><rect width="416" height="416" fill="#d2d9df"/><rect x="95" y="65" width="190" height="295" rx="12" fill="#486f98"/><path d="M95 65 L140 30 H255 L285 65" fill="#ecede1"/><rect x="125" y="130" width="130" height="90" rx="4" fill="#faf7e7"/><text x="139" y="185" font-size="32" fill="#486f98">MILK</text><rect x="310" y="85" width="14" height="240" rx="6" fill="#f3c95b"/><rect x="325" y="85" width="8" height="65" fill="#f3c95b"/></svg>',
    ),
  )
    .png()
    .toBuffer();
  writeFileSync(
    resolve("temporary/task_permissions_20261018/import-fixture.png"),
    image,
  );
  writeFileSync(
    resolve("temporary/task_permissions_20261018/invalid-fixture.png"),
    "invalid image fixture",
  );
  const samples: any[] = [];
  for (let i = 0; i < 55; i++) {
    const source =
      i === 54
        ? "SIMULATION"
        : i % 3 === 0
          ? "BOARD"
          : i % 3 === 1
            ? "MOBILE"
            : "IMPORT";
    const stored = await assets.store(
      image,
      "PREVIEW",
      source,
      `包装-${i}.png`,
      "image/png",
      416,
      416,
    );
    const sample = await db.sample.create({
      data: {
        name:
          i === 53
            ? "待关联任务图片"
            : `包装采样 ${String(i + 1).padStart(3, "0")}`,
        source,
        clientId: "data-workflow-test",
        idempotencyKey: `data-workflow-${i}`,
        localSequence: i,
        capturedAt: new Date(),
        createdAt: new Date(Date.now() - i * 1000),
        taskId: i === 53 ? null : task.id,
        assets: { create: stored },
      },
    });
    samples.push(sample);
  }
  const box = {
    classId: 1,
    label: "吸管",
    confidence: 1,
    x1: 310,
    y1: 85,
    x2: 335,
    y2: 326,
  };
  await call("POST", `/samples/${samples[52].id}/annotations`, {
    status: "COMPLETE",
    boxes: [box],
  });
  await call("POST", `/samples/${samples[52].id}/review`, {
    verdict: "ACCEPT",
    note: "包装完整，可用于训练",
    hard: false,
  });
  const orphan = samples[53];
  await call(
    "POST",
    `/samples/${orphan.id}/task`,
    { taskId: independent.id },
    409,
  );
  await call(
    "POST",
    `/samples/${orphan.id}/task`,
    { taskId: task.id },
    201,
    "ENGINEER",
  );
  assert.equal(
    (await call("GET", `/samples/${orphan.id}`)).task.plan.id,
    plan.id,
  );
  await call(
    "POST",
    `/samples/${samples[52].id}/task`,
    { taskId: otherTask.id },
    409,
  );
  await call(
    "POST",
    `/samples/${samples[1].id}/task`,
    { taskId: task.id },
    403,
    "OPERATOR",
  );
  await db.sample.update({ where: { id: orphan.id }, data: { taskId: null } });
  checks.push(
    "assign existing images to tasks; reject missing plans and incompatible annotated classes; enforce roles",
  );
  const source = await call(
    "GET",
    `/samples?source=BOARD&taskId=${task.id}&pageSize=100`,
  );
  assert(
    source.items.every(
      (r: any) => r.source === "BOARD" && r.taskId === task.id,
    ),
  );
  const pending = await call(
    "GET",
    "/samples?realOnly=true&annotation=pending&pageSize=100",
  );
  const complete = await call(
    "GET",
    "/samples?realOnly=true&annotation=complete&pageSize=100",
  );
  assert.equal(pending.total, 53);
  assert.equal(complete.total, 1);
  checks.push("combine source/task/annotation filters");
  for (const verdict of ["NEEDS_WORK", "REJECT", "ACCEPT"])
    await call("POST", `/samples/${samples[51].id}/review`, {
      verdict,
      note: `审核意见 ${verdict}`,
      hard: false,
    });
  assert.equal(
    (await call("GET", `/samples/${samples[51].id}`)).reviews[0].verdict,
    "ACCEPT",
  );
  await call(
    "POST",
    `/samples/${samples[51].id}/review`,
    { verdict: "ACCEPT", note: "", hard: false },
    403,
    "ENGINEER",
  );
  checks.push("review outcomes, visible latest note, admin-only review");
  const makeDataset = async (name: string) => {
    const dataset = await call("POST", "/datasets", { name, version: 1 });
    await call("POST", `/datasets/${dataset.id}/items`, {
      sampleIds: [samples[52].id],
    });
    return dataset;
  };
  const disposable = await makeDataset("可删除的草稿数据集");
  await call("DELETE", `/datasets/${disposable.id}`, { confirm: false }, 400);
  await call(
    "DELETE",
    `/datasets/${disposable.id}`,
    { confirm: true },
    403,
    "OPERATOR",
  );
  await call(
    "DELETE",
    `/datasets/${disposable.id}`,
    { confirm: true },
    200,
    "ENGINEER",
  );
  assert.equal(
    await db.datasetItem.count({ where: { datasetId: disposable.id } }),
    0,
  );
  assert.equal(
    await db.sample.count({ where: { id: samples[52].id, deletedAt: null } }),
    1,
  );
  const frozen = await makeDataset("可删除的未使用冻结版本");
  await call("POST", `/datasets/${frozen.id}/freeze`);
  await call("DELETE", `/datasets/${frozen.id}`, { confirm: true });
  checks.push(
    "delete draft and unused frozen datasets, preserve original images, require confirmation and roles",
  );
  const used = await makeDataset("已用于训练的数据集");
  await db.trainingJob.create({
    data: { name: "保留训练历史", datasetId: used.id, status: "COMPLETED" },
  });
  await call("DELETE", `/datasets/${used.id}`, { confirm: true }, 409);
  assert.equal(
    await db.datasetItem.count({ where: { datasetId: used.id } }),
    1,
  );
  checks.push(
    "reject deletion of datasets used by training without removing their items",
  );
  const evaluated = await makeDataset("已用于评估的数据集");
  const model = await db.model.create({
    data: {
      name: "验证模型",
      version: "1",
      architecture: "TEST",
      manifest: {},
      source: "SIMULATION",
    },
  });
  const device = await db.device.create({
    data: {
      name: "隔离验证设备",
      serialNumber: "DATA-WORKFLOW-TEST",
      type: "SIMULATOR",
      capabilities: {},
    },
  });
  await db.benchmark.create({
    data: {
      name: "保留评估历史",
      modelId: model.id,
      datasetId: evaluated.id,
      deviceId: device.id,
      source: "SIMULATION",
      metrics: {},
    },
  });
  await call("DELETE", `/datasets/${evaluated.id}`, { confirm: true }, 409);
  assert.equal(
    await db.datasetItem.count({ where: { datasetId: evaluated.id } }),
    1,
  );
  checks.push(
    "reject deletion of datasets used by evaluation without removing their items",
  );
  const exportDataset = await makeDataset("正在导出的数据集");
  await db.job.create({
    data: {
      type: "DATASET_EXPORT",
      entityId: exportDataset.id,
      status: "RUNNING",
      payload: { datasetId: exportDataset.id },
    },
  });
  await call("DELETE", `/datasets/${exportDataset.id}`, { confirm: true }, 409);
  await db.job.updateMany({
    where: { entityId: exportDataset.id },
    data: { status: "COMPLETED" },
  });
  checks.push("reject deletion while export is running");
  const deleteSample = await db.sample.create({
    data: {
      name: "API删除验证",
      source: "IMPORT",
      clientId: "delete-test",
      localSequence: 0,
      idempotencyKey: "delete-test-sample",
      capturedAt: new Date(),
    },
  });
  await call(
    "DELETE",
    `/samples/${deleteSample.id}`,
    { confirm: true },
    403,
    "OPERATOR",
  );
  await call("DELETE", `/samples/${deleteSample.id}`, { confirm: true });
  await call("GET", `/samples/${deleteSample.id}`, undefined, 404);
  assert(
    (await db.sample.findUniqueOrThrow({ where: { id: deleteSample.id } }))
      .deletedAt,
  );
  checks.push("delete samples from library through existing soft-delete API");
  const realTasks = await call("GET", "/tasks?realOnly=true&pageSize=100");
  assert(!realTasks.items.some((row: any) => row.name === "旧模拟任务"));
  assert(realTasks.items.some((row: any) => row.name === "旧任务（缺少类别）"));
  assert(realTasks.items.some((row: any) => row.id === independent.id));
  const simulationOnly = await call("POST", "/datasets", {
    name: "旧模拟数据集",
    version: 1,
  });
  await call("POST", `/samples/${samples[54].id}/annotations`, {
    status: "COMPLETE",
    boxes: [box],
  });
  await call("POST", `/datasets/${simulationOnly.id}/items`, {
    sampleIds: [samples[54].id],
  });
  assert(
    !(await call("GET", "/datasets?realOnly=true&pageSize=100")).items.some(
      (row: any) => row.id === simulationOnly.id,
    ),
  );
  assert.equal(
    (await call("GET", "/models?realOnly=true&pageSize=100")).total,
    0,
  );
  checks.push(
    "daily task, sample, dataset and model queries exclude simulation fixtures while tolerating legacy tasks without classes",
  );
  await makeDataset("界面删除验证数据集");
  const { SamplesService } = await import("../../apps/server/src/samples/samples.service.js");
  const samplesService = app.get(SamplesService);
  const removableTask = await call("POST", "/tasks", {
    name: "管理员删除任务验证", target: 20, planId: plan.id,
  });
  const uploadDto = {
    source: "IMPORT" as const, taskId: removableTask.id,
    idempotencyKey: "task-delete-original", clientId: "task-delete-test",
    localSequence: 1, capturedAt: new Date().toISOString(), metadata: {},
  };
  const retained = await samplesService.upload(uploadDto, image, "保留图片.png", "image/png", users.ADMIN!);
  await call("POST", `/samples/${retained.id}/annotations`, { status: "COMPLETE", boxes: [box] });
  await call("POST", `/samples/${retained.id}/review`, { verdict: "ACCEPT", note: "删除任务后仍需保留", hard: false });
  const retainedDataset = await call("POST", "/datasets", { name: "删除任务后保留数据集", version: 1 });
  await call("POST", `/datasets/${retainedDataset.id}/items`, { sampleIds: [retained.id] });
  await call("POST", `/datasets/${retainedDataset.id}/freeze`);
  const retainedInspection = await db.inspection.create({ data: {
    sampleId: retained.id, taskId: removableTask.id, deviceId: device.id,
    source: "IMPORT", result: "REVIEW", status: "COMPLETED", reason: "LOW_CONFIDENCE",
    startedAt: new Date(), completedAt: new Date(),
  } });
  for (const role of ["ENGINEER", "OPERATOR"])
    await call("DELETE", `/tasks/${removableTask.id}`, { confirm: true }, 403, role);
  await call("DELETE", `/tasks/${removableTask.id}`, { confirm: false }, 400);
  assert.equal((await call("GET", `/tasks/${removableTask.id}`)).status, "OPEN");
  await call("DELETE", `/tasks/${removableTask.id}`, { confirm: true });
  await call("GET", `/tasks/${removableTask.id}`, undefined, 404);
  await call("DELETE", `/tasks/${removableTask.id}`, { confirm: true });
  for (const query of ["", "?realOnly=true", "?status=DELETED", "?search=管理员删除任务验证", "?realOnly=true&status=DELETED"])
    assert(!(await call("GET", `/tasks${query}`)).items.some((r: any) => r.id === removableTask.id));
  const retainedDetail = await call("GET", `/samples/${retained.id}`);
  assert.equal(retainedDetail.task.plan.id, plan.id);
  assert.equal(retainedDetail.annotations[0].boxes[0].label, "吸管");
  assert.equal((await call("GET", `/datasets/${retainedDataset.id}`)).items.length, 1);
  assert.equal((await db.inspection.findUniqueOrThrow({ where: { id: retainedInspection.id } })).taskId, removableTask.id);
  assert.equal(await db.captureSession.count({ where: { taskId: removableTask.id } }), 1);
  await call("POST", `/samples/${samples[0].id}/task`, { taskId: removableTask.id }, 404);
  await call("POST", "/samples/capture", {
    deviceId: device.id, taskId: removableTask.id, idempotencyKey: "deleted-task-capture",
    clientId: "task-delete-test", localSequence: 2,
  }, 404);
  await assert.rejects(samplesService.upload({ ...uploadDto, idempotencyKey: "deleted-task-upload", localSequence: 3 }, image, "禁止新增.png", "image/png", users.ADMIN!), (error: any) => error.code === "P2025");
  assert.equal(await db.sample.count({ where: { taskId: removableTask.id } }), 1);
  // Existing sample annotations remain usable, with the original plan's class validation.
  await call("POST", `/samples/${retained.id}/annotations`, { status: "DRAFT", boxes: [box] });
  checks.push("admin-only task deletion with confirmation; all filters hide deleted tasks; preserve samples, labels, frozen dataset and inspection/session history; reject new uploads, capture and assignment");
  writeFileSync(
    resolve(output, "api-results.json"),
    JSON.stringify({ ok: true, checks }, null, 2),
  );
  console.log(JSON.stringify({ ok: true, checks, output }));
  if (process.argv.includes("--test-only")) {
    await app.close();
    return;
  }
  const { DevicesService } =
    await import("../../apps/server/src/devices/devices.service.js");
  await app.get(DevicesService).attach(device.id);
  await db.model.update({
    where: { id: model.id },
    data: { source: "IMPORT" },
  });
  await db.inspection.create({
    data: {
      sampleId: samples[0].id,
      deviceId: device.id,
      source: "BOARD",
      result: "REVIEW",
      status: "COMPLETED",
      reason: "LOW_CONFIDENCE",
      startedAt: new Date(),
      completedAt: new Date(),
    },
  });
  const firmwareAsset = await db.asset.create({
    data: await assets.store(
      Buffer.from("UI TEST ONLY"),
      "FIRMWARE_PACKAGE",
      "SIMULATION",
      "ui-test.bin",
      "application/octet-stream",
    ),
  });
  await db.firmware.create({
    data: {
      name: "仅界面验证固件",
      version: "ui-test-1",
      sha256: firmwareAsset.sha256,
      size: 12,
      imageSize: 12,
      entry: 1048576,
      segments: [],
      assetId: firmwareAsset.id,
      notes: "仅用于界面验证，不可部署",
    },
  });
  await app.listen(3027, "127.0.0.1");
  const { createServer } =
    await import("../../apps/web/node_modules/vite/dist/node/index.js");
  const { default: config } = await import("../../apps/web/vite.config.ts");
  const vite = await createServer({
    ...config,
    configFile: false,
    root: resolve("apps/web"),
    server: {
      host: "127.0.0.1",
      port: 5187,
      strictPort: true,
      proxy: {
        "/api": "http://127.0.0.1:3027",
        "/ws": { target: "ws://127.0.0.1:3027", ws: true },
      },
    },
  });
  await vite.listen();
  console.log(
    "Isolated UI ready: http://127.0.0.1:5187/#/data/samples (admin / Data-Workflow-Test-2026!)",
  );
  writeFileSync(
    resolve("temporary/task_permissions_20261018/test-server.pid"),
    String(process.pid),
  );
  process.on(
    "SIGINT",
    () =>
      void Promise.all([vite.close(), app.close()]).then(() => process.exit(0)),
  );
}
void main().catch((error) => {
  console.error(error);
  process.exit(1);
});

