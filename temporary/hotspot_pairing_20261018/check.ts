import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { serverAddresses, mobileServerUrl } from "../../apps/server/src/system/network.js";

async function main() {
  const output = resolve("temporary/hotspot_pairing_20261018", `run-${Date.now()}`);
  mkdirSync(output, { recursive: true });
  const entry = (address: string) => ({ address, netmask: "255.255.255.0", family: "IPv4" as const, mac: "00:00:00:00:00:00", internal: false, cidr: `${address}/24` });
  const addresses = serverAddresses(3000, {
    "Radmin VPN": [entry("26.229.61.139")],
    "以太网": [entry("169.254.140.109")],
    "WLAN": [entry("10.101.242.54")],
    "vEthernet (WSL)": [entry("172.20.0.1")],
  });
  assert.equal(addresses[0]!.url, "http://10.101.242.54:3000");
  assert.deepEqual(addresses.filter((address) => address.mobile).map((address) => address.interfaceName), ["WLAN"]);
  for (const url of ["http://localhost:3000", "http://127.0.0.1:3000", "http://0.0.0.0:3000", "http://[::1]:3000", "http://sub.localhost:3000", "ftp://10.1.1.1", "http://user:pass@10.1.1.1", "http://10.1.1.1/mobile/", "http://10.1.1.1?x=1"])
    assert.equal(mobileServerUrl(url), false, url);
  assert.equal(mobileServerUrl("http://10.101.242.54:3000/"), true);
  process.env.DATABASE_URL = `file:${resolve(output, "app.db").replaceAll("\\", "/")}`;
  process.env.STORAGE_ROOT = resolve(output, "storage");
  process.env.JWT_SECRET = "isolated-hotspot-pairing-32-character-test-secret";
  process.env.ZYNQ_LOCAL_PORT = "15029";
  execFileSync(process.execPath, [resolve("apps/server/node_modules/prisma/build/index.js"), "migrate", "deploy", "--schema", resolve("apps/server/prisma/schema.prisma")], { env: process.env, stdio: "pipe" });
  const { createApp } = await import("../../apps/server/src/bootstrap.js");
  const { Db } = await import("../../apps/server/src/core/db.js");
  const { hash } = await import("../../apps/server/node_modules/bcryptjs/index.js");
  const app = await createApp(false), db = app.get(Db);
  await db.user.create({ data: { username: "admin", name: "热点配对验证", role: "ADMIN", passwordHash: await hash("Hotspot-Test-2026!", 4) } });
  const login = await app.inject({ method: "POST", url: "/api/auth/login", payload: { username: "admin", password: "Hotspot-Test-2026!" } });
  const headers = { authorization: `Bearer ${login.json().token}` };
  for (const serverUrl of ["http://localhost:3000", "http://127.0.0.1:3000", "file:///C:/", "http://10.101.242.54:3000/mobile/"]) {
    const response = await app.inject({ method: "POST", url: "/api/system/pairing", headers, payload: { serverUrl } });
    assert.equal(response.statusCode, 400, response.body);
  }
  assert.equal(await db.pairingToken.count(), 0);
  const response = await app.inject({ method: "POST", url: "/api/system/pairing", headers, payload: { serverUrl: "http://10.101.242.54:3000/" } });
  assert.equal(response.statusCode, 201, response.body);
  const paired = response.json();
  assert.equal(paired.serverUrl, "http://10.101.242.54:3000");
  const redeem = await app.inject({ method: "POST", url: "/api/system/pairing/redeem", payload: { token: paired.pairingToken } });
  assert.equal(redeem.statusCode, 201, redeem.body);
  const repeat = await app.inject({ method: "POST", url: "/api/system/pairing/redeem", payload: { token: paired.pairingToken } });
  assert.equal(repeat.statusCode, 400, repeat.body);
  const report = { ok: true, wlanFirst: true, unusableAddressesRejected: true, normalizedOrigin: true, singleUseToken: true, addresses };
  writeFileSync(resolve(output, "results.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
  if (process.argv.includes("--test-only")) { await app.close(); return; }
  await app.listen(3029, "127.0.0.1");
  const { createServer } = await import("../../apps/web/node_modules/vite/dist/node/index.js");
  const { default: config } = await import("../../apps/web/vite.config.ts");
  const vite = await createServer({ ...config, configFile: false, root: resolve("apps/web"), server: { host: "127.0.0.1", port: 5189, strictPort: true, proxy: { "/api": "http://127.0.0.1:3029", "/ws": { target: "ws://127.0.0.1:3029", ws: true } } } });
  await vite.listen();
  console.log("Hotspot UI ready: http://127.0.0.1:5189/#/system/pairing");
  process.on("SIGINT", () => void Promise.all([vite.close(), app.close()]).then(() => process.exit(0)));
}
void main().catch((error) => { console.error(error); process.exit(1); });
