import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
async function main() {
const out = resolve("temporary/frontend_usability", `run-${Date.now()}`);
mkdirSync(out, { recursive: true });
const script = `from pathlib import Path
import sqlite3,shutil,sys
root=Path.cwd();out=Path(sys.argv[1]);source=sqlite3.connect((root/'data/app.db').as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(out/'app.db');source.backup(target);source.close()
for (key,) in target.execute('SELECT storageKey FROM Asset'):
 p=root/'data/storage'/key;q=out/'storage'/key
 if p.is_file():q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
target.execute("UPDATE Device SET type='SIMULATOR',name='界面验证设备',reportedState='{}',desiredState='{}'")
target.execute("UPDATE Job SET status='CANCELLED' WHERE status IN ('RUNNING','QUEUED')")
target.execute("UPDATE TrainingJob SET status='CANCELLED' WHERE status IN ('RUNNING','QUEUED')")
target.commit();target.close()`;
execFileSync("python", ["-X", "utf8", "-c", script, out], { stdio: "pipe" });
process.env.DATABASE_URL = `file:${resolve(out, "app.db").replaceAll("\\", "/")}`;
process.env.STORAGE_ROOT = resolve(out, "storage");
process.env.JWT_SECRET = "isolated-ui-check-secret-at-least-32-characters";
const { createApp } = await import("../../apps/server/src/bootstrap.js");
const { Db } = await import("../../apps/server/src/core/db.js");
const { hash } =
  await import("../../apps/server/node_modules/bcryptjs/index.js");
const app = await createApp(false),
  db = app.get(Db);
await db.user.upsert({
  where: { username: "qa-usability" },
  create: {
    username: "qa-usability",
    name: "界面验证（隔离数据）",
    role: "ADMIN",
    passwordHash: await hash("UI-Workflow-2026!", 4),
  },
  update: { disabled: false },
});
await app.listen(3017, "127.0.0.1");
console.log(
  JSON.stringify({ ready: true, url: "http://127.0.0.1:3017", data: out }),
);
process.on("SIGINT", () => {
  void app.close().then(() => process.exit(0));
});
}
void main();
