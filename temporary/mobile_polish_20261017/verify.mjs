import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
const root=resolve(import.meta.dirname,'../..');
const out=import.meta.dirname;
const require=createRequire(resolve(root,'apps/server/package.json'));
const WebSocket=require('ws');
const env=Object.fromEntries(readFileSync(resolve(root,'.env'),'utf8').split(/\r?\n/).filter(s=>s.includes('=')&&!s.startsWith('#')).map(s=>[s.slice(0,s.indexOf('=')),s.slice(s.indexOf('=')+1)]));
const base='http://127.0.0.1:5174/mobile/';
const api='http://127.0.0.1:3000/api';
const login=await fetch(api+'/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'admin',password:env.SEED_PASSWORD})}).then(r=>r.json());
if(!login.token)throw Error('Login unavailable');
const headers={authorization:'Bearer '+login.token};
const inspections=await fetch(api+'/inspections?pageSize=2',{headers}).then(r=>r.json());
const samples=await fetch(api+'/samples?pageSize=2',{headers}).then(r=>r.json());
const chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--remote-debugging-port=9236',`--user-data-dir=${resolve(out,'profile')}`,'--no-first-run','--no-default-browser-check','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--autoplay-policy=no-user-gesture-required','about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let ws,seq=0;
const waiting=new Map();
try{
 let targets;
 for(let i=0;i<40;i++){try{targets=await fetch('http://127.0.0.1:9236/json/list').then(r=>r.json());break;}catch{await sleep(250);}}
 ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.once('open',r);ws.once('error',j);});
 const faults=[];
 ws.on('message',raw=>{const m=JSON.parse(raw);if(m.method==='Runtime.exceptionThrown')faults.push(m.params.exceptionDetails.text+': '+(m.params.exceptionDetails.exception?.description??''));if(waiting.has(m.id)){let {r,j}=waiting.get(m.id);waiting.delete(m.id);m.error?j(Error(m.error.message)):r(m.result);}});
 const call=(method,params={})=>new Promise((r,j)=>{const id=++seq;waiting.set(id,{r,j});ws.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description??r.exceptionDetails.text);return r.result.value;};
 const click=async selector=>{if(!await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;e.click();return true;})()`))throw Error('Missing control '+selector);await sleep(650);};
 const fill=(selector,value)=>evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('Missing input');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
 await call('Page.enable');await call('Runtime.enable');
 await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:2,mobile:true});
 await call('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:5});
 const report={pages:[],flows:[],faults};
 const shot=async name=>{const image=await call('Page.captureScreenshot',{format:'png'});writeFileSync(resolve(out,name+'.png'),Buffer.from(image.data,'base64'));};
 const visit=async(name,route)=>{
  const target=base+'?verify='+Date.now()+'#/'+route;
  await call('Page.navigate',{url:target});
  let ready=false;
  for(let attempt=0;attempt<80;attempt++){await sleep(200);if(await evaluate(`location.href===${JSON.stringify(target)} && document.readyState==='complete' && document.body.innerText.trim().length>0`)){ready=true;break;}if(faults.length)throw Error(faults.join('\n'));}
  if(!ready)throw Error('Page did not become ready: '+name);
  await sleep(1000);
  const result=await evaluate(`({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,text:document.body.innerText.slice(0,180)})`);
  report.pages.push({name,...result});await shot(name);console.log(name,JSON.stringify(result));
 };
 await visit('login','pages/login/index');
 await fill('uni-input[aria-label="服务器地址"] input',base.replace('/mobile/',''));
 await fill('uni-input[aria-label="账号"] input','admin');await fill('uni-input[aria-label="密码"] input',env.SEED_PASSWORD);
 await click('.submit');await sleep(1400);
 if(!await evaluate(`!!document.querySelector('.welcome')`)){await shot('login-error');throw Error('Login did not reach home');}
 report.flows.push('Login via form → home');
 await visit('home','pages/home/index');
 await visit('tasks','pages/tasks/index');
 await click('.independent');
 if(!await evaluate(`!!document.querySelector('.capture-page')`))throw Error('Task to capture failed');
 report.flows.push('Independent task → capture');
 await visit('capture-board','pages/capture/index');
 await evaluate(`[...document.querySelectorAll('.mode-switch uni-text')].find(e=>e.textContent.trim()==='手机').click()`);await sleep(1500);await shot('capture-mobile');
 await click('.shutter');
 for(let attempt=0;attempt<60;attempt++){await sleep(300);if(await evaluate(`document.body.innerText.includes('手机原图已保存') || !!document.querySelector('.result-overlay.error')`))break;}
 await shot('capture-saved');
 if(!await evaluate(`document.body.innerText.includes('手机原图已保存')`))throw Error('Mobile capture did not persist');
 report.flows.push('Browser camera → local queue');
 await click('.task-btn');await shot('capture-settings');
 await visit('sync','pages/sync/index');
 for(let attempt=0;attempt<100;attempt++){if(await evaluate(`(uni.getStorageSync('vision.queue')||[]).every(i=>i.status==='SYNCED')`))break;await sleep(300);}
 if(!await evaluate(`(uni.getStorageSync('vision.queue')||[]).every(i=>i.status==='SYNCED')`))throw Error('Upload queue not acknowledged');
 report.flows.push('Upload acknowledged by server');
 report.queue=await evaluate(`document.body.innerText`);
 await visit('records','pages/records/index');
 await evaluate(`[...document.querySelectorAll('.filter')].find(e=>e.textContent.trim()==='待复核').click()`);await sleep(1000);await shot('records-review');
 report.flows.push('Records → pending review filter');
 await visit('pair','pages/pair/index');
 await visit('live','pages/live/index');await click('.immersive-toggle');await shot('live-immersive');
 if(inspections.items?.[0])await visit('detail','pages/detail/index?id='+inspections.items[0].id);
 if(samples.items?.[0])await visit('sample','pages/sample/index?id='+samples.items[0].id);
 await call('Emulation.setDeviceMetricsOverride',{width:360,height:740,deviceScaleFactor:2,mobile:true});
 for(const [name,route]of[['login','login'],['home','home'],['tasks','tasks'],['records','records'],['pair','pair'],['sync','sync'],['capture','capture']])await visit(name+'-360','pages/'+route+'/index');
 if(process.env.FLOWS){
  const waitFor=async(expression,label)=>{for(let attempt=0;attempt<100;attempt++){if(await evaluate(expression))return;await sleep(250);}throw Error(label);};
  await visit('offline-capture-start','pages/capture/index');
  await call('Network.enable');
  await call('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
  await sleep(500);
  await click('.shutter');
  await waitFor(`document.body.innerText.includes('手机原图已保存')`,'Offline original not persisted');
  await shot('offline-capture-saved');
  const offlineItems=await evaluate(`(uni.getStorageSync('vision.queue')||[]).map(i=>({id:i.id,status:i.status,sequence:i.localSequence}))`);
  if(!offlineItems.some(i=>i.status==='QUEUED'||i.status==='FAILED'))throw Error('Offline sample was not queued');
  report.flows.push('Offline capture persists original without server');
  await call('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await waitFor(`(uni.getStorageSync('vision.queue')||[]).every(i=>i.status==='SYNCED')`,'Reconnect upload failed');
  const uploaded=await evaluate(`(uni.getStorageSync('vision.queue')||[]).map(i=>({id:i.id,serverId:i.serverId,sequence:i.localSequence}))`);
  report.flows.push('Network restored → queued sample automatically uploads');
  const mobileId=uploaded.at(-1).serverId;
  await visit('sample-review-test','pages/sample/index?id='+mobileId);
  await evaluate(`[...document.querySelectorAll('.review-options uni-text')].find(e=>e.textContent.trim()==='待补充').click()`);
  await fill('textarea','移动端流程验证图，请勿用于训练。');
  await click('button.primary, uni-button.primary');
  await waitFor(`!!document.querySelector('.success-note')`,'Sample review not saved');
  report.flows.push('Uploaded sample → review → saved confirmation');
  await visit('pair-workflow','pages/pair/index');
  const pairing=await fetch(api+'/system/pairing',{method:'POST',headers:{...headers,'content-type':'application/json'},body:JSON.stringify({serverUrl:base.replace('/mobile/','')})}).then(r=>r.json());
  await fill('textarea',JSON.stringify(pairing));await click('.verify');
  await waitFor(`document.body.innerText.includes('配对成功')`,'Pair redeem failed');
  report.flows.push('Valid pairing payload → server redemption → success');
  const operator=await fetch(api+'/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'operator',password:env.SEED_PASSWORD})}).then(r=>r.json());
  if(!operator.token)throw Error('Operator login failed');
  await evaluate(`uni.setStorageSync('vision.token',${JSON.stringify(operator.token)});uni.setStorageSync('vision.user',${JSON.stringify(operator.user)});`);
  await visit('operator-sample','pages/sample/index?id='+mobileId);
  if(await evaluate(`!!document.querySelector('.review-options')`))throw Error('Operator has admin review controls');
  report.flows.push('Operator sample detail exposes view-only controls');
  report.verifiedSampleIds=uploaded.map(i=>i.serverId);
  // Remove only samples generated by this browser profile's camera checks.
  for(const id of report.verifiedSampleIds){const r=await fetch(api+'/samples/'+id,{method:'DELETE',headers:{...headers,'content-type':'application/json'},body:JSON.stringify({confirm:true})});if(!r.ok)throw Error('Test sample cleanup failed');}
 }
 writeFileSync(resolve(out,'verification.json'),JSON.stringify(report,null,2));
 if(faults.length)throw Error('Browser runtime faults: '+faults.join('\n'));
 if(report.pages.some(p=>p.overflow))throw Error('Horizontal overflow detected');
 console.log('PASS',report.flows);
}finally{ws?.close();chrome.kill();}
