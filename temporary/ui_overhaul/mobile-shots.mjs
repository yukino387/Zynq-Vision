// 移动端截图：登录后逐屏抓取。
import { spawn } from "node:child_process";
import fs from "node:fs";

const ROOT = "C:/00_workplace/fpga/cnn_accelerator";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5174/mobile/";
const OUT = `${ROOT}/temporary/ui_overhaul/shots/mobile`;
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

const chrome = spawn(
  CHROME,
  [
    "--remote-debugging-port=9899",
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    `--user-data-dir=${ROOT}/temporary/ui_overhaul/profile-mobile`,
    "--window-size=390,844",
    "about:blank",
  ],
  { stdio: "ignore" },
);

let wsUrl;
for (let i = 0; i < 60; i++) {
  try {
    const list = await (await fetch("http://127.0.0.1:9899/json/list")).json();
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
const errors = [];
const net = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.method === "Network.requestWillBeSent" && m.params.request.url.includes("/api"))
    net.push("→ " + m.params.request.method + " " + m.params.request.url);
  if (m.method === "Network.loadingFailed")
    net.push("✗ 失败 " + m.params.errorText);
  if (m.method === "Network.responseReceived" && m.params.response.url.includes("/api"))
    net.push("← " + m.params.response.status + " " + m.params.response.url);
  if (m.method === "Runtime.exceptionThrown")
    errors.push((m.params.exceptionDetails.exception?.description ?? m.params.exceptionDetails.text ?? "").slice(0, 160));
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
const ev = async (expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true })).result?.value;

await send("Page.enable");
await send("Runtime.enable");
await send("Network.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await send("Page.navigate", { url: BASE });
await sleep(3000);
// 清掉上一次跑测试时写进 storage 的 vision.server（会绕过代理直连 3000，被 CORS 挡）
await ev(`uni.removeStorageSync("vision.server")`);

await ev(`uni.setStorageSync("vision.token", ${JSON.stringify(login.token)})`);
await ev(`uni.setStorageSync("vision.user", ${JSON.stringify(JSON.stringify(login.user))})`);
// 不设 vision.server：留空则用同源 origin，走 vite 的 /api 代理
// state.ts 在模块加载时只读一次 storage，必须重载后才生效
await send("Page.reload");
await sleep(4000);

for (const page of ["home", "tasks", "capture", "records", "sync"]) {
  await ev(`uni.reLaunch({url:"/pages/${page}/index"})`);
  await sleep(2800);
  const shot = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(`${OUT}/${page}.png`, Buffer.from(shot.data, "base64"));
  const text = (await ev(`document.body.innerText`)) ?? "";
  console.log(`${page.padEnd(9)} ${JSON.stringify(text.replace(/\s+/g, " ").slice(0, 108))}`);
}
if (errors.length) console.log("运行时错误:\n  " + errors.slice(0, 3).join("\n  "));
chrome.kill();
