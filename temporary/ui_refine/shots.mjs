import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import WebSocket from "../../apps/server/node_modules/ws/index.js";

const root = new URL("../../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const env = Object.fromEntries(
  readFileSync(`${root}/.env`, "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const i = line.indexOf("=");
      return [line.slice(0, i), line.slice(i + 1)];
    }),
);
const login = await fetch("http://localhost:3000/api/auth/login", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ username: "admin", password: env.SEED_PASSWORD }),
});
const session = await login.json();
const shots = `${root}/temporary/ui_refine/screens`;
mkdirSync(shots, { recursive: true });
const profile = `${root}/temporary/ui_refine/profile`;
mkdirSync(profile, { recursive: true });
const chrome = spawn(
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=9231",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let version;
for (let i = 0; i < 40; i++) {
  try {
    version = await (await fetch("http://127.0.0.1:9231/json/version")).json();
    break;
  } catch {
    await sleep(250);
  }
}
const targets = await (await fetch("http://127.0.0.1:9231/json/list")).json();
const socket = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.once("open", resolve);
  socket.once("error", reject);
});
let id = 0;
const pending = new Map();
socket.on("message", (data) => {
  const message = JSON.parse(String(data));
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
});
const call = (method, params = {}, timeout = 20000) =>
  new Promise((resolve, reject) => {
    const requestId = ++id;
    const timer = setTimeout(() => {
      pending.delete(requestId);
      reject(new Error(`${method} timeout`));
    }, timeout);
    pending.set(requestId, (message) => {
      clearTimeout(timer);
      resolve(message);
    });
    socket.send(JSON.stringify({ id: requestId, method, params }));
  });
const evaluate = async (expression, timeout) =>
  (await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, timeout)).result?.result?.value;
const shot = async (name) => {
  const result = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: true }, 30000);
  writeFileSync(`${shots}/${name}.png`, Buffer.from(result.result.data, "base64"));
  console.log("saved", name);
};
await call("Runtime.enable");
await call("Page.enable");
await call("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await call("Page.navigate", { url: "http://localhost:3000/" });
await sleep(1200);
await evaluate(
  `sessionStorage.setItem('vision.token', ${JSON.stringify(session.token)}); sessionStorage.setItem('vision.user', ${JSON.stringify(JSON.stringify(session.user))}); 'ok'`,
);
await call("Page.reload");
await sleep(3500);
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.trim()==='菜单')?.click()`);
await sleep(500);
await evaluate(`Array.from(document.querySelectorAll('a,button')).find(a=>a.innerText.includes('设备诊断'))?.click()`);
await sleep(500);
await evaluate(`Array.from(document.querySelectorAll('a,button')).find(e=>e.innerText.trim()==='设备')?.click()`);
await sleep(3000);
await shot("desktop-light-page");
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes('控制与详情'))?.click()`);
await sleep(1200);
await shot("desktop-light-drawer");
await evaluate(`document.querySelector('[role="dialog"] button[aria-label="关闭"]')?.click()`);
await sleep(400);
await call("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
await sleep(800);
await shot("desktop-dark-page");
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes('控制与详情'))?.click()`);
await sleep(1200);
await shot("desktop-dark-drawer");
await call("Emulation.setEmulatedMedia", { features: [] });
await call("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await call("Page.navigate", { url: "http://localhost:3000/" });
await sleep(3500);
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.trim()==='菜单')?.click()`);
await sleep(500);
await evaluate(`Array.from(document.querySelectorAll('a,button')).find(a=>a.innerText.includes('设备诊断'))?.click()`);
await sleep(500);
await evaluate(`Array.from(document.querySelectorAll('a,button')).find(e=>e.innerText.trim()==='设备')?.click()`);
await sleep(3000);
await shot("mobile-light-page");
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes('控制与详情'))?.click()`);
await sleep(1200);
await shot("mobile-light-drawer");
console.log("done");
socket.close();
chrome.kill();
process.exit(0);
