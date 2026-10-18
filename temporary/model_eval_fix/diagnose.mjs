import { createRequire } from 'node:module';
import { writeFileSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const require = createRequire(new URL('../../apps/server/package.json', import.meta.url));
require('dotenv').config({ path: new URL('../../.env', import.meta.url), quiet: true });
const { PrismaClient } = require('@prisma/client');
const db = new PrismaClient();
const base = 'http://127.0.0.1:3000/api';
const login = await fetch(`${base}/auth/login`, { method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({username:'admin',password:process.env.SEED_PASSWORD}) });
const session = await login.json();
if (!login.ok) throw new Error('Local diagnostic login failed');
const headers = {authorization:`Bearer ${session.token}`};
const devices = await (await fetch(`${base}/devices/snapshot`,{headers})).json();
const device = devices.find(d=>d.type==='ZYNQ');
const models = await (await fetch(`${base}/models?pageSize=100`,{headers})).json();
const commands = await db.command.findMany({where:{type:'BENCHMARK'}, orderBy:{createdAt:'desc'},take:3,select:{id:true,status:true,error:true,createdAt:true}});
const artifacts=await db.model.findMany({where:{source:'IMPORT'},include:{artifacts:{include:{asset:true}}}});
for (const m of artifacts) {
  const asset=m.artifacts.find(a=>a.kind==='WEIGHTS')?.asset;
  if (!asset || asset.size!==6416360) continue;
  const buf=readFileSync(resolve('apps/server',process.env.STORAGE_ROOT??'../../data/storage',asset.storageKey));
  console.log('artifact',m.version,'payload',buf.subarray(88,120).toString('hex'),'matches active',buf.subarray(88,120).toString('hex')===device.reportedState.modelPayloadSha256);
}
const summary = {device:{id:device.id,runtimeState:device.runtimeState,connectionState:device.connectionState,reportedState:device.reportedState},models:models.items.map(m=>({id:m.id,version:m.version,source:m.source,weights:m.manifest.weights})),commands};
writeFileSync(new URL('./baseline.json',import.meta.url),JSON.stringify(summary,null,2));
console.log(JSON.stringify(summary,null,2));
await db.$disconnect();
