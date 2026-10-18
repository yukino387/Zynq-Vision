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
  body: JSON.stringify({ username: "admin", password: env.SEED_PASSWORD }),
});
const session = await login.json();
const headers = {
  authorization: `Bearer ${session.token}`,
  "content-type": "application/json",
};
const snapshot = await (await fetch(`${base}/devices/snapshot`, { headers })).json();
const zynq = snapshot.find((d) => d.type === "ZYNQ");
console.log("device", zynq?.id, zynq?.connectionState, zynq?.reportedState?.modelVersion);
const models = await (await fetch(`${base}/models?pageSize=100`, { headers })).json();
for (const model of models.items.filter((m) => m.version.includes("MILK") || m.version.includes("milk"))) {
  console.log(
    "model",
    model.version,
    model.status,
    model.source,
    "channels", model.manifest?.input?.channels,
    "weights", model.manifest?.weights?.size,
    "classes", model.manifest?.classes?.slice(0, 2),
  );
  const started = performance.now();
  const response = await fetch(`${base}/models/${model.id}/compatibility`, {
    method: "POST",
    headers,
    body: JSON.stringify({ deviceId: zynq.id }),
  });
  const body = await response.text();
  console.log("compat", model.version, response.status, `${(performance.now() - started).toFixed(0)}ms`, body.slice(0, 500));
}
