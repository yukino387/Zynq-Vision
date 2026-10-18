import { PrismaClient } from '../../apps/server/node_modules/@prisma/client/default.js';
import { hash } from '../../apps/server/node_modules/bcryptjs/index.js';
const db = new PrismaClient({datasources:{db:{url:'file:C:/00_workplace/fpga/cnn_accelerator/temporary/frontend_usability/run-1792230158903/app.db'}}});
for (const [username,role,name] of [['qa-worker','OPERATOR','现场工人（隔离验证）'],['qa-maintenance','ENGINEER','技术维护（隔离验证）']]) await db.user.upsert({where:{username},update:{},create:{username,role,name,passwordHash:await hash('UI-Workflow-2026!',4)}});
await db.$disconnect();
console.log('Isolated worker and maintenance accounts ready');
