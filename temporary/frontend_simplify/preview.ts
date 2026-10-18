import "reflect-metadata";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
async function main() { const out = resolve("temporary/frontend_simplify", `run-${Date.now()}`);
mkdirSync(out, { recursive: true });
process.env.DATABASE_URL = `file:${resolve(out, "app.db").replaceAll("\\", "/")}`;
process.env.JWT_SECRET = "frontend-local-test-secret-do-not-use-in-production";
process.env.STORAGE_ROOT = resolve(out, "storage");
process.env.SERVER_PORT = "3010";
execFileSync(process.execPath, [resolve("apps/server/node_modules/prisma/build/index.js"), "migrate", "deploy", "--schema", resolve("apps/server/prisma/schema.prisma")], { env: process.env, stdio: "pipe" });
const { createApp } = await import("../../apps/server/src/bootstrap.js");
const { Db } = await import("../../apps/server/src/core/db.js");
const { hash } = await import("../../apps/server/node_modules/bcryptjs/index.js");
const app = await createApp(false), db = app.get(Db);
await db.user.create({ data: { name: "流程验证员", username: "workflow", role: "ADMIN", passwordHash: await hash("Workflow-Test-2026!", 4) } });
const device = await db.device.create({ data: { name: "流程验证模拟设备", serialNumber: "SIM-WORKFLOW", type: "SIMULATOR", capabilities: {} } });
const { DevicesService } = await import("../../apps/server/src/devices/devices.service.js");
await app.get(DevicesService).attach(device.id);
for (let i = 1; i <= 2; i++) {
 const sample = await db.sample.create({ data: { name: `待审核样本${i}`, source: "SIMULATION", clientId: "workflow-test", localSequence: i, idempotencyKey: `workflow-${i}`, capturedAt: new Date() } });
 await db.inspection.create({ data: { sampleId: sample.id, deviceId: device.id, source: "SIMULATION", result: "REVIEW", status: "COMPLETED", reason: "LOW_CONFIDENCE", startedAt: new Date(), completedAt: new Date() } });
}
await app.listen(3010, "127.0.0.1");
console.log("Isolated workflow test ready: http://localhost:3010");

}
void main();


