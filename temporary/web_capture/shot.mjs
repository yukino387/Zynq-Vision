// 截取指定元素的高清图。用法: node shot.mjs <元素选择器> <输出名> [宽]
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const SELECTOR = process.argv[2] ?? ".screen";
const OUTNAME = process.argv[3] ?? "clip.png";
const WIDTH = Number(process.argv[4] ?? 1340);
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const FILE = "file:///C:/00_workplace/fpga/cnn_accelerator/temporary/web_capture/ui.html";
const PORT = 9444;

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

const chrome = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    `--user-data-dir=${path.resolve("profile-shot")}`,
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
    deviceScaleFactor: 2,
    mobile: false,
  });
  await cdp.send("Page.navigate", { url: FILE });
  await sleep(3500);

  const idx = Number(process.argv[5] ?? 0);
  const box = await cdp.eval(`(() => {
    const el = document.querySelectorAll(${JSON.stringify(SELECTOR)})[${idx}];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left + scrollX, y: r.top + scrollY, width: r.width, height: r.height };
  })()`);
  if (!box) throw new Error("未找到元素 " + SELECTOR);
  const shot = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
    clip: { x: box.x, y: box.y, width: box.width, height: box.height, scale: 1 },
  });
  fs.writeFileSync(OUTNAME, Buffer.from(shot.data, "base64"));
  console.log(`${OUTNAME}  ${Math.round(box.width)}×${Math.round(box.height)}`);
} finally {
  chrome.kill();
}
