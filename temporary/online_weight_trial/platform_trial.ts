import '../../apps/server/src/config.js';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import WebSocket from '../../apps/server/node_modules/ws/index.js';
async function main(){
 const login=await fetch('http://localhost:3000/api/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'admin',password:process.env.SEED_PASSWORD})});if(!login.ok)throw new Error(`Login ${login.status}`);const {token}=await login.json() as {token:string};
 const evidence:any={purpose:'Online transfer/activation/rollback; identical trained payload, version header changed',startedAt:new Date().toISOString(),phases:[]};
 const log=(phase:string,data:any)=>{evidence.phases.push({phase,at:new Date().toISOString(),...data});console.log(phase,JSON.stringify(data));};
 async function api(path:string,body?:unknown){const multipart=body instanceof FormData;const r=await fetch('http://localhost:3000/api'+path,{method:body===undefined?'GET':'POST',headers:{authorization:`Bearer ${token}`,...(multipart?{}:{'content-type':'application/json'})},body:body===undefined?undefined:multipart?body:JSON.stringify(body)});const value=await r.json();if(!r.ok)throw new Error(JSON.stringify({path,status:r.status,value}));return value;}
 let d=(await api('/devices/snapshot')).find((d:any)=>d.type==='ZYNQ');assert.ok(d,'Zynq device required');if(d.connectionState!=='ONLINE'||!d.capabilities.modelUpdate){await api(`/devices/${d.id}/connect`,{});d=(await api('/devices/snapshot')).find((v:any)=>v.id===d.id);}
 const baselineBytes=await readFile('camera/build/models/factory/model.bin');const baselineVersion=baselineBytes.subarray(24,88).toString('ascii').split('\0')[0];const baselineDigest=baselineBytes.subarray(88,120).toString('hex');assert.equal(d.reportedState.modelVersion,baselineVersion);assert.equal(d.reportedState.modelPayloadSha256,baselineDigest);
 log('INITIAL',{deviceId:d.id,version:baselineVersion,payloadSha256:baselineDigest,runtime:d.runtimeState});
 async function register(name:string,folder:string){const bytes=await readFile(folder+'/model.bin');const manifest=JSON.parse(await readFile(folder+'/manifest.json','utf8'));const version=bytes.subarray(24,88).toString('ascii').split('\0')[0];const rows=await api('/models?pageSize=100');const existing=rows.items.find((m:any)=>m.source==='IMPORT'&&m.version===version&&m.manifest.weights.sha256===manifest.weights.sha256);if(existing)return existing;const form=new FormData();form.set('metadata',JSON.stringify({name,version,manifest}));form.set('file',new Blob([bytes]),'model.bin');return api('/models/import',form);}
 const baseline=await register('Zynq 正式 INT8 权重','camera/build/models/factory');const candidate=await register('在线更新链路测试（同权重）','temporary/online_weight_trial/compatible-test');
 log('REGISTERED',{baseline:baseline.id,candidate:candidate.id,candidateVersion:candidate.version,samePayload:true});console.log('QUANTIZATION',JSON.stringify(candidate.manifest.quantization));await api(`/models/${candidate.id}/compatibility`,{deviceId:d.id});
 const frozen=(await api('/datasets?status=FROZEN&pageSize=100')).items[0];assert.ok(frozen,'Frozen snapshot required for hardware inference check');
 const ws=new WebSocket('ws://localhost:3000/ws');let frames=0,lastFrame:any=null,stages:string[]=[];
 await new Promise<void>((resolve,reject)=>{ws.on('open',()=>ws.send(JSON.stringify({token})));ws.on('error',reject);ws.on('message',raw=>{const e=JSON.parse(raw.toString());if(e.type==='session.ready')resolve();if(e.type==='device.preview.frame'&&e.entityId===d.id){frames++;lastFrame={id:e.payload.frameId,receivedAt:e.payload.receivedAt,jpegBytes:e.payload.jpeg.length};}if(e.type==='deployment.progress'){stages.push(e.payload.status);console.log('PROGRESS',e.payload.status);}});});
 let deployment:any=null;
 try{
  console.log('HARDWARE_CHECK_RUNNING');const benchmark=await api('/benchmarks',{name:'在线更新链路自检（同权重，不评估精度）',modelId:candidate.id,datasetId:frozen.id,deviceId:d.id});assert.equal(benchmark.source,'BOARD');assert.equal(benchmark.metrics.candidateExecuted,true);assert.equal(benchmark.metrics.restoredModelVersion,baselineVersion);log('HARDWARE_CHECK',{id:benchmark.id,metrics:benchmark.metrics});
  deployment=await api('/deployments',{modelId:candidate.id,deviceId:d.id});log('DEPLOYMENT_CREATED',{id:deployment.id,previousVersion:deployment.previousVersion});let latest=deployment;const until=Date.now()+120000;
  while(Date.now()<until){latest=(await api('/deployments?pageSize=100')).items.find((r:any)=>r.id===deployment.id);if(['ACTIVE','FAILED'].includes(latest.status))break;await new Promise(r=>setTimeout(r,1000));}
  assert.equal(latest.status,'ACTIVE',JSON.stringify(latest));assert.equal(latest.receipt.simulated,false);for(const k of ['downloaded','verified','loaded','selfTest','active'])assert.equal(latest.receipt[k],true,k);
  const active=(await api('/devices/snapshot')).find((v:any)=>v.id===d.id);assert.equal(active.reportedState.modelVersion,candidate.version);assert.equal(active.reportedState.modelPayloadSha256,baselineDigest);const beforeFrames=frames;await new Promise(r=>setTimeout(r,5000));assert.ok(frames>beforeFrames,'Post-activation frames required');log('ACTIVE',{version:active.reportedState.modelVersion,receipt:latest.receipt,stages,previewFramesAfterActivation:frames-beforeFrames,lastFrame});
 }finally{
  try{if(deployment){const latest=(await api('/deployments?pageSize=100')).items.find((r:any)=>r.id===deployment.id);if(['ACTIVE','FAILED'].includes(latest.status)){const restored=await api(`/deployments/${deployment.id}/rollback`,{});assert.equal(restored.status,'ROLLED_BACK');assert.equal(restored.receipt.rollback.selfTest,true);log('ROLLBACK',{id:restored.id,status:restored.status,receipt:restored.receipt});}}
   const final=(await api('/devices/snapshot')).find((v:any)=>v.id===d.id);assert.equal(final.reportedState.modelVersion,baselineVersion);assert.equal(final.reportedState.modelPayloadSha256,baselineDigest);const n=frames;await new Promise(r=>setTimeout(r,5000));assert.ok(frames>n);log('FINAL',{version:final.reportedState.modelVersion,payloadSha256:final.reportedState.modelPayloadSha256,runtime:final.runtimeState,error:final.error,previewFramesAfterRollback:frames-n});
  }finally{ws.close();evidence.finishedAt=new Date().toISOString();await writeFile('temporary/online_weight_trial/platform-result.json',JSON.stringify(evidence,null,2));}
 }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
