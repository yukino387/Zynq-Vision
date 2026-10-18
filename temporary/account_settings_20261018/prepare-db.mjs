import '../../apps/server/dist/config.js';
import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
const require=createRequire(new URL('../../apps/server/package.json',import.meta.url));
const {PrismaClient}=require('@prisma/client');
const db=new PrismaClient();
try {
  const commands=await db.command.count({where:{status:{in:['QUEUED','RUNNING']}}});
  const jobs=await db.job.count({where:{status:{in:['QUEUED','RUNNING']}}});
  if(commands+jobs)throw new Error('Other device tasks are active; do not restart');
  const folder=resolve('temporary/account_settings_20261018');
  mkdirSync(folder,{recursive:true});
  const backup=resolve(folder,`before-${Date.now()}.db`).replaceAll('\\','/');
  await db.$executeRawUnsafe(`VACUUM INTO '${backup.replaceAll("'","''")}'`);
  console.log(JSON.stringify({pendingCommands:commands,pendingJobs:jobs,backup}));
} finally {await db.$disconnect();}
