import {
  existsSync,
  copyFileSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { randomBytes } from "node:crypto";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
for (const name of ["storage", "exports", "logs"])
  mkdirSync(resolve("data", name), { recursive: true });
if (!existsSync(".env")) {
  copyFileSync(".env.example", ".env");
  writeFileSync(
    ".env",
    readFileSync(".env", "utf8")
      .replace(
        "replace-with-at-least-32-random-characters",
        randomBytes(48).toString("hex"),
      )
      .replace(
        "SEED_PASSWORD=",
        "SEED_PASSWORD=" + randomBytes(12).toString("base64url"),
      ),
  );
  console.log(
    "Created local .env. Read SEED_PASSWORD there for initial demo accounts.",
  );
}
for (const command of ["db:deploy", "seed"]) {
  const runner = process.env.npm_execpath;
  if (!runner) throw new Error("Run this initializer through pnpm run setup.");
  const result = spawnSync(
    process.execPath,
    [runner, "--filter", "@vision/server", command],
    { stdio: "inherit" },
  );
  if (result.status !== 0) process.exit(result.status ?? 1);
}
