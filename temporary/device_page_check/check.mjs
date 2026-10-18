import { readFileSync } from "node:fs";
const env = Object.fromEntries(
  readFileSync(new URL("../../.env", import.meta.url), "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const i = line.indexOf("=");
      return [line.slice(0, i), line.slice(i + 1)];
    }),
);
const base = "http://localhost:3000/api";
const login = await fetch(`${base}/auth/login`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({
    username: "admin",
    password: env.SEED_PASSWORD,
  }),
});
if (!login.ok) {
  console.log("login failed", login.status, await login.text());
  process.exit(1);
}
const session = await login.json();
console.log("login ok", session.user?.role);
const headers = { authorization: `Bearer ${session.token}` };
const snapshotResponse = await fetch(`${base}/devices/snapshot`, { headers });
const devices = await snapshotResponse.json();
const deviceId = devices[0]?.id;
for (const path of [
  "/devices/policy",
  "/devices/snapshot",
  "/system/events?pageSize=30",
  "/stations?pageSize=100",
  ...(deviceId ? [`/devices/${deviceId}`] : []),
]) {
  const started = performance.now();
  const response = await fetch(`${base}${path}`, { headers });
  const body = await response.text();
  console.log(
    path.replace(/devices\/[^/?]+/, "devices/:id"),
    response.status,
    `${(performance.now() - started).toFixed(0)}ms`,
    `${body.length}B`,
  );
  if (!response.ok) console.log(body.slice(0, 300));
}
