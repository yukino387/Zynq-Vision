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
if (!login.ok) throw new Error(`login ${login.status}`);
const session = await login.json();
console.log("login", session.user.role);

const profile = `${root}/temporary/device_page_check/profile`;
mkdirSync(profile, { recursive: true });
const chrome = spawn(
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-debugging-port=9229",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let version;
for (let i = 0; i < 40; i++) {
  try {
    version = await (await fetch("http://127.0.0.1:9229/json/version")).json();
    break;
  } catch {
    await sleep(250);
  }
}
if (!version) throw new Error("chrome did not start");
const targets = await (await fetch("http://127.0.0.1:9229/json/list")).json();
const page = targets.find((t) => t.type === "page");
const socket = new WebSocket(page.webSocketDebuggerUrl);
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
  if (message.method === "Runtime.exceptionThrown")
    console.log("EXCEPTION", message.params.exceptionDetails?.exception?.description?.slice(0, 400));
  if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error")
    console.log("CONSOLE", message.params.args?.map((a) => a.value ?? a.description).join(" ").slice(0, 400));
  if (message.method === "Log.entryAdded" && message.params.entry.level === "error")
    console.log("LOG", message.params.entry.text?.slice(0, 400));
});
const call = (method, params = {}, timeout = 8000) =>
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
const evaluate = async (expression, timeout) => {
  const result = await call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, timeout);
  return result.result?.result?.value;
};
await call("Runtime.enable");
await call("Page.enable");
await call("Log.enable");
await call("Page.navigate", { url: `${origin}/` });
await sleep(1200);
await evaluate(
  `sessionStorage.setItem('vision.token', ${JSON.stringify(session.token)}); sessionStorage.setItem('vision.user', ${JSON.stringify(JSON.stringify(session.user))}); 'ok'`,
);
await call("Page.reload");
await sleep(3500);
console.log("home", await evaluate(`JSON.stringify({title:document.title,h1:document.querySelector('h1')?.innerText,links:Array.from(document.querySelectorAll('a')).map(a=>a.innerText.trim()).filter(Boolean).slice(0,20)})`));
console.log(
  "menu",
  await evaluate(`(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.innerText.trim()==='菜单');if(!b)return 'no-menu';b.click();return 'opened'})()`),
);
await sleep(800);
console.log(
  "navLinks",
  await evaluate(`JSON.stringify(Array.from(document.querySelectorAll('a')).map(a=>a.innerText.trim().split('\\n').pop()).filter(Boolean).slice(0,30))`),
);
console.log(
  "nav",
  await evaluate(`(()=>{const a=Array.from(document.querySelectorAll('a,button')).find(a=>a.innerText.includes('设备诊断'));if(!a)return 'no-link';a.click();return 'clicked'})()`),
);
await sleep(800);
console.log(
  "subTab",
  await evaluate(`(()=>{const candidates=Array.from(document.querySelectorAll('a,button')).filter(e=>e.innerText.trim()==='设备');return JSON.stringify(candidates.map(e=>({tag:e.tagName,cls:e.className,href:e.getAttribute('href')})))+' picked='+(candidates[0]?(candidates[0].click(),'yes'):'no')})()`),
);
await sleep(3000);
console.log("devicePage", await evaluate(`JSON.stringify({h1:document.querySelector('h1')?.innerText,text:document.body.innerText.slice(0,700),buttons:Array.from(document.querySelectorAll('button')).map(b=>b.innerText.trim()).filter(Boolean).slice(0,20),nodes:document.querySelectorAll('*').length})`));
console.log(
  "openDrawer",
  await evaluate(`(()=>{const b=Array.from(document.querySelectorAll('button')).find(b=>b.innerText.includes('控制与详情'));if(!b)return 'no-button';b.click();return 'clicked'})()`),
);
await evaluate(`window.__gaps=[];window.__long=[];window.__last=performance.now();window.__hb=setInterval(()=>{const n=performance.now();if(n-window.__last>100)window.__gaps.push(Math.round(n-window.__last));window.__last=n;},50);if(window.PerformanceObserver){const o=new PerformanceObserver(l=>{for(const e of l.getEntries())window.__long.push(Math.round(e.duration))});o.observe({entryTypes:['longtask']});window.__po=o} 'ok'`);
await sleep(8000);
try {
  console.log("perf", await evaluate(`JSON.stringify({gaps:window.__gaps,long:window.__long.slice(-20),heap:performance.memory?Math.round(performance.memory.usedJSHeapSize/1048576):null,nodes:document.querySelectorAll('*').length,dialog:!!document.querySelector('[role="dialog"]')})`, 10000));
} catch (error) {
  console.log("PERF", String(error));
}
try {
  console.log("responsive", await evaluate("1+1", 5000));
} catch (error) {
  console.log("RESPONSIVE", String(error));
}
await evaluate(`document.querySelector('[role="dialog"] button[aria-label="关闭"]')?.click()`);
await sleep(500);
console.log(
  "debugTab",
  await evaluate(`(()=>{const a=Array.from(document.querySelectorAll('a')).find(a=>a.innerText.trim()==='实时事件');if(!a)return 'no-link';a.click();return 'clicked'})()`),
);
await sleep(6000);
try {
  console.log("debugPage", await evaluate(`JSON.stringify({h1:document.querySelector('h1')?.innerText,nodes:document.querySelectorAll('*').length,pres:document.querySelectorAll('pre').length})`, 6000));
  console.log("debugResponsive", await evaluate("1+1", 3000));
} catch (error) {
  console.log("DEBUG", String(error));
}
console.log(
  "eventTab",
  await evaluate(`(()=>{const a=Array.from(document.querySelectorAll('a')).find(a=>a.innerText.trim()==='设备事件');if(!a)return 'no-link';a.click();return 'clicked'})()`),
);
await sleep(2500);
try {
  console.log("eventPage", await evaluate(`JSON.stringify({h1:document.querySelector('h1')?.innerText,nodes:document.querySelectorAll('*').length})`, 5000));
} catch (error) {
  console.log("EVENT", String(error));
}
socket.close();
chrome.kill();
process.exit(0);
