import '../../apps/server/src/config.js';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
async function main(){
 const login=await fetch('http://localhost:3000/api/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'admin',password:process.env.SEED_PASSWORD})});assert.ok(login.ok);const {token}=await login.json() as {token:string};
 async function request(path:string,body?:unknown){const multi=body instanceof FormData;return fetch('http://localhost:3000/api'+path,{method:body===undefined?'GET':'POST',headers:{authorization:`Bearer ${token}`,...(multi?{}:{'content-type':'application/json'})},body:body===undefined?undefined:multi?body:JSON.stringify(body)});}
 const before=(await (await request('/devices/snapshot')).json()).find((d:any)=>d.type==='ZYNQ');
 const bytes=await readFile('temporary/online_weight_trial/neu_det_yolov8n_best.onnx');const sha256=createHash('sha256').update(bytes).digest('hex');
 const name='公开 NEU-DET YOLOv8n（7020 不兼容）',version='github-v1.0.0';
 let model=(await (await request('/models?pageSize=100')).json()).items.find((m:any)=>m.name===name&&m.version===version);
 if(!model){const manifest={formatVersion:1,networkTemplate:'YOLOV8N_NEU_DET',firmwareInterfaceVersion:'ONNX',preprocessProfile:'RGB640_FLOAT32',input:{width:640,height:640,channels:3,dtype:'FLOAT32'},output:[[1,10,8400]],classCount:6,classes:['龟裂','夹杂','斑块','麻点','轧入氧化皮','划痕'],quantization:{scheme:'FLOAT32',inputScale:1/255,inputZeroPoint:0,outputScales:[1]},weights:{size:bytes.length,sha256}};const form=new FormData();form.set('metadata',JSON.stringify({name,version,manifest}));form.set('file',new Blob([bytes]),'neu_det_yolov8n_best.onnx');const imported=await request('/models/import',form);assert.ok(imported.ok,await imported.clone().text());model=await imported.json();}
 const check=await request(`/models/${model.id}/compatibility`,{deviceId:before.id});const result=await check.json();assert.equal(check.status,422);assert.equal(result.code,'MODEL_INCOMPATIBLE');
 const after=(await (await request('/devices/snapshot')).json()).find((d:any)=>d.id===before.id);assert.equal(after.reportedState.modelVersion,before.reportedState.modelVersion);assert.equal(after.reportedState.modelPayloadSha256,before.reportedState.modelPayloadSha256);
 const evidence={source:'https://github.com/winthegame259/steel-surface-defect-detection/releases/tag/v1.0.0',modelId:model.id,sha256,bytes:bytes.length,result,activeVersionUnchanged:after.reportedState.modelVersion};await writeFile('temporary/online_weight_trial/public-compatibility.json',JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
