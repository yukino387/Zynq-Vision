import { spawn } from "node:child_process";
import fs from "node:fs";
const ROOT="C:/00_workplace/fpga/cnn_accelerator", CHROME="C:/Program Files/Google/Chrome/Application/chrome.exe";
const env=Object.fromEntries(fs.readFileSync(`${ROOT}/.env`,"utf8").split(/\r?\n/).filter(l=>l.includes("=")&&!l.trimStart().startsWith("#")).map(l=>{const i=l.indexOf("=");return [l.slice(0,i).trim(),l.slice(i+1).trim()]}));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const jwt=(await (await fetch("http://localhost:3000/api/auth/login",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({username:"admin",password:env.SEED_PASSWORD})})).json()).token;
const chrome=spawn(CHROME,[`--remote-debugging-port=9777`,"--headless=new","--disable-gpu","--no-first-run",`--user-data-dir=${ROOT}/temporary/ui_overhaul/profile-nav`,"--window-size=1400,950","about:blank"],{stdio:"ignore"});
let wsUrl; for(let i=0;i<60;i++){try{const l=await (await fetch("http://127.0.0.1:9777/json/list")).json();const p=l.find(t=>t.type==="page");if(p?.webSocketDebuggerUrl){wsUrl=p.webSocketDebuggerUrl;break}}catch{}await sleep(250)}
const ws=new WebSocket(wsUrl); await new Promise(r=>ws.addEventListener("open",r));
let seq=0; const pend=new Map();
ws.addEventListener("message",e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){const{res,rej}=pend.get(m.id);pend.delete(m.id);m.error?rej(new Error(JSON.stringify(m.error))):res(m.result)}});
const send=(method,params={})=>{const id=++seq;ws.send(JSON.stringify({id,method,params}));return new Promise((res,rej)=>pend.set(id,{res,rej}))};
const ev=async x=>{const r=await send("Runtime.evaluate",{expression:x,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.text);return r.result.value};
await send("Page.enable"); await send("Runtime.enable");
await send("Page.navigate",{url:"http://localhost:3000/"}); await sleep(2500);
await ev(`sessionStorage.setItem("vision.token",${JSON.stringify(jwt)})`);
await send("Page.reload"); await sleep(2500);
console.log("初始侧栏项:", JSON.stringify(await ev(`[...document.querySelectorAll(".sidebar a,.sidebar button")].map(e=>e.textContent.trim()).filter(Boolean)`)));
// 展开"数据管理"
const clicked = await ev(`(()=>{const b=[...document.querySelectorAll(".sidebar button")].find(x=>x.textContent.includes("数据管理"));if(!b)return false;b.click();return true})()`);
await sleep(700);
console.log("点开数据管理:", clicked);
console.log("展开后:", JSON.stringify(await ev(`[...document.querySelectorAll(".sidebar a")].map(e=>e.textContent.trim()).filter(Boolean)`)));
// 搜索
await ev(`(()=>{const i=document.querySelector(".menu-search");i.value="标注";i.dispatchEvent(new Event("input",{bubbles:true}))})()`);
await sleep(700);
console.log("搜索「标注」:", JSON.stringify(await ev(`[...document.querySelectorAll(".sidebar a")].map(e=>e.textContent.trim()).filter(Boolean)`)));
chrome.kill();
