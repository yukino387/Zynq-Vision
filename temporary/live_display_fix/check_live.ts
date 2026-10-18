import '../../apps/server/src/config.js';
import WebSocket from '../../apps/server/node_modules/ws/index.js';
async function main(){
const response = await fetch('http://localhost:3000/api/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'admin',password:process.env.SEED_PASSWORD})});
if(!response.ok) throw new Error(`Login failed ${response.status}`);
const {token}=await response.json() as {token:string};
const headers={'authorization':`Bearer ${token}`,'content-type':'application/json'};
async function call(path:string,body?:unknown){const r=await fetch('http://localhost:3000/api'+path,{headers,method:body===undefined?'GET':'POST',body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw new Error(JSON.stringify({path,status:r.status,data}));return data;}
const snapshots=await call('/devices/snapshot');const device=snapshots.find((d:any)=>d.type==='ZYNQ');if(!device)throw new Error('No ZYNQ registered');
console.log('BEFORE',JSON.stringify({id:device.id,connection:device.connectionState,runtime:device.runtimeState,error:device.error,model:device.reportedState.modelVersion}));
let previews=0,telemetry=0,first:number|null=null,last:number|null=null;
const ws=new WebSocket('ws://localhost:3000/ws');
await new Promise<void>((resolve,reject)=>{ws.on('open',()=>ws.send(JSON.stringify({token})));ws.on('error',reject);ws.on('message',raw=>{const e=JSON.parse(raw.toString());if(e.type==='session.ready')resolve();if(e.entityId!==device.id)return;if(e.type==='device.preview.frame'){previews++;first??=e.payload.frameId;last=e.payload.frameId;}if(e.type==='device.telemetry')telemetry++;});});
try{console.log('CONNECT',JSON.stringify(await call(`/devices/${device.id}/connect`,{})));await new Promise(resolve=>setTimeout(resolve,8000));const state=(await call('/devices/snapshot')).find((d:any)=>d.id===device.id);console.log('STREAM',JSON.stringify({previews,telemetry,first,last,connection:state.connectionState,runtime:state.runtimeState,error:state.error,model:state.reportedState.modelVersion,capabilities:state.capabilities}));if(!previews)process.exitCode=1;}finally{ws.close();}

}
main().catch(error=>{console.error(error);process.exitCode=1;});
