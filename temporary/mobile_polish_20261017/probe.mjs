import {readFileSync} from 'node:fs';
const env=Object.fromEntries(readFileSync('.env','utf8').split(/\r?\n/).filter(s=>s.includes('=')&&!s.startsWith('#')).map(s=>[s.slice(0,s.indexOf('=')),s.slice(s.indexOf('=')+1)]));
const login=await fetch('http://127.0.0.1:3000/api/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({username:'admin',password:env.SEED_PASSWORD})}).then(r=>r.json());
const result=await fetch('http://127.0.0.1:3000/api/samples?source=MOBILE&pageSize=12',{headers:{authorization:'Bearer '+login.token}}).then(r=>r.json());
console.log(result.items?.map(s=>({id:s.id,clientId:s.clientId,sequence:s.localSequence,createdAt:s.createdAt})));
if(process.argv.includes('--cleanup'))for(const id of ['cmvcjixsb0051ue2wounfw4bw','cmvcixexb003sue2w8sqdbvha']){
 const r=await fetch('http://127.0.0.1:3000/api/samples/'+id,{method:'DELETE',headers:{authorization:'Bearer '+login.token,'content-type':'application/json'},body:JSON.stringify({confirm:true})});
 if(!r.ok)throw Error('Cleanup failed '+id);console.log('Removed own test sample',id);
}
