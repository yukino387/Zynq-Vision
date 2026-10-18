import { readFileSync, mkdirSync } from "node:fs";
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
const origin = process.env.ORIGIN ?? "http://localhost:3000";
const login = await fetch("http://localhost:3000/api/auth/login", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ username: "admin", password: env.SEED_PASSWORD }),
});
const session = await login.json();
const profile = `${root}/temporary/device_page_check/profile`;
mkdirSync(profile, { recursive: true });
const chrome = spawn(
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=9230",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let version;
for (let i = 0; i < 40; i++) {
  try {
    version = await (await fetch("http://127.0.0.1:9230/json/version")).json();
    break;
  } catch {
    await sleep(250);
  }
}
const targets = await (await fetch("http://127.0.0.1:9230/json/list")).json();
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
const call = (method, params = {}, timeout = 15000) =>
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
await call("Runtime.enable");
await call("Page.enable");
await call("Page.navigate", { url: `${origin}/` });
await sleep(1200);
await evaluate(
  `sessionStorage.setItem('vision.token', ${JSON.stringify(session.token)}); sessionStorage.setItem('vision.user', ${JSON.stringify(JSON.stringify(session.user))}); 'ok'`,
);
await call("Page.reload");
await sleep(3500);
await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.innerText.trim()==='菜单')?.click()`);
await sleep(600);
await evaluate(`Array.from(document.querySelectorAll('a,button')).find(a=>a.innerText.includes('设备诊断'))?.click()`);
await sleep(600);
await evaluate(`Array.from(document.querySelectorAll('a,button')).find(e=>e.innerText.trim()==='设备')?.click()`);
await sleep(3000);

await call("Profiler.enable");
await call("Profiler.setSamplingInterval", { interval: 200 });
await call("Profiler.start");
console.log("drawer", await evaluate(`(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes('控制与详情'));if(!b)return 'no-button';b.click();return 'clicked'})()`));
await sleep(6000);
const result = await call("Profiler.stop", {}, 30000);
const profileData = result.result?.profile;
const nodes = new Map((profileData?.nodes ?? []).map((node) => [node.id, node]));
const self = new Map();
const deltas = profileData?.timeDeltas ?? [];
const samples = profileData?.samples ?? [];
for (let i = 0; i < samples.length; i++) {
  const node = nodes.get(samples[i]);
  if (!node) continue;
  const frame = node.callFrame;
  const key = `${frame.functionName || "(anonymous)"} @ ${frame.url.split("/").pop()}:${frame.lineNumber + 1}`;
  self.set(key, (self.get(key) ?? 0) + (deltas[i] ?? 0));
}
const top = [...self.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20);
for (const [key, us] of top) console.log((us / 1000).toFixed(0).padStart(6), "ms ", key);
socket.close();
chrome.kill();
process.exit(0);
