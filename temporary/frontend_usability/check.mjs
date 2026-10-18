import assert from 'node:assert/strict';
const base = 'http://127.0.0.1:3017/api';
const login = await fetch(`${base}/auth/login`, { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify({username:'qa-usability',password:'UI-Workflow-2026!'}) });
assert.equal(login.status, 201);
const { token } = await login.json();
async function get(path) {
  const response = await fetch(base + path, {headers:{authorization:`Bearer ${token}`}});
  assert.equal(response.status,200,path);
  return response.json();
}
const [all, real, pending, complete, simulated, overview, datasets] = await Promise.all([
  get('/samples?pageSize=100'),get('/samples?realOnly=true&pageSize=100'),
  get('/samples?realOnly=true&annotation=pending&pageSize=100'),
  get('/samples?realOnly=true&annotation=complete&pageSize=100'),
  get('/samples?source=SIMULATION&pageSize=100'),get('/overview'),get('/datasets?pageSize=100')
]);
assert.equal(real.total + simulated.total, all.total);
assert.equal(pending.total + complete.total, real.total);
assert(real.items.every(row=>row.source !== 'SIMULATION'));
assert(pending.items.every(row=>row._count.annotations===0));
assert(complete.items.every(row=>row._count.annotations>0));
assert.equal(overview.trainingReadiness.realSamples,real.total);
assert.equal(overview.trainingReadiness.annotatedReal,complete.total);
assert.equal(overview.trainingReadiness.simulatedSamples,simulated.total);
for (const dataset of datasets.items) assert.equal(Object.values(dataset.sourceCounts).reduce((a,b)=>a+b,0),dataset._count.items);
const created = datasets.items.find(row=>row.name==='界面验证 · 两张真实样本');
assert(created);
assert.equal(created.status,'FROZEN');
assert.equal(created._count.items,2);
assert.equal(created.sourceCounts.BOARD,2);
assert(overview.trainingReadiness.readyDatasets.some(row=>row.id===created.id));
console.log(JSON.stringify({ok:true,real:real.total,pending:pending.total,complete:complete.total,simulated:simulated.total,datasetWorkflow:'2 samples selected, frozen, available for training'},null,2));
