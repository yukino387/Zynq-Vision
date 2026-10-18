import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const require = createRequire(new URL('../../apps/server/package.json',import.meta.url));
require('dotenv').config({path:new URL('../../.env',import.meta.url),quiet:true});
const db = new (require('@prisma/client').PrismaClient)();
const base = 'http://127.0.0.1:3000/api';
const login = await fetch(`${base}/auth/login`, {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'admin',password:process.env.SEED_PASSWORD})});
assert.ok(login.ok,`Login: ${login.status}`);
const {token} = await login.json();
const headers = {authorization:`Bearer ${token}`,'content-type':'application/json'};
async function get(path) {
  const response = await fetch(`${base}${path}`, {headers});
  assert.ok(response.ok,`${path}: ${response.status}`);
  return response.json();
}
try {
  if (process.argv.includes('--before')) {
    const [commands,jobs] = await Promise.all([
      db.command.count({where:{status:{in:['QUEUED','RUNNING']}}}),
      db.job.count({where:{status:{in:['QUEUED','RUNNING']}}}),
    ]);
    assert.equal(commands+jobs,0,'Do not restart while tasks are running');
    const devices = await get('/devices/snapshot');
    const snapshot = {devices,benchmarks:await db.benchmark.count()};
    writeFileSync(new URL('./disable-before.json',import.meta.url),JSON.stringify(snapshot,null,2));
    console.log(JSON.stringify({commands,jobs,benchmarks:snapshot.benchmarks,devices:devices.map(d=>({id:d.id,connectionState:d.connectionState,runtimeState:d.runtimeState,version:d.reportedState.modelVersion}))}));
  } else {
    const before = JSON.parse(readFileSync(new URL('./disable-before.json',import.meta.url),'utf8'));
    for (const method of ['GET','POST']) {
      const response = await fetch(`${base}/benchmarks`,{method,headers,...(method==='POST'?{body:JSON.stringify({})}:{})});
      assert.equal(response.status,404,`${method} benchmarks must be disabled`);
    }
    assert.equal(await db.benchmark.count(),before.benchmarks,'Keep existing history');
    for (const device of before.devices.filter(d=>d.type==='ZYNQ'&&d.connectionState==='ONLINE')) {
      const connected = await fetch(`${base}/devices/${device.id}/connect`,{method:'POST',headers,body:'{}'});
      assert.ok(connected.ok,`Reconnect: ${connected.status} ${await connected.text()}`);
    }
    const after = await get('/devices/snapshot');
    for (const device of before.devices.filter(d=>d.type==='ZYNQ'&&d.connectionState==='ONLINE')) {
      const current = after.find(d=>d.id===device.id);
      assert.equal(current.connectionState,'ONLINE');
      assert.equal(current.reportedState.modelVersion,device.reportedState.modelVersion);
      assert.equal(current.reportedState.modelPayloadSha256,device.reportedState.modelPayloadSha256);
      assert.equal(current.reportedState.cameraOnly,device.reportedState.cameraOnly);
      assert.equal(current.runtimeState,device.runtimeState);
    }
    const result = {disabled:true,benchmarks:before.benchmarks,devices:after.map(d=>({id:d.id,connectionState:d.connectionState,runtimeState:d.runtimeState,version:d.reportedState.modelVersion}))};
    writeFileSync(new URL('./disable-after.json',import.meta.url),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }
} finally {await db.$disconnect();}
