// 读取表格内指标单元格的实际计算样式，定位行高偏大的原因。
import { spawn } from "node:child_process";
import { route } from "./mock-api.mjs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://localhost:5173";
const PORT = 9334;
const profile = new URL(`./chrome-profile-${process.pid}`, import.meta.url).pathname.replace(/^\//, "");
const chrome = spawn(CHROME, [
  "--headless=new",
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`,
  "--no-first-run",
  "--disable-gpu",
  "about:blank",
]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let version;
for (let i = 0; i < 60 && !version; i++) {
  try {
    version = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
  } catch {
    await sleep(200);
  }
}
class CDP {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
    this.handlers = new Map();
    this.ws.addEventListener("message", (e) => {
      const m = JSON.parse(e.data);
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
        return;
      }
      for (const h of this.handlers.get(m.method) ?? []) h(m.params);
    });
  }
  open() {
    return new Promise((r) => this.ws.addEventListener("open", r, { once: true }));
  }
  on(m, h) {
    if (!this.handlers.has(m)) this.handlers.set(m, []);
    this.handlers.get(m).push(h);
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params, sessionId }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
}
const cdp = new CDP(version.webSocketDebuggerUrl);
await cdp.open();
const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
const s = (m, p) => cdp.send(m, p, sessionId);
await s("Page.enable");
await s("Runtime.enable");
await s("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
await s("Fetch.enable", { patterns: [{ urlPattern: "*/api/*", requestStage: "Request" }] });
cdp.on("Fetch.requestPaused", async ({ requestId, request }) => {
  const path = new URL(request.url, "http://127.0.0.1").pathname;
  await cdp.send(
    "Fetch.fulfillRequest",
    {
      requestId,
      responseCode: 200,
      responseHeaders: [{ name: "content-type", value: "application/json" }],
      body: Buffer.from(JSON.stringify(route(path))).toString("base64"),
    },
    sessionId,
  );
});
await s("Page.navigate", { url: `${BASE}/` });
await sleep(1200);
await s("Runtime.evaluate", {
  expression: `sessionStorage.setItem('vision.token','mock');sessionStorage.setItem('vision.user',JSON.stringify({id:'usr_admin',name:'YUKINO',role:'ADMIN'}));`,
});
await s("Page.navigate", { url: "about:blank" });
await sleep(150);
await s("Page.navigate", { url: `${BASE}/#/models/registry` });
await sleep(2200);
const result = await s("Runtime.evaluate", {
  returnByValue: true,
  expression: `(() => {
    const tr = document.querySelector('tbody tr');
    const txt = document.body.innerText.slice(0, 200);
    const dl = document.querySelector('.cell-metrics .detail-fields');
    const dt = dl?.querySelector('dt');
    const out = {
      rowHeight: tr?.getBoundingClientRect().height, txt,
      dlGrid: dl && getComputedStyle(dl).gridTemplateColumns,
      dlGap: dl && getComputedStyle(dl).rowGap,
      dtPadding: dt && getComputedStyle(dt).padding,
      dtHeight: dt?.getBoundingClientRect().height,
      dtFont: dt && getComputedStyle(dt).fontSize,
      cells: [...(tr?.children ?? [])].map((td) => Math.round(td.getBoundingClientRect().height)),
    };
    return JSON.stringify(out);
  })()`,
});
console.log(result.result.value);
chrome.kill();
process.exit(0);
