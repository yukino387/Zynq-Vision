import "reflect-metadata";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { hash } from "../../apps/server/node_modules/bcryptjs/index.js";
import { WebSocket } from "../../apps/server/node_modules/ws/index.js";
import { JwtService } from "../../apps/server/node_modules/@nestjs/jwt/dist/index.js";
const out = resolve("temporary/account_settings_20261018", `test-${Date.now()}`);
mkdirSync(out, { recursive: true });
process.env.DATABASE_URL = `file:${resolve(out, "account.db").replaceAll("\\", "/")}`;
process.env.JWT_SECRET = "isolated-account-test-secret-at-least-32-characters";
process.env.STORAGE_ROOT = resolve(out, "storage");
process.env.WS_PATH = "/account-test-ws";
const oldPassword = "Account-Test-Old-2026!", newPassword = "Account-Test-New-2026!";
let app: Awaited<ReturnType<(typeof import("../../apps/server/src/bootstrap.js"))["createApp"]>>;
let db: import("../../apps/server/src/core/db.js").Db;
let operatorId = "", admin = "", operator = "", engineer = "", address = "";
async function request(method: "GET" | "POST" | "PATCH", path: string, token = "", body?: unknown, status = method === "POST" ? 201 : 200) {
  const response = await app.inject({ method, url: `/api${path}`, headers: token ? { authorization: `Bearer ${token}` } : {}, payload: body as Record<string, unknown> | undefined });
  assert.equal(response.statusCode, status, `${method} ${path}: ${response.body}`);
  return response.json();
}
async function login(username: string, password = oldPassword, status = 201) {
  return request("POST", "/auth/login", "", { username, password }, status);
}
async function socket(token: string) {
  const ws = new WebSocket(`${address}/account-test-ws`);
  await new Promise<void>((done, fail) => {
    const timer = setTimeout(() => fail(new Error("WebSocket authentication timed out")), 3000);
    ws.once("open", () => ws.send(JSON.stringify({ token })));
    ws.once("message", (raw) => { clearTimeout(timer); assert.equal(JSON.parse(String(raw)).type, "session.ready"); done(); });
    ws.once("error", fail);
  });
  return ws;
}
before(async () => {
  execFileSync(process.execPath, [resolve("apps/server/node_modules/prisma/build/index.js"), "migrate", "deploy", "--schema", resolve("apps/server/prisma/schema.prisma")], { env: process.env, stdio: "pipe" });
  const { createApp } = await import("../../apps/server/src/bootstrap.js");
  const { Db } = await import("../../apps/server/src/core/db.js");
  app = await createApp(false);
  db = app.get(Db);
  for (const role of ["ADMIN", "ENGINEER", "OPERATOR"] as const) {
    const user = await db.user.create({ data: { username: role.toLowerCase(), name: `TEST ${role}`, role, passwordHash: await hash(oldPassword, 4) } });
    if (role === "OPERATOR") operatorId = user.id;
  }
  admin = (await login("admin")).token;
  operator = (await login("operator")).token;
  engineer = (await login("engineer")).token;
  await app.listen(0, "127.0.0.1");
  const listening = app.getHttpServer().address() as { port: number };
  address = `ws://127.0.0.1:${listening.port}`;
});
after(async () => app?.close());

test("all roles have a private profile; users cannot alter their role or other accounts", async () => {
  for (const token of [admin, operator, engineer]) {
    const result = await request("GET", "/auth/profile", token);
    assert.equal(typeof result.username, "string");
    assert.equal(result.passwordHash, undefined);
    assert.equal(result.sessionVersion, undefined);
  }
  await request("GET", "/auth/profile", "", undefined, 401);
  await request("PATCH", "/auth/profile", operator, { name: "  新姓名  " });
  assert.equal((await request("GET", "/auth/me", operator)).name, "新姓名");
  await request("PATCH", "/auth/profile", operator, { name: "", role: "ADMIN" }, 400);
  await request("POST", `/users/${operatorId}/password`, engineer, { newPassword }, 403);
});
test("wrong current password, short, identical and oversized Unicode passwords are rejected", async () => {
  await request("POST", "/auth/password", operator, { currentPassword: "wrong", newPassword }, 400);
  await request("POST", "/auth/password", operator, { currentPassword: oldPassword, newPassword: "short" }, 400);
  await request("POST", "/auth/password", operator, { currentPassword: oldPassword, newPassword: oldPassword }, 400);
  await request("POST", "/auth/password", operator, { currentPassword: oldPassword, newPassword: "汉".repeat(25) }, 400);
  await request("GET", "/auth/me", operator);
});
test("password change revokes HTTP tokens and live WebSockets, including legacy tokens", async () => {
  const second = (await login("operator")).token;
  const legacy = await app.get(JwtService).signAsync({ sub: operatorId });
  await request("GET", "/auth/me", legacy);
  const ws = await socket(operator);
  const closed = new Promise<{ code: number; reason: string }>((done) => ws.once("close", (code, reason) => done({ code, reason: String(reason) })));
  await request("POST", "/auth/password", operator, { currentPassword: oldPassword, newPassword });
  assert.deepEqual(await closed, { code: 1008, reason: "Password changed" });
  for (const token of [operator, second, legacy]) await request("GET", "/auth/me", token, undefined, 401);
  await login("operator", oldPassword, 401);
  operator = (await login("operator", newPassword)).token;
  await request("GET", "/auth/profile", operator);
  assert.equal((await db.user.findUniqueOrThrow({ where: { id: operatorId } })).sessionVersion, 1);
});
test("revoked tokens cannot open a new WebSocket", async () => {
  const stale = await app.get(JwtService).signAsync({ sub: operatorId, sessionVersion: 0 });
  const ws = new WebSocket(`${address}/account-test-ws`);
  const closed = new Promise<number>((done) => ws.once("close", (code) => done(code)));
  ws.once("open", () => ws.send(JSON.stringify({ token: stale })));
  assert.equal(await closed, 1008);
});
test("administrator resets another user and invalidates that user's sessions", async () => {
  const reset = "Admin-Reset-Test-2026!";
  const self = await request("GET", "/auth/me", admin);
  await request("POST", `/users/${self.id}/password`, admin, { newPassword: reset }, 400);
  await request("POST", `/users/${operatorId}/password`, operator, { newPassword: reset }, 403);
  await request("POST", `/users/${operatorId}/password`, admin, { newPassword: reset });
  await request("GET", "/auth/me", operator, undefined, 401);
  await login("operator", newPassword, 401);
  operator = (await login("operator", reset)).token;
  await request("GET", "/auth/profile", operator);
  await request("GET", "/auth/me", admin);
});
test("simultaneous changes cannot both overwrite the same password", async () => {
  await db.user.create({ data: { name: "Race test", username: "race", role: "OPERATOR", passwordHash: await hash(oldPassword, 4) } });
  const token = (await login("race")).token;
  const responses = await Promise.all(["Race-Password-2026-A", "Race-Password-2026-B"].map(password => app.inject({ method: "POST", url: "/api/auth/password", headers: { authorization: `Bearer ${token}` }, payload: { currentPassword: oldPassword, newPassword: password } })));
  assert.equal(responses.filter(response => response.statusCode === 201).length, 1);
  assert.ok(responses.some(response => [400, 401, 409].includes(response.statusCode)));
});
test("audit records contain no password material", async () => {
  const entries = await db.auditLog.findMany();
  assert.ok(entries.some(e => e.action === "CHANGE_PASSWORD"));
  const serialized = JSON.stringify(entries);
  for (const secret of [oldPassword, newPassword, "Admin-Reset-Test-2026!", "passwordHash", "$2b$"]) assert.equal(serialized.includes(secret), false);
});
