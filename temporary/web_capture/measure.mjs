// 找出在窄屏下撑宽页面的元素。
import { spawn } from "node:child_process";
import path from "node:path";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const FILE = process.argv[3]
  ? `file:///${process.argv[3].replace(/\\/g, "/")}`
  : "file:///C:/00_workplace/fpga/cnn_accelerator/temporary/web_capture/ui.html";
const PORT = 9333;
const WIDTH = Number(process.argv[2] ?? 420);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(fn, timeout = 20000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    try {
      const v = await fn();
      if (v) return v;
    } catch {}
    await sleep(250);
  }
  throw new Error("timeout");
}

const chrome = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    `--user-data-dir=${path.resolve("profile-measure")}`,
    `--window-size=${WIDTH},1200`,
    "about:blank",
  ],
  { stdio: "ignore" },
);

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
    width: WIDTH,
    height: 1200,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp.send("Page.navigate", { url: FILE });
  await sleep(3000);

  const report = await cdp.eval(`(() => {
    const doc = document.documentElement;
    const limit = doc.clientWidth;
    const out = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.right > limit + 1) {
        out.push({
          tag: el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\\s+/).join(".") : ""),
          right: Math.round(r.right),
          width: Math.round(r.width),
        });
      }
    }
    return { viewport: limit, scrollWidth: doc.scrollWidth, bodyScroll: document.body.scrollWidth, offenders: out.slice(0, 12) };
  })()`);

  console.log(`视口 ${report.viewport}  documentElement.scrollWidth=${report.scrollWidth}  body.scrollWidth=${report.bodyScroll}`);
  if (!report.offenders.length) console.log("没有元素越界");
  for (const o of report.offenders) console.log(`  right=${String(o.right).padStart(5)} w=${String(o.width).padStart(5)}  ${o.tag}`);
} finally {
  chrome.kill();
}
