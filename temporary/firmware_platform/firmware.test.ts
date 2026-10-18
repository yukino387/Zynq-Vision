import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { crc32 } from "node:zlib";

const output = resolve("temporary/firmware_platform", `run-${Date.now()}`);
mkdirSync(output, { recursive: true });
process.env.DATABASE_URL = `file:${resolve(output, "app.db").replaceAll("\\", "/")}`;
process.env.JWT_SECRET = "test-only-secret-32-characters-do-not-reuse";
process.env.SEED_PASSWORD = "Vision-Test-Password-2026!";
process.env.WS_PATH = "/vision-firmware-test-ws";
process.env.STORAGE_ROOT = resolve(output, "storage");

let app: Awaited<
  ReturnType<(typeof import("../../apps/server/src/bootstrap.js"))["createApp"]>
>;
let token = "",
  engineer = "";

async function call<T = Record<string, unknown>>(
  method: "GET" | "POST",
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
  const deadline = Date.now() + 20000;
  let last: T;
  do {
    last = await read();
    if (done(last)) return last;
    await new Promise((r) => setTimeout(r, 150));
  } while (Date.now() < deadline);
  throw new Error(`Timed out: ${JSON.stringify(last!)}`);
}

/** 构造一个最小但完全合法的 PKG1 包；模拟器不执行其中代码。 */
function buildPackage(version: string, seed: number) {
  const segments = [
    { paddr: 0x100000, offset: 0, size: 64 },
    { paddr: 0x100100, offset: 64, size: 32 },
  ];
  const imageSize = 96,
    headerSize = 128 + segments.length * 16,
    header = Buffer.alloc(headerSize),
    payload = Buffer.alloc(imageSize);
  for (let i = 0; i < imageSize; i++) payload[i] = (i * 7 + seed) & 0xff;
  const versionBytes = Buffer.from(version, "ascii");
  header.writeUInt32LE(0x31474b50, 0);
  header.writeUInt32LE(1, 4);
  header.writeUInt32LE(headerSize, 8);
  header.writeUInt32LE(0x100000, 12);
  header.writeUInt32LE(0x100000, 16);
  header.writeUInt32LE(imageSize, 20);
  header.writeUInt32LE(segments.length, 24);
  header.writeUInt32LE(versionBytes.length, 28);
  header.writeUInt32LE(crc32(payload), 32);
  createHash("sha256").update(payload).digest().copy(header, 40);
  versionBytes.copy(header, 72);
  segments.forEach((segment, index) => {
    const at = 128 + index * 16;
    header.writeUInt32LE(segment.paddr, at);
    header.writeUInt32LE(segment.offset, at + 4);
    header.writeUInt32LE(segment.size, at + 8);
    header.writeUInt32LE(0, at + 12);
  });
  const crcInput = Buffer.concat([
    header.subarray(0, 36),
    header.subarray(40, 128),
    header.subarray(128, headerSize),
  ]);
  header.writeUInt32LE(crc32(crcInput), 36);
  return Buffer.concat([header, payload]);
}

async function uploadFirmware(
  data: Buffer,
  name: string,
  bearer = token,
  status = 201,
) {
  const boundary = `firmware-${randomUUID()}`;
  const payload = Buffer.concat([
    Buffer.from(
      `--${boundary}\r\nContent-Disposition: form-data; name="name"\r\n\r\n${name}\r\n--${boundary}\r\nContent-Disposition: form-data; name="notes"\r\n\r\nTEST firmware package\r\n--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="camera_live.fw"\r\nContent-Type: application/octet-stream\r\n\r\n`,
    ),
    data,
    Buffer.from(`\r\n--${boundary}--\r\n`),
  ]);
  const response = await app.inject({
    method: "POST",
    url: "/api/firmware/upload",
    headers: {
      authorization: `Bearer ${bearer}`,
      "content-type": `multipart/form-data; boundary=${boundary}`,
    },
    payload,
  });
  assert.equal(response.statusCode, status, response.body);
  return response.json<{
    id: string;
    version: string;
    sha256: string;
    size: number;
    imageSize: number;
    segments: unknown[];
  }>();
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
  for (const role of ["ADMIN", "ENGINEER"] as const)
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

test("package validation accepts generated and real packages and rejects corruption", async () => {
  const { validateFirmwarePackage } = await import(
    "../../apps/server/src/firmware/package.js"
  );
  const built = buildPackage("TEST-FW-VALID", 3);
  const parsed = validateFirmwarePackage(built);
  assert.equal(parsed.version, "TEST-FW-VALID");
  assert.equal(parsed.segments.length, 2);
  assert.equal(parsed.imageSize, 96);
  assert.equal(parsed.sha256, createHash("sha256").update(built.subarray(160)).digest("hex"));

  const fixture = resolve(
    "temporary/fw_ota_phase1/camera_live-TEST-FW-20261018.fw",
  );
  if (existsSync(fixture)) {
    const real = validateFirmwarePackage(readFileSync(fixture));
    assert.equal(real.version, "TEST-FW-20261018");
    assert.equal(real.segments.length, 2);
  }

  const corrupted = Buffer.from(built);
  corrupted[corrupted.length - 1] ^= 0xff;
  assert.throws(() => validateFirmwarePackage(corrupted));
});

test("firmware upload is admin-only, deploy/rollback work on a simulator", async () => {
  const packageA = buildPackage("TEST-FW-A", 11),
    packageB = buildPackage("TEST-FW-B", 29);
  await uploadFirmware(packageA, "TEST-FW-A", engineer, 403);
  const firmwareA = await uploadFirmware(packageA, "TEST-FW-A");
  assert.equal(firmwareA.version, "TEST-FW-A");
  assert.equal(firmwareA.segments.length, 2);
  await uploadFirmware(packageA, "duplicate", token, 409);
  const firmwareB = await uploadFirmware(packageB, "TEST-FW-B");

  const device = await call<{ id: string }>(
    "POST",
    "/devices",
    { name: "SIMULATED · Firmware OTA", serialNumber: `FW-${randomUUID()}`, type: "SIMULATOR" },
    engineer,
  );
  await call(
    "POST",
    `/firmware/${firmwareA.id}/deploy`,
    { deviceId: device.id },
    engineer,
    403,
  );
  const deploymentA = await call<{ id: string; status: string }>(
    "POST",
    `/firmware/${firmwareA.id}/deploy`,
    { deviceId: device.id },
  );
  await waitFor(
    () => call<{ items: { id: string; status: string }[] }>("GET", "/firmware-deployments?pageSize=50"),
    (page) => page.items.find((row) => row.id === deploymentA.id)?.status === "ACTIVE",
  );
  let snapshot = await call<{ id: string; firmwareVersion: string | null }[]>(
    "GET",
    "/devices/snapshot",
  );
  assert.equal(
    snapshot.find((row) => row.id === device.id)?.firmwareVersion,
    "TEST-FW-A",
  );
  let info = await call<{
    version: string;
    runningSlot: number;
    activeSlot: number;
    previousSlot: number;
  }>("GET", `/devices/${device.id}/firmware`);
  assert.equal(info.version, "TEST-FW-A");
  assert.equal(info.runningSlot, 0);
  assert.equal(info.activeSlot, 0);
  assert.equal(info.previousSlot, 2);
  const deploymentB = await call<{ id: string; previousVersion: string }>(
    "POST",
    `/firmware/${firmwareB.id}/deploy`,
    { deviceId: device.id },
  );
  assert.equal(deploymentB.previousVersion, "TEST-FW-A");
  await waitFor(
    () => call<{ items: { id: string; status: string }[] }>("GET", "/firmware-deployments?pageSize=50"),
    (page) => page.items.find((row) => row.id === deploymentB.id)?.status === "ACTIVE",
  );
  info = await call<typeof info>("GET", `/devices/${device.id}/firmware`);
  assert.equal(info.version, "TEST-FW-B");

  await call(
    "POST",
    `/firmware-deployments/${deploymentB.id}/rollback`,
    { target: "PREVIOUS" },
    token,
  );
  info = await call<typeof info>("GET", `/devices/${device.id}/firmware`);
  assert.equal(info.version, "TEST-FW-A");
  assert.equal(info.runningSlot, 0);
  snapshot = await call<typeof snapshot>("GET", "/devices/snapshot");
  assert.equal(
    snapshot.find((row) => row.id === device.id)?.firmwareVersion,
    "TEST-FW-A",
  );

  const deploymentC = await call<{ id: string }>(
    "POST",
    `/firmware/${firmwareB.id}/deploy`,
    { deviceId: device.id },
  );
  await waitFor(
    () => call<{ items: { id: string; status: string }[] }>("GET", "/firmware-deployments?pageSize=50"),
    (page) => page.items.find((row) => row.id === deploymentC.id)?.status === "ACTIVE",
  );
  await call("POST", `/firmware-deployments/${deploymentC.id}/rollback`, {
    target: "GOLDEN",
  });
  info = await call<typeof info>("GET", `/devices/${device.id}/firmware`);
  assert.equal(info.version, "SIM-GOLDEN");
  assert.equal(info.runningSlot, 2);
  assert.equal(info.activeSlot, 2);
});
