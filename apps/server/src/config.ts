import { config as dotenv } from "dotenv";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
export const root = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
dotenv({ path: resolve(root, ".env"), quiet: true });
const env = z
  .object({
    DATABASE_URL: z.string().default("file:../../../data/app.db"),
    JWT_SECRET: z.string().min(32),
    STORAGE_ROOT: z.string().default("../../data/storage"),
    SERVER_HOST: z.string().default("0.0.0.0"),
    SERVER_PORT: z.coerce.number().int().min(1).max(65535).default(3000),
    DEVICE_TIMEOUT: z.coerce.number().positive().default(30000),
    DEVICE_STALE: z.coerce.number().positive().default(10000),
    WS_PATH: z.string().default("/ws"),
    ZYNQ_HOST: z.string().ip().default("169.254.140.110"),
    ZYNQ_PORT: z.coerce.number().default(5001),
    ZYNQ_LOCAL_PORT: z.coerce.number().default(5003),
    TRAINING_PYTHON: z
      .string()
      .min(1)
      .default(
        resolve(
          root,
          "data/training-venv",
          process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
        ),
      ),
  })
  .parse(process.env);
if (env.DEVICE_STALE >= env.DEVICE_TIMEOUT)
  throw new Error("DEVICE_STALE must be less than DEVICE_TIMEOUT");
export const config = {
  ...env,
  storage: resolve(root, "apps/server", env.STORAGE_ROOT),
};
process.env.DATABASE_URL = env.DATABASE_URL;
