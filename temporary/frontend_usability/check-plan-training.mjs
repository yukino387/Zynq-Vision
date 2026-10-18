import assert from 'node:assert/strict';
import {writeFileSync} from 'node:fs';
const base='http://127.0.0.1:3017/api';
const login=await fetch(base+'/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'qa-usability',password:'UI-Workflow-2026!'})});
const {token}=await login.json();
async function call(path,body){const response=await fetch(base+path,{method:body?'POST':'GET',headers:{authorization:`Bearer ${token}`,...(body?{'content-type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});const value=await response.json();assert(response.ok,JSON.stringify(value));return value;}
const task=(await call('/tasks?pageSize=100')).items.find(row=>row.name==='饮品包装采样（界面验证）');assert(task?.plan);
const device=(await call('/devices?pageSize=100')).items.find(row=>row.type==='SIMULATOR');assert(device);
const ids=[];
for(let n=0;n<2;n++){
 const sample=await call('/samples/capture',{deviceId:device.id,taskId:task.id,idempotencyKey:crypto.randomUUID(),clientId:crypto.randomUUID(),localSequence:n});
 await call(`/samples/${sample.id}/annotations`,{status:'COMPLETE',boxes:[{classId:0,label:'盒体',confidence:1,x1:50,y1:50,x2:250,y2:300}]});
 await call(`/samples/${sample.id}/review`,{verdict:'ACCEPT',note:'隔离副本流程验证，不代表真实模型效果'});ids.push(sample.id);
}
const dataset=await call('/datasets',{name:'方案类别导出验证（隔离）',version:1});
await call(`/datasets/${dataset.id}/items`,{sampleIds:ids});await call(`/datasets/${dataset.id}/freeze`,{});
const train=await call('/trainings',{datasetId:dataset.id,name:'方案类别 GPU 流程检查',options:{epochs:1,batchSize:2,workers:0,device:'cuda',colorMode:'GRAY',amp:true}});
const deadline=Date.now()+90000;let result;
while(Date.now()<deadline){result=(await call('/trainings?pageSize=100')).items.find(row=>row.id===train.id);if(['COMPLETED','FAILED','CANCELLED'].includes(result.status))break;await new Promise(resolve=>setTimeout(resolve,1000));}
assert.equal(result.status,'COMPLETED',result.error);
const model=await call(`/models/${result.models[0].id}`);
assert.deepEqual(model.manifest.classes,['盒体','标签','_unused_2','_unused_3','_unused_4','_unused_5']);assert.equal(model.manifest.weights.size,6416360);
const report={ok:true,modelId:model.id,classes:model.manifest.classes,weightsBytes:model.manifest.weights.size,status:model.status,epochs:1,device:'cuda',note:'Isolated simulated inputs; workflow validation only, not model accuracy'};
writeFileSync('temporary/frontend_usability/plan-training-result.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
