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
const dir = `${root}/temporary/ui_refine`;
mkdirSync(dir, { recursive: true });
const profile = `${dir}/pair-profile`;
mkdirSync(profile, { recursive: true });
const chrome = spawn(
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=9232",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let version;
for (let i = 0; i < 40; i++) {
  try {
    version = await (await fetch("http://127.0.0.1:9232/json/version")).json();
    break;
  } catch {
    await sleep(250);
  }
}
const targets = await (await fetch("http://127.0.0.1:9232/json/list")).json();
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
  writeFileSync(`${dir}/screens/${name}.png`, Buffer.from(result.result.data, "base64"));
};
await call("Runtime.enable");
await call("Page.enable");
await call("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
await call("Page.navigate", { url: "http://localhost:3000/" });
await sleep(1000);
await evaluate(
  `sessionStorage.setItem('vision.token', ${JSON.stringify(session.token)}); sessionStorage.setItem('vision.user', ${JSON.stringify(JSON.stringify(session.user))}); 'ok'`,
);
await call("Page.reload");
await sleep(3200);
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.trim()==='菜单')?.click()`);
await sleep(500);
await evaluate(`Array.from(document.querySelectorAll('a,button')).find(a=>a.innerText.includes('系统管理'))?.click()`);
await sleep(500);
await evaluate(`Array.from(document.querySelectorAll('a,button')).find(a=>a.innerText.trim()==='移动端配对')?.click()`);
await sleep(2500);

const read = () =>
  evaluate(`(()=>{const t=document.querySelector('textarea[readonly]');const qr=document.querySelector('img[alt="配对二维码"]');return JSON.stringify({payload:t?.value?JSON.parse(t.value):null,qr:!!qr,note:Array.from(document.querySelectorAll('p.note')).map(p=>p.innerText),tag:document.querySelector('.panel-head .tag')?.innerText,stationSelect:Array.from(document.querySelectorAll('.panel select')).map(s=>({options:[...s.options].map(o=>o.text),value:s.value})),buttons:Array.from(document.querySelectorAll('.pairing-switch button')).map(b=>b.innerText.trim())})})()`);

console.log("server", await evaluate(`(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes('生成二维码'));b?.click();return !!b})()`));
await sleep(1200);
console.log("server-state", await read());
await shot("pairing-server");

await evaluate(`Array.from(document.querySelectorAll('.pairing-switch button')).find(b=>b.innerText.includes('工位快捷选择'))?.click()`);
await sleep(400);
console.log("station-select", await evaluate(`(()=>{const s=Array.from(document.querySelectorAll('.panel select')).find(s=>[...s.options].some(o=>o.text.includes('工位'))||[...s.options].some(o=>o.value));const o=[...s.options].find(o=>o.value);if(!o)return 'no-option';s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));return o.text})()`));
await sleep(200);
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes('生成二维码'))?.click()`);
await sleep(1000);
console.log("station-state", await read());
await shot("pairing-station");

await evaluate(`Array.from(document.querySelectorAll('.pairing-switch button')).find(b=>b.innerText.includes('设备快捷选择'))?.click()`);
await sleep(400);
console.log("device-select", await evaluate(`(()=>{const s=Array.from(document.querySelectorAll('.panel select')).find(s=>[...s.options].some(o=>o.text.includes('Zynq'))||[...s.options].some(o=>o.value));const o=[...s.options].find(o=>o.value);if(!o)return 'no-option';s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));return o.text})()`));
await sleep(200);
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes('生成二维码'))?.click()`);
await sleep(1000);
console.log("device-state", await read());
await shot("pairing-device");
socket.close();
chrome.kill();
process.exit(0);
