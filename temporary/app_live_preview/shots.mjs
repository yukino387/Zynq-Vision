// 移动端 H5 截图：登录 -> 设置 token -> 逐页抓取，并报告实时画面是否真的到达。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = "C:/00_workplace/fpga/cnn_accelerator";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://127.0.0.1:5174/mobile/";
const API = "http://localhost:3000";
const OUT = path.join(ROOT, "temporary/app_live_preview/shots");
const PORT = 9902;
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
const inspections = await (
  await fetch(`${API}/api/inspections?pageSize=1`, { headers })
).json();
const firstInspection = inspections.items?.[0]?.id;

fs.mkdirSync(OUT, { recursive: true });
const chrome = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${ROOT}/temporary/app_live_preview/profile`,
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
const errors = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.method === "Runtime.exceptionThrown")
    errors.push(
      (
        m.params.exceptionDetails.exception?.description ??
        m.params.exceptionDetails.text ??
        ""
      ).slice(0, 240),
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
  (await send("Runtime.evaluate", { expression: expr, returnByValue: true }))
    .result?.value;

await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", {
  width: 390,
  height: 844,
  deviceScaleFactor: 2,
  mobile: true,
});
await send("Page.navigate", { url: BASE });
await sleep(3000);
await ev(`uni.removeStorageSync("vision.server")`);
await ev(`uni.setStorageSync("vision.token", ${JSON.stringify(login.token)})`);
await ev(
  `uni.setStorageSync("vision.user", ${JSON.stringify(JSON.stringify(login.user))})`,
);

async function shot(name) {
  const png = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUT, `${name}.png`), Buffer.from(png.data, "base64"));
  const text = (await ev(`document.body.innerText`)) ?? "";
  const images = await ev(
    `[...document.querySelectorAll('img')].filter(i=>i.src.startsWith('data:image/jpeg')).length`,
  );
  console.log(
    `${name.padEnd(18)} imgs=${images ?? 0}  ${JSON.stringify(text.replace(/\s+/g, " ").slice(0, 110))}`,
  );
}

async function page(pathname, name, settle = 3200) {
  await ev(`uni.reLaunch({url:${JSON.stringify(pathname)}})`);
  await sleep(settle);
  await shot(name);
}

await ev(`uni.setStorageSync("vision.captureMode","BOARD")`);
await send("Page.reload");
await sleep(4000);

await page("/pages/home/index", "home");
await page("/pages/capture/index", "capture-board", 4200);
await page("/pages/live/index", "live", 4200);
await page("/pages/tasks/index", "tasks");
await page("/pages/records/index", "records");
await page("/pages/sync/index", "sync");
await page("/pages/pair/index", "pair");
if (firstInspection) {
  await ev(
    `uni.navigateTo({url:${JSON.stringify(`/pages/detail/index?id=${firstInspection}`)}})`,
  );
  await sleep(3500);
  await shot("detail");
}

await ev(`uni.setStorageSync("vision.captureMode","MOBILE")`);
await page("/pages/capture/index", "capture-mobile", 3800);

await ev(`uni.setStorageSync("vision.token","")`);
await ev(`uni.reLaunch({url:"/pages/login/index"})`);
await sleep(1400);
await shot("login");

if (errors.length) console.log("运行时错误:\n  " + errors.slice(0, 5).join("\n  "));
chrome.kill();
