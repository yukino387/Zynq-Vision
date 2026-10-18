import { spawn } from "node:child_process";
const ROOT="C:/00_workplace/fpga/cnn_accelerator", CHROME="C:/Program Files/Google/Chrome/Application/chrome.exe";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const chrome=spawn(CHROME,["--remote-debugging-port=9911","--headless=new","--disable-gpu","--no-first-run",`--user-data-dir=${ROOT}/temporary/ui_overhaul/profile-probe`,"--window-size=390,844","about:blank"],{stdio:"ignore"});
let wsUrl; for(let i=0;i<60;i++){try{const l=await (await fetch("http://127.0.0.1:9911/json/list")).json();const p=l.find(t=>t.type==="page");if(p?.webSocketDebuggerUrl){wsUrl=p.webSocketDebuggerUrl;break}}catch{}await sleep(250)}
const ws=new WebSocket(wsUrl); await new Promise(r=>ws.addEventListener("open",r));
let seq=0; const pend=new Map();
ws.addEventListener("message",e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){const{res,rej}=pend.get(m.id);pend.delete(m.id);m.error?rej(new Error(JSON.stringify(m.error))):res(m.result)}});
const send=(method,params={})=>{const id=++seq;ws.send(JSON.stringify({id,method,params}));return new Promise((res,rej)=>pend.set(id,{res,rej}))};
const ev=async x=>{const r=await send("Runtime.evaluate",{expression:x,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)return "抛出: "+r.exceptionDetails.text;return r.result?.value};
await send("Page.enable"); await send("Runtime.enable");
await send("Page.navigate",{url:"http://127.0.0.1:5174/mobile/"}); await sleep(4000);
console.log("origin:", await ev(`location.origin`));
console.log("fetch 同源 /api/health:", await ev(`fetch("/api/health").then(r=>r.status+" "+r.statusText).catch(e=>"fetch 失败: "+e.message)`));
console.log("fetch /mobile/api/health:", await ev(`fetch("/mobile/api/health").then(r=>r.status).catch(e=>"失败: "+e.message)`));
console.log("uni.request 存在:", await ev(`typeof uni!=="undefined" && typeof uni.request`));
console.log("uni.request 同源:", await ev(`new Promise(res=>{try{uni.request({url:location.origin+"/api/health",timeout:8000,success:r=>res("status "+r.statusCode),fail:e=>res("fail: "+JSON.stringify(e).slice(0,160))})}catch(e){res("throw: "+e.message)}})`));
chrome.kill();
