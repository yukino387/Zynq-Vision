// 角色可见性验证：三个账号分别登录，读出侧栏导航与各视图 tab 条。
// Phase 3 是纯重构，这里读到的结果必须与旧的角色表达式完全一致。
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = "C:/00_workplace/fpga/cnn_accelerator";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const DEV = "http://localhost:3000";
const API = "http://localhost:3000";
const PORT = 9555;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(fn, timeout = 20000) {
  const end = Date.now() + timeout;
  let last;
  while (Date.now() < end) {
    try {
      const v = await fn();
      if (v) return v;
    } catch (e) {
      last = e;
    }
    await sleep(250);
  }
  throw new Error("timeout " + (last?.message ?? ""));
}

const env = Object.fromEntries(
  fs
    .readFileSync(path.join(ROOT, ".env"), "utf8")
    .split(/\r?\n/)
    .filter((l) => l.includes("=") && !l.trimStart().startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i).trim(), l.slice(i + 1).trim()];
    }),
);

async function token(username) {
  const r = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username, password: env.SEED_PASSWORD }),
  });
  if (!r.ok) throw new Error(`登录 ${username} 失败 HTTP ${r.status}`);
  return (await r.json()).token;
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.seq = 0;
    this.pending = new Map();
    ws.addEventListener("message", (e) => {
      const m = JSON.parse(e.data);
      if (!m.id || !this.pending.has(m.id)) return;
      const { resolve, reject } = this.pending.get(m.id);
      this.pending.delete(m.id);
      m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
    });
  }
  send(method, params = {}) {
    const id = ++this.seq;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((res, rej) => this.pending.set(id, { resolve: res, reject: rej }));
  }
  async eval(expression) {
    const r = await this.send("Runtime.evaluate", { expression, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
    return r.result.value;
  }
}

const chrome = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    `--user-data-dir=${path.resolve(ROOT, "temporary/ui_overhaul/profile-roles")}`,
    "--window-size=1440,900",
    "about:blank",
  ],
  { stdio: "ignore" },
);

const readNav = `[...document.querySelectorAll(".sidebar nav a")].map(a => a.textContent.trim())`;
const readTabs = `[...document.querySelectorAll(".tabs a")].map(a => a.textContent.trim())`;
const readTitle = `document.querySelector(".topbar > span")?.textContent.trim() ?? ""`;

try {
  let wsUrl;
  await waitFor(async () => {
    const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    const p = list.find((t) => t.type === "page");
    if (p?.webSocketDebuggerUrl) {
      wsUrl = p.webSocketDebuggerUrl;
      return true;
    }
    return false;
  });
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", rej);
  });
  const cdp = new Cdp(ws);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });

  for (const username of ["admin", "engineer", "operator"]) {
    const jwt = await token(username);
    await cdp.send("Page.navigate", { url: `${DEV}/` });
    await waitFor(async () => (await cdp.eval("document.readyState")) === "complete");
    await cdp.eval(`sessionStorage.setItem("vision.token", ${JSON.stringify(jwt)})`);
    await cdp.send("Page.reload");
    await waitFor(async () => (await cdp.eval("document.readyState")) === "complete");
    await sleep(1800);

    console.log(`\n──── ${username} ────`);
    console.log(`侧栏  ${JSON.stringify(await cdp.eval(readNav))}`);
    console.log(`顶栏标题  ${await cdp.eval(readTitle)}`);
    console.log(`落地 #/  → ${await cdp.eval(`location.hash || "(空)"`)}`);

    for (const route of ["data", "models", "diagnostics", "system"]) {
      await cdp.send("Page.navigate", { url: `${DEV}/#/${route}` });
      await sleep(2200);
      const tabs = await cdp.eval(readTabs);
      console.log(`  /${route}  tabs=${JSON.stringify(tabs)}`);
    }

    await cdp.send("Page.navigate", { url: `${DEV}/#/nope-does-not-exist` });
    await sleep(1500);
    const body = await cdp.eval(
      `(document.querySelector("main")?.innerText ?? "").replace(/\\s+/g, " ").slice(0, 50)`,
    );
    console.log(`  #/nope-does-not-exist → ${JSON.stringify(body)}`);
  }
} finally {
  chrome.kill();
}
