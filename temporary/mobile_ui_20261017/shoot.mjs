import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(
  resolve(import.meta.dirname, "../../apps/server/package.json"),
);
const WebSocket = require("ws");

const root = resolve(import.meta.dirname, "../..");
const out = resolve(import.meta.dirname);
mkdirSync(out, { recursive: true });
const env = Object.fromEntries(
  readFileSync(resolve(root, ".env"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line.includes("=") && !line.trim().startsWith("#"))
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index), line.slice(index + 1)];
    }),
);
const password = env.SEED_PASSWORD;
if (!password) throw new Error("SEED_PASSWORD missing");

const server = "http://127.0.0.1:3000";
const login = await fetch(`${server}/api/auth/login`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ username: "admin", password }),
}).then((response) => {
  if (!response.ok) throw new Error(`login ${response.status}`);
  return response.json();
});
const authorization = { authorization: `Bearer ${login.token}` };
const inspections = await fetch(`${server}/api/inspections?pageSize=3`, {
  headers: authorization,
}).then((response) => response.json());
const samples = await fetch(`${server}/api/samples?pageSize=3`, {
  headers: authorization,
}).then((response) => response.json());

const mobileBase = process.env.MOBILE_BASE ?? mobileBase;
const mobileOrigin = new URL(mobileBase).origin;
const profile = resolve(out, "profile");
const chrome = spawn(
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  [
    "--headless=new",
    "--remote-debugging-port=9224",
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-gpu",
    "--hide-scrollbars",
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
    "--window-size=390,844",
    "about:blank",
  ],
  { stdio: "ignore" },
);

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
async function endpoint(path) {
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      const response = await fetch(`http://127.0.0.1:9224${path}`);
      if (response.ok) return response.json();
    } catch {}
    await sleep(200);
  }
  throw new Error(`debug endpoint ${path} unavailable`);
}
const targets = await endpoint("/json/list");
const page = targets.find((target) => target.type === "page");
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((done, fail) => {
  socket.once("open", done);
  socket.once("error", fail);
});
let sequence = 0;
const waiting = new Map();
socket.on("message", (raw) => {
  const message = JSON.parse(raw.toString());
  if (message.id && waiting.has(message.id)) {
    const { done, fail } = waiting.get(message.id);
    waiting.delete(message.id);
    if (message.error) fail(new Error(message.error.message));
    else done(message.result);
  }
});
function call(method, params = {}) {
  const id = ++sequence;
  return new Promise((done, fail) => {
    waiting.set(id, { done, fail });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await call("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  return result.result?.value;
}
async function shot(name, hash, wait = 1600, full = false) {
  await call("Page.navigate", {
    url: `${mobileBase}?shot=${Date.now()}#/${hash}`,
  });
  await sleep(wait);
  let image;
  let height = 844;
  if (full) {
    const metrics = await call("Page.getLayoutMetrics");
    height = Math.ceil(metrics.cssContentSize?.height ?? 844);
    image = await call("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: 390, height, scale: 2 },
    });
  } else {
    image = await call("Page.captureScreenshot", { format: "png" });
  }
  writeFileSync(resolve(out, `${name}.png`), Buffer.from(image.data, "base64"));
  console.log("saved", `${name}.png`, `390x${height} @2x`);
}

await call("Page.enable");
await call("Runtime.enable");
await call("Emulation.setDeviceMetricsOverride", {
  width: 390,
  height: 844,
  deviceScaleFactor: 2,
  mobile: true,
});
await call("Emulation.setTouchEmulationEnabled", {
  enabled: true,
  maxTouchPoints: 5,
});

// 1. 登录页（未登录）
await shot("login", "pages/login/index", 1500);

// 2. 写入登录态（uni H5 的 string 直接存，object 包 type/data）
await call("Page.navigate", { url: mobileBase });
await sleep(1200);
await evaluate(`(() => {
  localStorage.setItem('vision.token', ${JSON.stringify(login.token)});
  localStorage.setItem('vision.user', JSON.stringify({ type: 'object', data: ${JSON.stringify(login.user)} }));
  localStorage.setItem('vision.server', ${JSON.stringify(mobileOrigin)});
  localStorage.setItem('vision.device', ${JSON.stringify("")});
  localStorage.setItem('vision.task', ${JSON.stringify("")});
  localStorage.setItem('vision.captureMode', 'BOARD');
  return 'ok';
})()`);

await shot("home", "pages/home/index", 2200);
await shot("tasks", "pages/tasks/index", 1800);
await shot("records", "pages/records/index", 2200);
await evaluate(`[...document.querySelectorAll('.filter')].find((el) => el.textContent.trim() === '真实')?.click()`);
await sleep(900);
await snap("records-real");
await shot("sync", "pages/sync/index", 1400);
await shot("pair", "pages/pair/index", 1400);
await shot("capture-board", "pages/capture/index", 2200);

// 手机相机模式：切到“手机采样”，启用实时相机
await call("Page.navigate", {
  url: `${mobileBase}?shot=${Date.now()}#/pages/capture/index`,
});
await sleep(1800);
const clickedMobile = await evaluate(`(() => {
  const nodes = [...document.querySelectorAll('.mode-switch uni-text, .mode-switch text, .mode-switch span')];
  const mobile = nodes.find((el) => el.textContent.trim() === '手机');
  mobile?.click();
  return mobile ? 'clicked' : 'not found';
})()`);
console.log("mode mobile:", clickedMobile);
await sleep(2200);
await call("Page.captureScreenshot", { format: "png" }).then((image) =>
  writeFileSync(
    resolve(out, "capture-mobile-camera.png"),
    Buffer.from(image.data, "base64"),
  ),
);
console.log("saved capture-mobile-camera.png 390x844 @2x");

// 同步模式
await call("Page.navigate", {
  url: `${mobileBase}?shot=${Date.now()}#/pages/capture/index`,
});
await sleep(1600);
const clickedSync = await evaluate(`(() => {
  const nodes = [...document.querySelectorAll('.mode-switch uni-text, .mode-switch text, .mode-switch span')];
  const sync = nodes.find((el) => el.textContent.trim() === '同步');
  sync?.click();
  return sync ? 'clicked' : 'not found';
})()`);
console.log("mode sync:", clickedSync);
await sleep(1600);
await call("Page.captureScreenshot", { format: "png" }).then((image) =>
  writeFileSync(
    resolve(out, "capture-sync.png"),
    Buffer.from(image.data, "base64"),
  ),
);
console.log("saved capture-sync.png 390x844 @2x");

await shot("live", "pages/live/index", 2200);

const inspectionId = inspections.items?.[0]?.id;
const sampleId = samples.items?.[0]?.id;
if (inspectionId)
  await shot(`detail`, `pages/detail/index?id=${inspectionId}`, 2200, true);
if (sampleId) await shot(`sample`, `pages/sample/index?id=${sampleId}`, 2200, true);

async function snap(name) {
  const image = await call("Page.captureScreenshot", { format: "png" });
  writeFileSync(resolve(out, `${name}.png`), Buffer.from(image.data, "base64"));
  console.log("saved", `${name}.png`, "390x844 @2x");
}

// 相机页的任务与设备抽屉
await call("Page.navigate", {
  url: `${mobileBase}?shot=${Date.now()}#/pages/capture/index`,
});
await sleep(1800);
await evaluate(`document.querySelector('.task-btn')?.click()`);
await sleep(500);
await snap("capture-sheet");

// 实时画面沉浸模式
await call("Page.navigate", {
  url: `${mobileBase}?shot=${Date.now()}#/pages/live/index`,
});
await sleep(2200);
await evaluate(`document.querySelector('.immersive-toggle')?.click()`);
await sleep(800);
await snap("live-immersive");

chrome.kill();
socket.close();
process.exit(0);
