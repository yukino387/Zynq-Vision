import { spawn } from "node:child_process";
import fs from "node:fs";
const ROOT = "C:/00_workplace/fpga/cnn_accelerator";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const env = Object.fromEntries(fs.readFileSync(`${ROOT}/.env`,"utf8").split(/\r?\n/).filter(l=>l.includes("=")&&!l.trimStart().startsWith("#")).map(l=>{const i=l.indexOf("=");return [l.slice(0,i).trim(),l.slice(i+1).trim()]}));
const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));
const jwt = (await (await fetch("http://localhost:3000/api/auth/login",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({username:"admin",password:env.SEED_PASSWORD})})).json()).token;
const chrome = spawn(CHROME,[`--remote-debugging-port=9666`,"--headless=new","--disable-gpu","--no-first-run",`--user-data-dir=${ROOT}/temporary/ui_overhaul/profile-t`,`--window-size=1400,900`,"about:blank"],{stdio:"ignore"});
let wsUrl; for(let i=0;i<60;i++){try{const l=await (await fetch("http://127.0.0.1:9666/json/list")).json();const p=l.find(t=>t.type==="page");if(p?.webSocketDebuggerUrl){wsUrl=p.webSocketDebuggerUrl;break}}catch{}await sleep(250)}
const ws=new WebSocket(wsUrl); await new Promise(r=>ws.addEventListener("open",r));
let seq=0; const pend=new Map();
ws.addEventListener("message",e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){const{res,rej}=pend.get(m.id);pend.delete(m.id);m.error?rej(new Error(JSON.stringify(m.error))):res(m.result)}});
const send=(method,params={})=>{const id=++seq;ws.send(JSON.stringify({id,method,params}));return new Promise((res,rej)=>pend.set(id,{res,rej}))};
const ev=async(x)=>(await send("Runtime.evaluate",{expression:x,returnByValue:true})).result.value;
await send("Page.enable"); await send("Runtime.enable");
await send("Page.navigate",{url:"http://localhost:3000/"}); await sleep(2500);
await ev(`sessionStorage.setItem("vision.token",${JSON.stringify(jwt)})`);
await send("Page.reload"); await sleep(2500);
for (const h of ["#/data","#/data/annotation","#/records","#/system"]) {
  await send("Page.navigate",{url:"http://localhost:3000/"+h}); await sleep(1800);
  const title = await ev(`document.querySelector(".topbar > span").textContent.trim()`);
  const sub = await ev(`(document.querySelector("nav a.sub.selected")||{}).textContent?.trim() ?? "(无高亮子项)"`);
  const subs = await ev(`[...document.querySelectorAll("nav a.sub")].map(a=>a.textContent.trim()).join("/")`);
  const tab = await ev(`String(window.__vueRouteTab ?? "")`);
  const doc = await ev(`document.title`);
  console.log(`${h.padEnd(20)} 标签页=${JSON.stringify(doc)}  顶栏=${JSON.stringify(title)}  高亮子项=${JSON.stringify(sub)}  子项数=${subs ? subs.split("/").length : 0}`);
}
chrome.kill();
