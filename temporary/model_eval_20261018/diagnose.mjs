import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const require = createRequire(new URL('../../apps/server/package.json', import.meta.url));
require('dotenv').config({path: new URL('../../.env', import.meta.url), quiet: true});
const base = 'http://127.0.0.1:3000/api';
const response = await fetch(`${base}/auth/login`, {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({username: 'admin', password: process.env.SEED_PASSWORD})});
if (!response.ok) throw new Error(`Login failed: ${response.status}`);
const {token} = await response.json();
const headers = {authorization: `Bearer ${token}`};
async function get(path) {
  const r = await fetch(`${base}${path}`, {headers});
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}
const [devices, models, datasets] = await Promise.all([get('/devices/snapshot'), get('/models?pageSize=100&realOnly=true'), get('/datasets?pageSize=100&realOnly=true&status=FROZEN')]);
const db = new (require('@prisma/client').PrismaClient)();
try {
  const artifacts = await db.model.findMany({where: {source: 'IMPORT'}, include: {artifacts: {include: {asset: true}}}});
  const device = devices.find(d => d.type === 'ZYNQ');
  const summary = {
    device,
    models: artifacts.map(m => {
      const asset = m.artifacts.find(a => a.kind === 'WEIGHTS')?.asset;
      let payload, version, error;
      try {
        const weights = readFileSync(resolve('apps/server', process.env.STORAGE_ROOT ?? '../../data/storage', asset.storageKey));
        payload = weights.subarray(88,120).toString('hex');
        version = weights.subarray(24,88).toString('ascii').split('\0')[0];
      } catch(e) {error=String(e);}
      return {id:m.id,name:m.name,version:m.version,packageVersion:version,payload,activeMatch:m.version===device?.reportedState.modelVersion && payload===device?.reportedState.modelPayloadSha256,classes:m.manifest.classes,error};
    }),
    datasets: datasets.items.map(d => ({id:d.id,name:d.name,version:d.version,status:d.status,count:d._count})),
  };
  writeFileSync(new URL('./diagnosis.json',import.meta.url),JSON.stringify(summary,null,2));
  console.log(JSON.stringify(summary,null,2));
} finally {await db.$disconnect();}
