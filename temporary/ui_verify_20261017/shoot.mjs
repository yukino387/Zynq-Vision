import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";

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
const username = process.env.SHOT_USER ?? "admin";
const shotWidth = Number(process.env.SHOT_WIDTH ?? 1440);
const shotHeight = Number(process.env.SHOT_HEIGHT ?? 1000);
if (!password) throw new Error("SEED_PASSWORD missing from .env");

const profile = resolve(out, "profile");
const chrome = spawn(
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  [
    "--headless=new",
    "--remote-debugging-port=9223",
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-gpu",
    "--hide-scrollbars",
    `--window-size=${shotWidth},${shotHeight + 100}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
async function endpoint(path) {
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      const response = await fetch(`http://127.0.0.1:9223${path}`);
      if (response.ok) return response.json();
    } catch {}
    await sleep(200);
  }
  throw new Error(`Chrome debugging endpoint ${path} unavailable`);
}
const targets = await endpoint("/json/list");
const page = targets.find((target) => target.type === "page");
if (!page) throw new Error("No page target");
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

await call("Page.enable");
await call("Runtime.enable");
await call("Emulation.setDeviceMetricsOverride", {
  width: shotWidth,
  height: shotHeight,
  deviceScaleFactor: 1,
  mobile: false,
});

await call("Page.navigate", { url: "http://127.0.0.1:5173/" });
await sleep(1500);
const login = await call("Runtime.evaluate", {
  expression: `(async () => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ username: ${JSON.stringify(username)}, password: ${JSON.stringify(password)} }),
    });
    if (!response.ok) return 'login failed ' + response.status;
    const data = await response.json();
    sessionStorage.setItem('vision.token', data.token);
    sessionStorage.setItem('vision.user', JSON.stringify(data.user));
    return data.user.role;
  })()`,
  awaitPromise: true,
  returnByValue: true,
});
console.log("login:", login.result?.value);

async function shot(name, hash, wait = 2600, script) {
  // 整页重载，让 auth.restore() 重新读取刚写入的 sessionStorage。
  await call("Page.navigate", {
    url: `http://127.0.0.1:5173/?shot=${Date.now()}#/${hash}`,
  });
  await sleep(wait);
  if (script) {
    const result = await call("Runtime.evaluate", {
      expression: script,
      awaitPromise: true,
      returnByValue: true,
    });
    console.log(`${name} setup:`, result.result?.value);
    await sleep(800);
  }
  const metrics = await call("Page.getLayoutMetrics");
  const height = Math.min(
    Math.ceil(metrics.cssContentSize?.height ?? 1000),
    2600,
  );
  const image = await call("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: 1440, height, scale: 1 },
  });
  writeFileSync(resolve(out, `${name}.png`), Buffer.from(image.data, "base64"));
  console.log("saved", `${name}.png`, `${shotWidth}x${height}`);
}

const workbenchSetup = `(() => {
  const select = document.querySelectorAll('.toolbar-field select')[0];
  if (!select || select.options.length < 2) return 'no tasks';
  select.value = select.options[1].value;
  select.dispatchEvent(new Event('change', { bubbles: true }));
  return select.options[1].textContent.trim();
})()`;
if (process.env.SHOT_ONLY === "workbench") {
  await shot(process.env.SHOT_NAME ?? "workbench", "workbench", 2800, workbenchSetup);
  const sizes = await call("Runtime.evaluate", {
    expression: `(() => {
      const rect = (selector) => {
        const el = document.querySelector(selector);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: Math.round(r.x), width: Math.round(r.width), height: Math.round(r.height) };
      };
      return JSON.stringify({
        viewport: { width: innerWidth, height: innerHeight },
        scrollWidth: document.documentElement.scrollWidth,
        grid: rect('.workbench-grid'),
        stage: rect('.workbench-stage'),
        canvas: rect('.vision-canvas'),
        imageStage: rect('.image-stage'),
        side: rect('.workbench-side'),
        toolbar: rect('.workbench-toolbar'),
        recent: rect('.recent-panel'),
        table: rect('.recent-panel table'),
        tableWrap: rect('.recent-panel .table-wrap'),
        confidence: rect('.detection-item strong'),
        confidenceCount: document.querySelectorAll('.detection-item strong').length,
        capture: rect('.workbench-capture'),
        heading: rect('.workbench-heading'),
        track: rect('.filmstrip-track'),
        thumb: rect('.frame-thumb'),
        frameCount: document.querySelectorAll('.frame-thumb').length,
      });
    })()`,
    returnByValue: true,
  });
  console.log("sizes:", sizes.result?.value);
} else {
  await shot("system-health", "system/health");
  await shot("system-pairing", "system/pairing");
  await shot("devices-registry", "diagnostics/registry");
  await shot("system-jobs", "system/jobs");
  await shot("workbench", "workbench", 2800, workbenchSetup);
}

chrome.kill();
socket.close();
process.exit(0);
