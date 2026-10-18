// 交互验收：离线态、全屏、采样结果。
import { spawn } from "node:child_process";
import fs from "node:fs";

const ROOT = "C:/00_workplace/fpga/cnn_accelerator";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5174/mobile/";
const API = "http://localhost:3000";
const OUT = `${ROOT}/temporary/app_live_preview/shots`;
const PORT = 9903;
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
  await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username: "admin", password: env.SEED_PASSWORD }),
  })
).json();
const headers = { authorization: `Bearer ${login.token}` };
const devices = await (
  await fetch(`${API}/api/devices/snapshot`, { headers })
).json();
const zynq = devices.find((d) => d.type === "ZYNQ");
const sim = devices.find((d) => d.type === "SIMULATOR");
const before = await (
  await fetch(`${API}/api/inspections?pageSize=1`, { headers })
).json();

const chrome = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${ROOT}/temporary/app_live_preview/profile2`,
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
let seq = 0,
  errors = [];
const pending = new Map();
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.method === "Runtime.exceptionThrown")
    errors.push(
      JSON.stringify(m.params.exceptionDetails).slice(0, 500),
    );
  if (
    m.method === "Network.requestWillBeSent" &&
    m.params.request.url.includes("/samples/capture")
  )
    console.log(
      "→ POST samples/capture",
      String(m.params.request.postData).slice(0, 260),
    );
  if (
    m.method === "Network.responseReceived" &&
    m.params.response.url.includes("/samples/capture")
  )
    console.log("←", m.params.response.status, "samples/capture");
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
  (await send("Runtime.evaluate", { expression: expr, returnByValue: true }))
    .result?.value;
const shot = async (name) => {
  const png = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(`${OUT}/${name}.png`, Buffer.from(png.data, "base64"));
  const text = (await ev(`document.body.innerText`)) ?? "";
  console.log(`${name.padEnd(20)} ${JSON.stringify(text.replace(/\s+/g, " ").slice(0, 120))}`);
};
async function clickText(text) {
  return ev(
    `(()=>{const el=[...document.querySelectorAll('uni-button,uni-text,uni-view,button,span,div')].find(e=>e.textContent?.trim()===${JSON.stringify(text)});if(!el)return false;el.click();return true})()`,
  );
}

await send("Page.enable");
await send("Runtime.enable");
await send("Network.enable");
await send("Emulation.setDeviceMetricsOverride", {
  width: 390,
  height: 844,
  deviceScaleFactor: 2,
  mobile: true,
});
await send("Page.navigate", { url: BASE });
await sleep(2500);
await ev(`uni.removeStorageSync("vision.server")`);
await ev(`uni.setStorageSync("vision.token", ${JSON.stringify(login.token)})`);
await ev(
  `uni.setStorageSync("vision.user", ${JSON.stringify(JSON.stringify(login.user))})`,
);
await ev(`uni.setStorageSync("vision.captureMode","BOARD")`);

// 1. 离线设备
await ev(`uni.setStorageSync("vision.device", ${JSON.stringify(zynq.id)})`);
await send("Page.reload");
await sleep(4000);
await ev(`uni.reLaunch({url:"/pages/capture/index"})`);
await sleep(3000);
await shot("capture-offline");
await ev(`uni.navigateTo({url:"/pages/live/index"})`);
await sleep(2500);
await shot("live-offline");

// 2. 全屏
await ev(`uni.setStorageSync("vision.device", ${JSON.stringify(sim.id)})`);
await send("Page.reload");
await sleep(3500);
await ev(`uni.reLaunch({url:"/pages/live/index"})`);
await sleep(3500);
console.log("click 全屏:", await clickText("全屏"));
await sleep(900);
await shot("live-immersive");
console.log("click 退出:", await clickText("退出"));
await sleep(700);

// 3. 采样当前帧
console.log(
  "button:",
  await ev(
    `(()=>{const b=document.querySelector('.shutter-action');return b?{disabled:b.hasAttribute('disabled'),cls:b.className,text:b.textContent.trim()}:null})()`,
  ),
);
console.log(
  "click 采样当前帧:",
  await ev(`document.querySelector('.shutter-action')?.click(); true`),
);
await sleep(900);
console.log(
  "toast:",
  JSON.stringify(
    await ev(`(document.body.innerText||'').replace(/\\s+/g,' ').slice(-180)`),
  ),
);
await sleep(2600);
await shot("live-after-capture");
const after = await (
  await fetch(`${API}/api/inspections?pageSize=1`, { headers })
).json();
console.log(
  "inspections:",
  before.total,
  "->",
  after.total,
  "newest:",
  after.items?.[0]?.id,
);
if (errors.length) console.log("运行时错误:\n  " + errors.slice(0, 4).join("\n  "));
chrome.kill();
