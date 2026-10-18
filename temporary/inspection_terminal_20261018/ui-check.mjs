import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import WebSocket from '../../apps/server/node_modules/ws/index.js';
const out=resolve('temporary/inspection_terminal_20261018'),profile=resolve(out,`ui-profile-${Date.now()}`);
mkdirSync(profile,{recursive:true});
const chrome=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--remote-debugging-port=0',`--user-data-dir=${profile}`,'--no-first-run','--no-default-browser-check','about:blank'],{stdio:'ignore'});
const delay=ms=>new Promise(done=>setTimeout(done,ms));
let socket,sequence=0;const waiting=new Map(),errors=[];
async function send(method,params={}) {const id=++sequence;return new Promise((done,fail)=>{waiting.set(id,{done,fail});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression) {const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;}
async function until(expression){for(let i=0;i<60;i++){if(await evaluate(expression))return;await delay(150);}throw Error(`UI condition failed: ${expression}\n${await evaluate('document.body.innerText')}`);}
const click=text=>evaluate(`(()=>{const button=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)});if(!button||button.disabled)throw Error('Button unavailable');button.click();return true;})()`);
const set=(label,value)=>evaluate(`(()=>{const field=[...document.querySelectorAll('label')].find(l=>l.textContent.includes(${JSON.stringify(label)}));const input=field?.querySelector('input,select,textarea');if(!input)throw Error('Field unavailable');input.value=${JSON.stringify(value)};input.dispatchEvent(new Event(input.tagName==='SELECT'?'change':'input',{bubbles:true}));return true;})()`);
try {
  for(let i=0;i<100&&!existsSync(resolve(profile,'DevToolsActivePort'));i++)await delay(100);
  const port=readFileSync(resolve(profile,'DevToolsActivePort'),'utf8').split('\n')[0];
  const tab=await fetch(`http://127.0.0.1:${port}/json/new?http://127.0.0.1:38881/`,{method:'PUT'}).then(r=>r.json());
  socket=new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((done,fail)=>{socket.once('open',done);socket.once('error',fail);});
  socket.on('message',raw=>{const message=JSON.parse(String(raw));if(message.id){const request=waiting.get(message.id);if(request){waiting.delete(message.id);message.error?request.fail(Error(JSON.stringify(message.error))):request.done(message.result);}}else if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails);});
  await send('Page.enable');await send('Runtime.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await evaluate(`(async()=>{const response=await fetch('/api/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'ADMIN',password:'test-password-2026'})});if(!response.ok)throw Error('Isolated login failed');const login=await response.json();sessionStorage.setItem('vision.token',login.token);sessionStorage.setItem('vision.user',JSON.stringify(login.user));const headers={authorization:'Bearer '+login.token,'content-type':'application/json'};const batches=await fetch('/api/batches?status=OPEN',{headers}).then(r=>r.json());for(const batch of batches.items)await fetch('/api/batches/'+batch.id+'/close',{method:'POST',headers,body:JSON.stringify({confirm:true})});return true;})()`);
  await send('Page.navigate',{url:'http://127.0.0.1:38881/#/production'});
  await send('Page.reload',{ignoreCache:true});
  await until(`document.querySelector('h1')?.textContent.includes('检测作业') && [...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='新建批次'&&!b.disabled)`);
  await click('新建批次');await set('批次名称','TEST UI 包装检查');
  const task=await evaluate(`([...document.querySelectorAll('label')].find(l=>l.textContent.includes('使用任务')).querySelector('select').options[1]).value`);
  await set('使用任务',task);await click('建立批次');
  await until(`document.body.innerText.includes('批次已建立')`);
  await until(`[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='检查一件 · F5'&&!b.disabled)`);
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'F5',code:'F5',windowsVirtualKeyCode:116});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'F5',code:'F5',windowsVirtualKeyCode:116});
  await until(`document.body.innerText.includes('本件检查与证据已保存') && document.querySelector('.production-stats')?.textContent.includes('1 / 100')`);
  let screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});writeFileSync(resolve(out,'production-desktop.png'),Buffer.from(screenshot.data,'base64'));
  await click('查看本件证据与复核');await until(`!!document.querySelector('[role=dialog]') && document.body.innerText.includes('最终处理结论')`);
  await set('审核结论','CORRECT');await set('最终处理结论','FAIL');await set('备注','TEST 人工复核更正，保留机器原判');await click('提交复核意见');
  await until(`document.querySelector('.production-stats strong:last-of-type') && [...document.querySelectorAll('.production-stats strong')].at(-1).textContent.trim()==='0.0%'`);
  assert.equal(await evaluate(`document.querySelectorAll('.production-stats strong')[2].textContent`),'1');
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});await delay(300);
  const layout=await evaluate(`({width:innerWidth,scroll:document.documentElement.scrollWidth})`);assert.ok(layout.scroll<=layout.width,JSON.stringify(layout));
  screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});writeFileSync(resolve(out,'production-mobile.png'),Buffer.from(screenshot.data,'base64'));
  assert.deepEqual(errors,[]);
  writeFileSync(resolve(out,'ui-results.json'),JSON.stringify({fixture:true,createdBatch:true,keyboardCheck:true,reviewPreservesMachineResult:true,responsive:true,browserErrors:errors.length},null,2));
  console.log('UI passed: batch create, F5 inspection, review, statistics, responsive layout and no browser exceptions');
}finally{socket?.close();chrome.kill();}
