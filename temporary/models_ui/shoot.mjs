// 用 CDP 驱动无头 Chrome 截取模型与发布各子页，仅用于本地核对显示效果。
import { spawn } from "node:child_process";
import { route } from "./mock-api.mjs";
import { mkdirSync, writeFileSync } from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = new URL("./shots/", import.meta.url).pathname.replace(/^\//, "");
const BASE = process.env.BASE ?? "http://localhost:5173";
const PORT = 9333;
const profile = new URL(
  `./chrome-profile-${process.pid}`,
  import.meta.url,
).pathname.replace(/^\//, "");

const targets = process.argv.slice(2).length
  ? process.argv.slice(2)
  : ["registry", "training", "benchmarks", "deployments"];

mkdirSync(OUT, { recursive: true });

const chrome = spawn(CHROME, [
  "--headless=new",
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`,
  "--no-first-run",
  "--disable-gpu",
  "--hide-scrollbars",
  "about:blank",
]);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function version() {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      return await res.json();
    } catch {
      await sleep(200);
    }
  }
  throw new Error("chrome did not start");
}

class CDP {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
    this.handlers = new Map();
    this.ws.addEventListener("message", (e) => {
      const msg = JSON.parse(e.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
        return;
      }
      for (const handler of this.handlers.get(msg.method) ?? []) handler(msg.params);
    });
  }
  open() {
    return new Promise((r) => this.ws.addEventListener("open", r, { once: true }));
  }
  on(method, handler) {
    if (!this.handlers.has(method)) this.handlers.set(method, []);
    this.handlers.get(method).push(handler);
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params, sessionId }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
}

const { webSocketDebuggerUrl } = await version();
const cdp = new CDP(webSocketDebuggerUrl);
await cdp.open();

const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
const s = (method, params) => cdp.send(method, params, sessionId);

await s("Page.enable");
await s("Runtime.enable");
await s("Emulation.setDeviceMetricsOverride", {
  width: 1440,
  height: 1000,
  deviceScaleFactor: 1.5,
  mobile: false,
});

// 直接在浏览器侧拦住接口请求，用假数据应答；不启动任何本地服务。
await s("Fetch.enable", {
  patterns: [{ urlPattern: "*/api/*", requestStage: "Request" }],
});
cdp.on("Fetch.requestPaused", async (event) => {
  const { requestId, request } = event;
  const path = new URL(request.url, "http://127.0.0.1").pathname;
  const body = Buffer.from(JSON.stringify(route(path))).toString("base64");
  await cdp.send(
    "Fetch.fulfillRequest",
    {
      requestId,
      responseCode: 200,
      responseHeaders: [
        { name: "content-type", value: "application/json" },
        { name: "cache-control", value: "no-store" },
      ],
      body,
    },
    sessionId,
  );
});

await s("Page.navigate", { url: `${BASE}/` });
await sleep(1500);
await s("Runtime.evaluate", {
  expression:
    `sessionStorage.setItem('vision.token','mock');` +
    `sessionStorage.setItem('vision.user', JSON.stringify({id:'usr_admin',name:'YUKINO',role:'ADMIN'}));`,
});

const shots = [];
for (const spec of targets) {
  const [tab, clickText] = spec.split("@");
  // 先离开再回来，强制整页重新加载，让登录态在挂载时生效
  await s("Page.navigate", { url: "about:blank" });
  await sleep(120);
  await s("Page.navigate", { url: `${BASE}/#/models/${tab}` });
  await sleep(2200);
  if (clickText) {
    const r = await s("Runtime.evaluate", {
      returnByValue: true,
      expression: `(() => {
        const el = [...document.querySelectorAll('button, a')]
          .find((e) => e.textContent.trim().includes(${JSON.stringify(clickText)}));
        if (!el) return 'missing';
        el.click();
        return 'clicked';
      })()`,
    });
    console.log(spec, r.result.value);
    await sleep(1200);
    // 浮层里再滚动到顶部，保证截图从第一屏开始
    await s("Runtime.evaluate", {
      expression: `document.querySelector('.drawer-body')?.scrollTo(0, 0)`,
    });
  }
  // 展开接口下拉之外的浮层不需要，直接按整页高度截图
  const { contentSize } = await s("Page.getLayoutMetrics");
  const height = Math.min(Math.ceil(contentSize.height), 4000);
  const { data } = await s("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: 1440, height, scale: 1.5 },
  });
  const file = `${OUT}models-${spec.replace(/[^\w\u4e00-\u9fa5-]/g, "_")}.png`;
  writeFileSync(file, Buffer.from(data, "base64"));
  shots.push(file);
  console.log("saved", file);
}

chrome.kill();
process.exit(0);
