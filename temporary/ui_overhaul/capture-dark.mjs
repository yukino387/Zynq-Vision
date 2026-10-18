// 用无头 Chrome + CDP 截取当前前端各页面。不新增依赖：Node 22 自带 WebSocket 与 fetch。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = "C:/00_workplace/fpga/cnn_accelerator";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const DEV = "http://localhost:3000";
const API = "http://localhost:3000";
const PORT = 9222;
const OUT = path.join(ROOT, "temporary/ui_overhaul/shots/dark");
const PROFILE = path.join(ROOT, "temporary/web_capture/profile");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitFor(fn, { timeout = 20000, interval = 250, label = "条件" } = {}) {
  const deadline = Date.now() + timeout;
  let last;
  while (Date.now() < deadline) {
    try {
      const v = await fn();
      if (v) return v;
    } catch (e) {
      last = e;
    }
    await sleep(interval);
  }
  throw new Error(`等待超时: ${label}${last ? ` (${last.message})` : ""}`);
}

function readEnv() {
  const text = fs.readFileSync(path.join(ROOT, ".env"), "utf8");
  const out = {};
  for (const line of text.split(/\r?\n/)) {
    if (!line.includes("=") || line.trimStart().startsWith("#")) continue;
    const at = line.indexOf("=");
    out[line.slice(0, at).trim()] = line.slice(at + 1).trim();
  }
  return out;
}

async function login(password) {
  const r = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username: "admin", password }),
  });
  if (!r.ok) throw new Error(`登录失败 HTTP ${r.status}`);
  const body = await r.json();
  if (!body.token) throw new Error("登录响应中没有 token");
  return body.token;
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.seq = 0;
    this.pending = new Map();
    ws.addEventListener("message", (e) => {
      const msg = JSON.parse(e.data);
      if (!msg.id || !this.pending.has(msg.id)) return;
      const { resolve, reject } = this.pending.get(msg.id);
      this.pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
    });
  }
  send(method, params = {}) {
    const id = ++this.seq;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  async eval(expression) {
    const r = await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
    return r.result.value;
  }
}

fs.mkdirSync(OUT, { recursive: true });
const token = await login(readEnv().SEED_PASSWORD);

const chrome = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${PROFILE}`,
    "--window-size=1600,1000",
    "about:blank",
  ],
  { stdio: "ignore" },
);

try {
  let wsUrl;
  await waitFor(
    async () => {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) {
        wsUrl = page.webSocketDebuggerUrl;
        return true;
      }
      return false;
    },
    { label: "Chrome 调试端口" },
  );

  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", rej);
  });
  const cdp = new Cdp(ws);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1600,
    height: 1400,
    deviceScaleFactor: 1,
    mobile: false,
  });

  await cdp.send("Page.navigate", { url: `${DEV}/` });
  await waitFor(async () => (await cdp.eval("document.readyState")) === "complete", { label: "首次加载" });
  await cdp.eval(`sessionStorage.setItem("vision.token", ${JSON.stringify(token)})`);
  await cdp.send("Page.reload", { ignoreCache: false });
  await waitFor(async () => (await cdp.eval("document.readyState")) === "complete", { label: "带 token 重载" });
  await sleep(800);
  await cdp.eval(`document.documentElement.setAttribute("data-theme","dark")`);
  await sleep(600);

  const routes = [
    ["overview", "/overview"],
    ["workbench", "/workbench"],
    ["records", "/records"],
    ["data", "/data"],
    ["models", "/models"],
    ["diagnostics", "/diagnostics"],
    ["system", "/system"],
  ];

  for (const [name, route] of routes) {
    await cdp.send("Page.navigate", { url: `${DEV}/#${route}` });
    await sleep(2800);
    const shot = await cdp.send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, `${name}.png`), Buffer.from(shot.data, "base64"));
    const nodes = await cdp.eval("document.querySelectorAll('*').length");
    const text = await cdp.eval("(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,160)");
    console.log(`${name.padEnd(12)} DOM=${String(nodes).padStart(5)}  ${text}`);
  }
} finally {
  chrome.kill();
}
