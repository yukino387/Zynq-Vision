import { createRequire } from 'node:module';
import { readFileSync,writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const require=createRequire(new URL('../../apps/server/package.json',import.meta.url));
require('dotenv').config({path:new URL('../../.env',import.meta.url),quiet:true});
const base='http://127.0.0.1:3000/api';
const login=await fetch(`${base}/auth/login`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'admin',password:process.env.SEED_PASSWORD})});
const session=await login.json();
if(!login.ok)throw new Error('Local login failed');
const headers={authorization:`Bearer ${session.token}`};
const devices=await(await fetch(`${base}/devices/snapshot`,{headers})).json();
const device=devices.find(d=>d.type==='ZYNQ');
const models=await(await fetch(`${base}/models?pageSize=100`,{headers})).json();
const content=readFileSync(new URL('../milk_model_import/board_model_20261017/model.bin',import.meta.url));
if(content.subarray(88,120).toString('hex')!==device.reportedState.modelPayloadSha256)throw new Error('Recovery artifact does not match active payload');
const checksum=createHash('sha256').update(content).digest('hex');
let recovery=models.items.find(m=>m.manifest.weights.sha256===checksum);
if(!recovery){
 const data=new FormData();
 data.append('name','板端当前模型（评估恢复用）');
 data.append('classes',JSON.stringify(models.items.find(m=>m.version===device.reportedState.modelVersion).manifest.classes));
 data.append('file',new Blob([content]),'model.bin');
 const response=await fetch(`${base}/models/import`,{method:'POST',headers,body:data});
 recovery=await response.json();
 console.log('register recovery',response.status,JSON.stringify({id:recovery.id,...(!response.ok?recovery:{})}));
 if(!response.ok)process.exit(1);
}
writeFileSync(new URL('./registered-recovery.json',import.meta.url),JSON.stringify({id:recovery.id,version:recovery.version,sha256:checksum,payload:content.subarray(88,120).toString('hex')},null,2));
console.log('exact active recovery artifact ready',recovery.id);
