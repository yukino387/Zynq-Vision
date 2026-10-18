import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
const output = resolve(
  "temporary/frontend_workflow_20261016",
  `run-${Date.now()}`,
);
mkdirSync(output, { recursive: true });
process.env.DATABASE_URL = `file:${resolve(output, "app.db").replaceAll("\\", "/")}`;
process.env.JWT_SECRET = "registration-test-secret-never-use-in-production";
process.env.STORAGE_ROOT = resolve(output, "storage");
let app: Awaited<
  ReturnType<(typeof import("../../apps/server/src/bootstrap.js"))["createApp"]>
>;
let db: InstanceType<(typeof import("../../apps/server/src/core/db.js"))["Db"]>;
let admin = "",
  operator = "",
  adminId = "";
const password = "Registration-Test-2026!";
async function call(
  method: "GET" | "POST" | "PATCH",
  path: string,
  body?: unknown,
  token = admin,
  expected = method === "POST" ? 201 : 200,
) {
  const r = await app.inject({
    method,
    url: `/api${path}`,
    headers: token ? { authorization: `Bearer ${token}` } : {},
    payload: body as Record<string, unknown>,
  });
  assert.equal(r.statusCode, expected, r.body);
  return r.json();
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
  const { hash } =
    await import("../../apps/server/node_modules/bcryptjs/index.js");
  app = await createApp(false);
  db = app.get(Db);
  const user = await db.user.create({
    data: {
      username: "admin",
      name: "测试管理员",
      role: "ADMIN",
      passwordHash: await hash(password, 4),
    },
  });
  adminId = user.id;
  admin = (
    await call("POST", "/auth/login", { username: "admin", password }, "")
  ).token;
});
after(async () => {
  await app?.close();
});
test("registration codes: hash storage, verify, consume once, fixed operator role, safe list and audit", async () => {
  const issued = await call("POST", "/registration-codes", {
    label: "一号工位",
    days: 3,
  });
  assert.ok(issued.code.startsWith("VSN-"));
  assert.equal(issued.codeHash, undefined);
  const stored = await db.registrationCode.findUniqueOrThrow({
    where: { id: issued.id },
  });
  assert.equal(
    stored.codeHash,
    createHash("sha256").update(issued.code).digest("hex"),
  );
  await call(
    "POST",
    "/auth/registration/verify",
    { code: issued.code.toLowerCase() },
    "",
  );
  await call(
    "POST",
    "/auth/register",
    {
      code: issued.code,
      name: "越权测试",
      username: "privilege",
      password,
      role: "ADMIN",
    },
    "",
    400,
  );
  const result = await call(
    "POST",
    "/auth/register",
    { code: issued.code, name: "现场操作员", username: "operator01", password },
    "",
  );
  assert.equal(result.user.role, "OPERATOR");
  assert.equal(result.user.passwordHash, undefined);
  operator = result.token;
  await call("GET", "/registration-codes", undefined, operator, 403);
  await call(
    "POST",
    "/registration-codes",
    { label: "越权签发" },
    operator,
    403,
  );
  await call(
    "POST",
    "/auth/register",
    { code: issued.code, name: "重复账号", username: "operator02", password },
    "",
    400,
  );
  const listing = await call("GET", "/registration-codes?page=1&pageSize=20");
  assert.equal(listing.total, 1);
  assert.ok(listing.items[0].usedAt);
  assert.equal(listing.items[0].code, undefined);
  assert.equal(listing.items[0].codeHash, undefined);
  assert.equal(
    await db.auditLog.count({
      where: { action: "REGISTER", userId: result.user.id },
    }),
    1,
  );
});
test("expired/revoked codes reject; duplicate username rolls code consumption back", async () => {
  const expired = await call("POST", "/registration-codes", {
    label: "过期码",
  });
  await db.registrationCode.update({
    where: { id: expired.id },
    data: { expiresAt: new Date(0) },
  });
  await call(
    "POST",
    "/auth/registration/verify",
    { code: expired.code },
    "",
    400,
  );
  const revoked = await call("POST", "/registration-codes", {
    label: "撤销码",
  });
  await call("PATCH", `/registration-codes/${revoked.id}/revoke`);
  await call(
    "POST",
    "/auth/register",
    { code: revoked.code, name: "测试", username: "revoked", password },
    "",
    400,
  );
  const valid = await call("POST", "/registration-codes", { label: "有效码" });
  await call(
    "POST",
    "/auth/register",
    { code: valid.code, name: "重名", username: "admin", password },
    "",
    409,
  );
  assert.equal(
    (await db.registrationCode.findUniqueOrThrow({ where: { id: valid.id } }))
      .usedAt,
    null,
  );
  await call(
    "POST",
    "/auth/register",
    { code: valid.code, name: "注册成功", username: "newuser", password },
    "",
  );
});
test("simultaneous claims create exactly one account; current administrator cannot lock themselves out", async () => {
  const issued = await call("POST", "/registration-codes", { label: "并发码" });
  const responses = await Promise.all(
    ["concurrent1", "concurrent2"].map((username) =>
      app.inject({
        method: "POST",
        url: "/api/auth/register",
        payload: { code: issued.code, name: username, username, password },
      }),
    ),
  );
  assert.equal(responses.filter((r) => r.statusCode === 201).length, 1);
  assert.equal(
    await db.user.count({ where: { username: { startsWith: "concurrent" } } }),
    1,
  );
  await call("PATCH", `/users/${adminId}`, { disabled: true }, admin, 409);
  assert.equal(
    (await db.user.findUniqueOrThrow({ where: { id: adminId } })).disabled,
    false,
  );
});
test("review completion removes an inspection from pending queue without rewriting its original result", async () => {
  const device = await db.device.create({
    data: {
      name: "测试设备",
      serialNumber: "TEST-QUEUE",
      type: "SIMULATOR",
      capabilities: {},
    },
  });
  const {DevicesService} = await import('../../apps/server/src/devices/devices.service.js');
  await app.get(DevicesService).attach(device.id);
  const sample = await db.sample.create({
    data: {
      name: "待审核样本",
      source: "SIMULATION",
      clientId: "queue-test",
      idempotencyKey: "queue-test",
      capturedAt: new Date(),
    },
  });
  const inspection = await db.inspection.create({
    data: {
      sampleId: sample.id,
      deviceId: device.id,
      source: "SIMULATION",
      result: "REVIEW",
      status: "COMPLETED",
      reason: "test",
      startedAt: new Date(),
      completedAt: new Date(),
    },
  });
  const pending = await call(
    "GET",
    "/inspections?result=REVIEW&reviewed=false",
  );
  assert.ok(pending.items.some((r: { id: string }) => r.id === inspection.id));
  await call("POST", "/reviews", {
    inspectionId: inspection.id,
    verdict: "CORRECT",
    note: "已确认",
    hard: false,
  });
  const after = await call("GET", "/inspections?result=REVIEW&reviewed=false");
  assert.ok(!after.items.some((r: { id: string }) => r.id === inspection.id));
  assert.equal(
    (await db.inspection.findUniqueOrThrow({ where: { id: inspection.id } }))
      .result,
    "REVIEW",
  );
});
test("sample review queue counts pending and incomplete samples before pagination, excluding rejected samples", async () => {
  for (const status of ["PENDING", "NEEDS_WORK", "REJECTED"])
    await db.sample.create({
      data: {
        name: status,
        source: "SIMULATION",
        clientId: `sample-queue-${status}`,
        idempotencyKey: `sample-queue-${status}`,
        capturedAt: new Date(),
        status,
      },
    });
  const result = await call("GET", "/samples?reviewed=false&pageSize=1");
  assert.equal(result.total, 2);
  assert.equal(result.items.length, 1);
  const all = await call("GET", "/samples?reviewed=false&pageSize=20");
  assert.ok(
    all.items.every((row: { status: string }) =>
      ["PENDING", "NEEDS_WORK"].includes(row.status),
    ),
  );
});
