import "reflect-metadata";
import "../../apps/server/src/config.js";
import { Db } from "../../apps/server/src/core/db.js";
import { hash } from "../../apps/server/node_modules/bcryptjs/index.js";
async function main() {
  if (process.argv.includes("--disable")) {
    const login = await fetch("http://localhost:3000/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        username: "admin",
        password: process.env.SEED_PASSWORD,
      }),
    });
    if (!login.ok) throw new Error("Local cleanup authentication failed");
    const { token } = (await login.json()) as { token: string };
    const headers = {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
    };
    const users = (await fetch(
      "http://localhost:3000/api/users?search=DEMO%20%2F%20UI%20verification",
      { headers },
    ).then((r) => r.json())) as { items: { id: string; username: string }[] };
    const user = users.items.find((u) => u.username === "demo-ui-check");
    if (user) {
      const response = await fetch(
        `http://localhost:3000/api/users/${user.id}`,
        { method: "PATCH", headers, body: JSON.stringify({ disabled: true }) },
      );
      if (!response.ok) throw new Error("Failed to disable UI test account");
    }
    console.log("UI verification account disabled.");
    return;
  }
  const db = new Db();
  await db.user.upsert({
    where: { username: "demo-ui-check" },
    create: {
      username: "demo-ui-check",
      name: "DEMO / UI verification",
      role: "ADMIN",
      passwordHash: await hash("Local-UI-QA-2026!", 12),
    },
    update: { disabled: false },
  });
  await db.$disconnect();
  console.log("Local UI verification account ready.");
}
void main();
