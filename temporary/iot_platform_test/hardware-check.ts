import "../../apps/server/src/config.js";
import { writeFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
async function main() {
  const root = "http://localhost:3000";
  const login = await fetch(`${root}/api/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      username: "admin",
      password: process.env.SEED_PASSWORD,
    }),
  });
  if (!login.ok) throw new Error("Local admin login failed");
  const { token } = (await login.json()) as { token: string };
  const headers = {
    authorization: `Bearer ${token}`,
    "content-type": "application/json",
  };
  const devices = (await fetch(`${root}/api/devices/snapshot`, {
    headers,
  }).then((r) => r.json())) as { id: string; type: string }[];
  const board = devices.find((d) => d.type === "ZYNQ");
  if (!board) throw new Error("Configured Zynq endpoint missing");
  const status = await fetch(`${root}/api/devices/${board.id}/commands`, {
    method: "POST",
    headers,
    body: JSON.stringify({ type: "GET_STATUS" }),
  });
  const report = {
    timestamp: new Date().toISOString(),
    step: "READ_ONLY_GET_STATUS",
    status: status.status,
    payload: (await status.json()) as unknown,
  };
  await mkdir(resolve("temporary/iot_platform_test"), { recursive: true });
  await writeFile(
    resolve("temporary/iot_platform_test/hardware-status.json"),
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
}
void main();
