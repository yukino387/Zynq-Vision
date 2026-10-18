import {spawn} from 'node:child_process';
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {createRequire} from 'node:module';
const root=resolve(import.meta.dirname,'../..'),out=import.meta.dirname;
const require=createRequire(resolve(root,'apps/server/package.json')),WebSocket=require('ws');
const env=Object.fromEntries(readFileSync(resolve(root,'.env'),'utf8').split(/\r?\n/).filter(l=>l.includes('=')&&!l.startsWith('#')).map(l=>[l.slice(0,l.indexOf('=')),l.slice(l.indexOf('=')+1)]));
const api='http://127.0.0.1:3000/api',base='http://127.0.0.1:5174/mobile/';
const auth=await fetch(api+'/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'admin',password:env.SEED_PASSWORD})}).then(r=>r.json());
if(!auth.token)throw Error('Authentication failed');
const headers={authorization:'Bearer '+auth.token,'content-type':'application/json'};
const chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--remote-debugging-port=9237',`--user-data-dir=${resolve(out,'board-profile')}`,'--no-first-run','--no-default-browser-check','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let ws,seq=0;const calls=new Map(),cleanup=new Set(),report={flows:[]};
try{
 let tabs;for(let i=0;i<40;i++){try{tabs=await fetch('http://127.0.0.1:9237/json/list').then(r=>r.json());break;}catch{await sleep(200);}}
 ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.once('open',r);ws.once('error',j);});
 ws.on('message',raw=>{const m=JSON.parse(raw);if(calls.has(m.id)){const {r,j}=calls.get(m.id);calls.delete(m.id);m.error?j(Error(m.error.message)):r(m.result);}});
 const call=(method,params={})=>new Promise((r,j)=>{let id=++seq;calls.set(id,{r,j});ws.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description??'Runtime error');return r.result.value;};
 const waitFor=async(expression,label)=>{for(let i=0;i<120;i++){if(await evaluate(expression))return;await sleep(250);}throw Error(label);};
 const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
 const mode=async label=>{await evaluate(`[...document.querySelectorAll('.mode-switch uni-text')].find(e=>e.textContent.trim()===${JSON.stringify(label)}).click()`);await sleep(900);};
 await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:2,mobile:true});
 await call('Page.navigate',{url:base+'#/pages/login/index'});await waitFor(`!!document.querySelector('.login-page')`,'Login page missing');
 await evaluate(`uni.setStorageSync('vision.token',${JSON.stringify(auth.token)});uni.setStorageSync('vision.user',${JSON.stringify(auth.user)});uni.setStorageSync('vision.server',${JSON.stringify(base.replace('/mobile/',''))});uni.setStorageSync('vision.captureMode','BOARD');uni.setStorageSync('vision.task','');`);
 await call('Page.navigate',{url:base+'?board='+Date.now()+'#/pages/capture/index'});
 await waitFor(`!!document.querySelector('.capture-page')`,'Capture page missing');
 const client=await evaluate(`uni.getStorageSync('vision.client')`);
 const samples=async()=>{const r=await fetch(api+'/samples?pageSize=100',{headers}).then(r=>r.json());const items=r.items.filter(s=>s.clientId===client||s.clientId==='mobile-board-'+client);for(const s of items)cleanup.add(s.id);return items;};
 await mode('板端');await waitFor(`!document.querySelector('.shutter').disabled`,'Board frame not ready');
 await click('.shutter');await waitFor(`document.body.innerText.includes('板端采样已保存')`,'Board capture failed');
 const first=await samples();if(!first.some(s=>s.source==='BOARD'))throw Error('Board sample missing on server');
 const boardSample=first.find(s=>s.source==='BOARD');
 const detail=await fetch(api+'/samples/'+boardSample.id,{headers}).then(r=>r.json());
 if(!detail.inspections?.length)throw Error('Board inspection missing');
 report.flows.push('Live board frame → captured sample → inspection evidence');
 await click('.result-overlay');await waitFor(`!!document.querySelector('.review-options')`,'Inspection detail missing');
 await evaluate(`[...document.querySelectorAll('.review-options uni-text')].find(e=>e.textContent.trim()==='其他').click(); const e=document.querySelector('textarea');e.value='移动端流程验证，不代表人工合格判定';e.dispatchEvent(new Event('input',{bubbles:true}));`);
 await click('uni-button.primary');await waitFor(`!!document.querySelector('.success-note')`,'Inspection review failed');
 report.flows.push('Captured inspection → review OTHER → saved confirmation');
 await call('Page.navigate',{url:base+'?sync='+Date.now()+'#/pages/capture/index'});await waitFor(`!!document.querySelector('.capture-page')`,'Sync capture missing');
 await mode('同步');await waitFor(`!document.querySelector('.shutter').disabled && !!document.querySelector('video')`,'Sync inputs unavailable');
 await click('.shutter');await waitFor(`document.body.innerText.includes('板端采样已保存')`,'Synchronized capture failed');
 await waitFor(`(uni.getStorageSync('vision.queue')||[]).length>0&&(uni.getStorageSync('vision.queue')||[]).every(i=>i.status==='SYNCED')`,'Mobile half of sync did not upload');
 const paired=await samples(),mobile=paired.find(s=>s.source==='MOBILE'),board=paired.find(s=>s.source==='BOARD'&&s.captureSetId===mobile?.captureSetId);
 if(!mobile||!board||mobile.captureSetId!==board.captureSetId)throw Error('Sync pair not grouped');
 report.flows.push('SYNC capture → board + mobile original → shared capture group');
 report.samples=paired.map(s=>({id:s.id,source:s.source,captureSetId:s.captureSetId}));
 writeFileSync(resolve(out,'board-workflow.json'),JSON.stringify(report,null,2));console.log('PASS',report);
}finally{
 for(const id of cleanup){const r=await fetch(api+'/samples/'+id,{method:'DELETE',headers,body:JSON.stringify({confirm:true})});if(!r.ok)console.error('Cleanup failed',id);}
 ws?.close();chrome.kill();
}
