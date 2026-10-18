// 只读校验 seed 的三个账号能否登录。密码从本机 .env 读取，不打印。
import fs from "node:fs";

const env = Object.fromEntries(
  fs
    .readFileSync(".env", "utf8")
    .split(/\r?\n/)
    .filter((line) => line.includes("=") && !line.trimStart().startsWith("#"))
    .map((line) => {
      const at = line.indexOf("=");
      return [line.slice(0, at).trim(), line.slice(at + 1).trim()];
    }),
);

const base = `http://${env.SERVER_HOST === "0.0.0.0" ? "localhost" : env.SERVER_HOST}:${env.SERVER_PORT}`;
const password = env.SEED_PASSWORD;

if (!password) throw new Error(".env 中缺少 SEED_PASSWORD");

for (const username of ["admin", "engineer", "operator"]) {
  const response = await fetch(`${base}/api/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const body = await response.json().catch(() => ({}));
  const role = body?.user?.role ?? body?.role ?? "(未返回 role)";
  const token = typeof body?.token === "string" ? "token 已返回" : "无 token";
  console.log(`${username.padEnd(9)} HTTP ${response.status}  role=${role}  ${token}`);
}
