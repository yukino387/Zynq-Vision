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
const login = await fetch("http://localhost:3000/api/auth/login", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ username: "admin", password: env.SEED_PASSWORD }),
});
if (!login.ok) throw new Error(`login ${login.status}`);
const session = await login.json();
const profile = `${root}/temporary/firmware_platform/profile`;
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
if (!version) throw new Error("chrome did not start");
const targets = await (await fetch("http://127.0.0.1:9231/json/list")).json();
const page = targets.find((t) => t.type === "page");
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.once("open", resolve);
  socket.once("error", reject);
});
let id = 0;
const pending = new Map();
const errors = [];
socket.on("message", (data) => {
  const message = JSON.parse(String(data));
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
  if (message.method === "Runtime.exceptionThrown")
    errors.push(message.params.exceptionDetails?.exception?.description?.slice(0, 400));
  if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error")
    errors.push(message.params.args?.map((a) => a.value ?? a.description).join(" ").slice(0, 400));
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
await call("Page.navigate", { url: "http://localhost:3000/" });
await sleep(1200);
await evaluate(
  `sessionStorage.setItem('vision.token', ${JSON.stringify(session.token)}); sessionStorage.setItem('vision.user', ${JSON.stringify(JSON.stringify(session.user))}); 'ok'`,
);
await call("Page.reload");
await sleep(3000);
for (const path of ["/firmware/registry", "/firmware/deployments"]) {
  await evaluate(`location.hash = ${JSON.stringify(`#${path}`)}`);
  await sleep(2500);
  const pageState = await evaluate(
    `JSON.stringify({title:document.title,h1:document.querySelector('h1')?.innerText,hasNav:document.body.innerText.includes('固件与更新'),upload:document.body.innerText.includes('上传固件包'),text:document.body.innerText.slice(0,320)})`,
  );
  console.log(path, pageState);
}
console.log("errors", JSON.stringify(errors));
socket.close();
chrome.kill();
process.exit(0);
