import "../../apps/server/src/config.js";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
async function main() {
  const base = "http://localhost:3000/api";
  const login = await fetch(`${base}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      username: "admin",
      password: process.env.SEED_PASSWORD,
    }),
  });
  const { token } = (await login.json()) as { token: string };
  const headers = {
    authorization: `Bearer ${token}`,
    "content-type": "application/json",
  };
  async function get(path: string) {
    const r = await fetch(`${base}${path}`, { headers });
    if (!r.ok) throw new Error(await r.text());
    return r.json() as Promise<Record<string, unknown>>;
  }
  async function post(path: string, body: unknown = {}) {
    const r = await fetch(`${base}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const result = (await r.json()) as Record<string, unknown>;
    if (!r.ok) throw new Error(JSON.stringify(result));
    return result;
  }
  const all = (await fetch(`${base}/devices/snapshot`, { headers }).then((r) =>
    r.json(),
  )) as { id: string; type: string }[];
  const board = all.find((d) => d.type === "ZYNQ")!;
  const before = await post(`/devices/${board.id}/commands`, {
    type: "GET_STATUS",
  });
  const original = before.reportedState as { inspectionEnabled: boolean };
  const report: Record<string, unknown> = {
    timestamp: new Date().toISOString(),
    before,
  };
  try {
    report.connect = await post(`/devices/${board.id}/connect`);
    let sample: Record<string, unknown> | null = null;
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
      try {
        sample = await post("/samples/capture", {
          deviceId: board.id,
          clientId: "hardware-verification-" + crypto.randomUUID(),
          localSequence: 0,
          idempotencyKey: crypto.randomUUID(),
        });
        break;
      } catch (error) {
        if (!String(error).includes("FRAME_UNAVAILABLE")) throw error;
        await new Promise((r) => setTimeout(r, 250));
      }
    }
    if (!sample) throw new Error("No complete frame received within 5 seconds");
    report.sample = sample;
    report.device = await get(`/devices/${board.id}`);
  } catch (error) {
    report.error = String(error);
    process.exitCode = 1;
  } finally {
    if (!original.inspectionEnabled)
      report.restore = await post(`/devices/${board.id}/commands`, {
        type: "STOP_INSPECTION",
      });
    report.disconnect = await post(`/devices/${board.id}/disconnect`);
    await writeFile(
      resolve("temporary/iot_platform_test/hardware-capture-report.json"),
      JSON.stringify(report, null, 2),
    );
    console.log(
      JSON.stringify(
        {
          success: !report.error,
          error: report.error ?? null,
          sampleId: (report.sample as { id: string } | undefined)?.id,
          source: (report.sample as { source: string } | undefined)?.source,
          beforeRuntime: before.runtimeState,
          restoreRuntime: (
            report.restore as { runtimeState: string } | undefined
          )?.runtimeState,
          capabilities: (report.device as { snapshot?: unknown } | undefined)
            ?.snapshot,
        },
        null,
        2,
      ),
    );
  }
}
void main();
