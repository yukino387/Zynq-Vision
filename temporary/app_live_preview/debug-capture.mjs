// 调试：实时页快门是否真的发出 /samples/capture。
import { spawn } from "node:child_process";
import fs from "node:fs";

const ROOT = "C:/00_workplace/fpga/cnn_accelerator";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const PORT = 9904;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const env = Object.fromEntries(
  fs
    .readFileSync(`${ROOT}/.env`, "utf8")
    .split(/\r?\n/)
    .filter((l) => l.includes("=") && !l.trimStart().startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i).trim(), l.slice(i + 1).trim()];
    }),
);
const login = await (
  await fetch("http://localhost:3000/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username: "admin", password: env.SEED_PASSWORD }),
  })
).json();
const devices = await (
  await fetch("http://localhost:3000/api/devices/snapshot", {
    headers: { authorization: `Bearer ${login.token}` },
  })
).json();
const sim = devices.find((d) => d.type === "SIMULATOR");

const chrome = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    `--user-data-dir=${ROOT}/temporary/app_live_preview/profile3`,
    "--window-size=390,844",
    "about:blank",
  ],
  { stdio: "ignore" },
);
let wsUrl;
for (let i = 0; i < 80; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    const page = list.find((t) => t.type === "page");
    if (page?.webSocketDebuggerUrl) {
      wsUrl = page.webSocketDebuggerUrl;
      break;
    }
  } catch {}
  await sleep(250);
}
const ws = new WebSocket(wsUrl);
await new Promise((r) => ws.addEventListener("open", r));
let seq = 0;
const pending = new Map();
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.method === "Network.requestWillBeSent" && m.params.request.url.includes("/samples/capture"))
    console.log("→", m.params.request.method, m.params.request.url, m.params.request.postData);
  if (m.method === "Network.responseReceived" && m.params.response.url.includes("/samples/capture"))
    console.log("←", m.params.response.status, m.params.response.url);
  if (m.method === "Network.loadingFailed" && m.params.errorText)
    console.log("✗", m.params.errorText);
  if (m.method === "Runtime.consoleAPICalled")
    console.log(
      "console:",
      m.params.type,
      m.params.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 300),
    );
  if (m.id && pending.has(m.id)) {
    const { resolve, reject } = pending.get(m.id);
    pending.delete(m.id);
    m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
  }
});
const send = (method, params = {}) => {
  const id = ++seq;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((res, rej) => pending.set(id, { resolve: res, reject: rej }));
};
const ev = async (expr) =>
  (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }))
    .result?.value;

await send("Page.enable");
await send("Runtime.enable");
await send("Network.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await send("Page.navigate", { url: "http://127.0.0.1:5174/mobile/" });
await sleep(2500);
await ev(`uni.removeStorageSync("vision.server")`);
await ev(`uni.setStorageSync("vision.token", ${JSON.stringify(login.token)})`);
await ev(`uni.setStorageSync("vision.user", ${JSON.stringify(JSON.stringify(login.user))})`);
await ev(`uni.setStorageSync("vision.device", ${JSON.stringify(sim.id)})`);
await send("Page.reload");
await sleep(3500);
await ev(`uni.reLaunch({url:"/pages/live/index"})`);
await sleep(3500);
console.log(
  "button:",
  await ev(
    `(()=>{const b=document.querySelector('.shutter-action');return b?{tag:b.tagName,disabled:b.disabled,attr:b.getAttribute('disabled'),text:b.textContent.trim()}:null})()`,
  ),
);
console.log(
  "state:",
  await ev(
    `(()=>{const app=document.querySelector('uni-page-body');return (app?.innerText||'').replace(/\\s+/g,' ').slice(-220)})()`,
  ),
);
console.log("click:", await ev(`document.querySelector('.shutter-action').click(); true`));
await sleep(1200);
console.log(
  "after:",
  await ev(`(document.body.innerText||'').replace(/\\s+/g,' ').slice(-320)`),
);
await sleep(2500);
console.log(
  "final:",
  await ev(`(document.body.innerText||'').replace(/\\s+/g,' ').slice(-320)`),
);
chrome.kill();
