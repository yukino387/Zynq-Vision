import { readFileSync } from "node:fs";
import { manifestSchema } from "../../packages/contracts/src/index.js";
import { validateZynqPackage } from "../../apps/server/src/models/zynq-profile.js";

const dir = process.argv[2];
const manifest = manifestSchema.parse(JSON.parse(readFileSync(`${dir}/manifest.json`, "utf8")));
const weights = readFileSync(`${dir}/model.bin`);
const version = weights.subarray(24, 88).toString("ascii").split("\0")[0];
validateZynqPackage(weights, version, manifest);
console.log(JSON.stringify({ ok: true, version, bytes: weights.length, sha256: manifest.weights.sha256,
  channels: manifest.input.channels, classes: manifest.classes }));
