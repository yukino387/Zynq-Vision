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
const devices = await (await fetch(`${base}/devices/snapshot`, { headers })).json();
const zynq = devices.find((d) => d.type === "ZYNQ");
const models = await (await fetch(`${base}/models?pageSize=100`, { headers })).json();
const model = models.items.find((m) => m.version === "MILK-RGB-20261017");
const datasets = await (await fetch(`${base}/datasets?status=FROZEN&pageSize=100`, { headers })).json();
const dataset = datasets.items[0];
console.log("target", { device: zynq?.id, model: model?.id, dataset: dataset?.id, datasetName: dataset?.name });
const started = performance.now();
const response = await fetch(`${base}/benchmarks`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    name: `诊断复现 RGB ${new Date().toLocaleTimeString()}`,
    modelId: model.id,
    datasetId: dataset.id,
    deviceId: zynq.id,
  }),
});
const body = await response.text();
console.log("status", response.status, `${(performance.now() - started).toFixed(0)}ms`);
console.log(body.slice(0, 2000));
