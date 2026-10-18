import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";

async function main() {
  const output = resolve("temporary/plan_roles_20261018", `run-${Date.now()}`);
  mkdirSync(output, { recursive: true });
  process.env.DATABASE_URL = `file:${resolve(output, "app.db").replaceAll("\\", "/")}`;
  process.env.STORAGE_ROOT = resolve(output, "storage");
  process.env.JWT_SECRET = "plan-roles-isolated-32-character-test-secret";
  process.env.ZYNQ_LOCAL_PORT = "15030";
  execFileSync(process.execPath, [resolve("apps/server/node_modules/prisma/build/index.js"), "migrate", "deploy", "--schema", resolve("apps/server/prisma/schema.prisma")], { env: process.env, stdio: "pipe" });
  const { createApp } = await import("../../apps/server/src/bootstrap.js");
  const { Db } = await import("../../apps/server/src/core/db.js");
  const { SamplesService } = await import("../../apps/server/src/samples/samples.service.js");
  const { hash } = await import("../../apps/server/node_modules/bcryptjs/index.js");
  const { default: sharp } = await import("../../apps/server/node_modules/sharp/lib/index.js");
  const app = await createApp(false), db = app.get(Db);
  const tokens: Record<string,string> = {}, users: Record<string,string> = {};
  const password = "Plan-Roles-Test-2026!";
  for (const role of ["ADMIN", "ENGINEER", "OPERATOR"] as const) {
    const user = await db.user.create({ data: { username: role.toLowerCase(), name: `权限验证 ${role}`, role, passwordHash: await hash(password, 4) } });
    users[role] = user.id;
    const result = await app.inject({ method: "POST", url: "/api/auth/login", payload: { username: role.toLowerCase(), password } });
    assert.equal(result.statusCode, 201); tokens[role] = result.json().token;
  }
  const checks: string[] = [];
  async function call(method: "GET"|"POST"|"PATCH"|"DELETE", path: string, payload?: any, role="ADMIN", status=method === "POST" ? 201 : 200) {
    const result = await app.inject({ method, url: `/api${path}`, headers: { authorization: `Bearer ${tokens[role]}` }, payload });
    assert.equal(result.statusCode, status, `${role} ${method} ${path}: ${result.body}`);
    return result.json();
  }
  const rules = { product: "饮品包装", purpose: "PRESENCE", classes: ["盒体", "吸管"], instructions: "包装正面朝向摄像头", conditions: "保持均匀光照", referenceUrl: "", coordinateSpace: "NORMALIZED_FRAME", region: { x: 0, y: 0, width: 1, height: 1 }, checks: [{ classId: 0, min: 1, max: 1 }, { classId: 1, min: 1, max: 1 }] };
  for (const role of ["ENGINEER", "OPERATOR"]) {
    await call("POST", "/plans", { name: "越权方案", rules }, role, 403);
    await call("POST", "/tasks", { name: "越权任务", target: 10 }, role, 403);
    for (const path of ["/users", "/audit"])
      await call("GET", path, undefined, role, 403);
    for (const path of ["/models/missing/approve", "/deployments", "/deployments/missing/rollback", "/firmware/upload", "/firmware/missing/deploy", "/firmware-deployments/missing/rollback"])
      await call("POST", path, {}, role, 403);
  }
  await call("GET", "/plans", undefined, "ENGINEER");
  await call("GET", "/plans", undefined, "OPERATOR", 403);
  const plan = await call("POST", "/plans", { name: "可删除方案", rules });
  const task = await call("POST", "/tasks", { name: "保留历史任务", target: 10, planId: plan.id });
  for (const role of ["ENGINEER", "OPERATOR"]) {
    await call("PATCH", `/tasks/${task.id}`, { name: "越权修改", target: 20, status: "OPEN" }, role, 403);
    await call("DELETE", `/tasks/${task.id}`, { confirm: true }, role, 403);
    await call("DELETE", `/plans/${plan.id}`, { confirm: true }, role, 403);
  }
  await call("PATCH", `/tasks/${task.id}`, { name: "保留历史任务", target: 20, status: "OPEN" });
  await call("GET", `/tasks/${task.id}`, undefined, "OPERATOR");
  const image = await sharp({ create: { width: 128, height: 128, channels: 3, background: "#7d9b83" } }).png().toBuffer();
  const sample = await app.get(SamplesService).upload({ source: "IMPORT", taskId: task.id, idempotencyKey: "plan-roles-sample", clientId: "plan-roles-test", localSequence: 1, capturedAt: new Date().toISOString(), metadata: {} }, image, "方案历史样本.png", "image/png", users.ADMIN!);
  const box = { classId: 0, label: "盒体", confidence: 1, x1: 10, y1: 10, x2: 100, y2: 110 };
  await call("POST", `/samples/${sample.id}/annotations`, { status: "COMPLETE", boxes: [box] }, "ENGINEER");
  for (const role of ["ENGINEER", "OPERATOR"]) {
    await call("POST", `/samples/${sample.id}/review`, { verdict: "ACCEPT" }, role, 403);
    await call("DELETE", `/samples/${sample.id}`, { confirm: true }, role, 403);
  }
  await call("POST", `/samples/${sample.id}/annotations`, { status: "COMPLETE", boxes: [box] }, "OPERATOR", 403);
  await call("POST", `/samples/${sample.id}/process`, {}, "ENGINEER");
  await call("POST", `/samples/${sample.id}/review`, { verdict: "ACCEPT" });
  const dataset = await call("POST", "/datasets", { name: "保留方案快照", version: 1 }, "ENGINEER");
  await call("POST", `/datasets/${dataset.id}/items`, { sampleIds: [sample.id] }, "ENGINEER");
  await call("DELETE", `/datasets/${dataset.id}/items/${sample.id}`, undefined, "ENGINEER");
  await call("POST", `/datasets/${dataset.id}/items`, { sampleIds: [sample.id] }, "ENGINEER");
  await call("POST", `/datasets/${dataset.id}/freeze`, {}, "ENGINEER", 403);
  await call("POST", `/datasets/${dataset.id}/freeze`);
  const frozen = await call("GET", `/datasets/${dataset.id}`);
  await call("DELETE", `/plans/${plan.id}`, { confirm: false }, "ADMIN", 400);
  assert.equal((await call("GET", "/plans")).total, 1);
  await call("DELETE", `/plans/${plan.id}`, { confirm: true });
  await call("DELETE", `/plans/${plan.id}`, { confirm: true });
  assert.equal((await call("GET", "/plans")).total, 0);
  assert.equal((await call("GET", "/plans?search=可删除方案")).total, 0);
  assert.equal((await call("GET", `/tasks/${task.id}`, undefined, "OPERATOR")).plan.id, plan.id);
  assert.equal((await call("GET", `/samples/${sample.id}`)).task.plan.rules.classes[0], "盒体");
  assert.equal((await call("GET", `/datasets/${dataset.id}`)).checksum, frozen.checksum);
  await call("POST", "/tasks", { name: "不能使用已删除版本", target: 10, planId: plan.id }, "ADMIN", 404);
  await call("POST", `/samples/${sample.id}/annotations`, { status: "DRAFT", boxes: [box] }, "ENGINEER");
  const replacement = await call("POST", "/plans", { name: "可删除方案", rules });
  assert.equal(replacement.version, 2);
  assert.equal((await call("GET", "/plans")).total, 1);
  const disposableDataset = await call("POST", "/datasets", { name: "管理员可删除", version: 1 });
  for (const role of ["ENGINEER", "OPERATOR"]) await call("DELETE", `/datasets/${disposableDataset.id}`, { confirm: true }, role, 403);
  await call("DELETE", `/datasets/${disposableDataset.id}`, { confirm: true });
  for (const role of ["ADMIN", "ENGINEER", "OPERATOR"]) {
    await call("POST", "/samples/capture", {}, role, 400);
    await call("POST", "/reviews", {}, role, 400);
  }
  await call("POST", "/trainings", {}, "ENGINEER", 400);
  await call("POST", "/trainings", {}, "OPERATOR", 403);
  await call("GET", "/datasets", undefined, "OPERATOR", 403);
  await call("POST", `/devices/missing/connect`, {}, "OPERATOR", 403);
  for (const role of ["ENGINEER", "OPERATOR"])
    await call("PATCH", "/devices/missing/desired", { planVersion: "V9" }, role, 403);
  await call("POST", "/devices/missing/commands", { type: "SET_PLAN", value: "V9" }, "ENGINEER", 403);
  const disposableSample = await db.sample.create({ data: { name: "管理员删除验证", source: "IMPORT", clientId: "delete-role-test", idempotencyKey: "delete-role-test", localSequence: 0, capturedAt: new Date() } });
  await call("DELETE", `/samples/${disposableSample.id}`, { confirm: true });
  await call("GET", `/samples/${disposableSample.id}`, undefined, "ADMIN", 404);
  checks.push("admin exclusively manages plan/task/source-data deletion, review, freeze, users, publication, rollback and firmware changes", "engineer can read plans, annotate/process quality, curate draft datasets and access training; operator can sample and submit feedback", "plan deletion requires confirmation, hides list/search and blocks new tasks while preserving task/sample/frozen snapshot references", "deleted version numbers are never reused; old plan annotations remain usable");
  writeFileSync(resolve(output, "results.json"), JSON.stringify({ ok: true, checks }, null, 2));
  console.log(JSON.stringify({ ok: true, checks, output }));
  if (process.argv.includes("--test-only")) { await app.close(); return; }
  await app.listen(3030, "127.0.0.1");
  const { createServer } = await import("../../apps/web/node_modules/vite/dist/node/index.js");
  const { default: config } = await import("../../apps/web/vite.config.ts");
  const vite = await createServer({ ...config, configFile: false, root: resolve("apps/web"), server: { host: "127.0.0.1", port: 5190, strictPort: true, proxy: { "/api": "http://127.0.0.1:3030", "/ws": { target: "ws://127.0.0.1:3030", ws: true } } } });
  await vite.listen();
  console.log("Plan role UI ready: http://127.0.0.1:5190/#/plans");
  process.on("SIGINT", () => void Promise.all([vite.close(), app.close()]).then(() => process.exit(0)));
}
void main().catch((error) => { console.error(error); process.exit(1); });
