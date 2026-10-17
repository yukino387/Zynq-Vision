import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { root } from "../config.js";
// Exact integer coefficients and two-pass clipping from camera/int8/gray.cpp.
// This is a server reconstruction, not bytes reported by the board.
const coefficients = [
  ...readFileSync(
    resolve(root, "camera/int8/gray_coefficients.h"),
    "utf8",
  ).matchAll(/\{(\d+),(\d+),\{([^}]+)\}\}/g),
].map((m) => ({
  start: Number(m[1]),
  count: Number(m[2]),
  values: m[3]!.split(",").map(Number),
}));
if (coefficients.length !== 224)
  throw new Error("Source resize coefficient table unavailable");
const clip = (v: number) => Math.max(0, Math.min(255, v));
export function modelInput(raw: Buffer): Buffer {
  const horizontal = new Uint8Array(416 * 224),
    gray = new Uint8Array(416);
  for (let y = 0; y < 416; y++) {
    for (let x = 0; x < 416; x++) {
      const p = raw.readUInt16LE((y * 416 + x) * 2),
        r5 = p >>> 11,
        g6 = (p >>> 5) & 63,
        b5 = p & 31;
      gray[x] =
        (((r5 << 3) | (r5 >>> 2)) * 19595 +
          ((g6 << 2) | (g6 >>> 4)) * 38470 +
          ((b5 << 3) | (b5 >>> 2)) * 7471 +
          32768) >>>
        16;
    }
    for (let x = 0; x < 224; x++) {
      const c = coefficients[x]!;
      let sum = 0;
      for (let k = 0; k < c.count; k++)
        sum += gray[c.start + k]! * c.values[k]!;
      horizontal[y * 224 + x] = clip(Math.floor((sum + 2 ** 21) / 2 ** 22));
    }
  }
  const output = Buffer.alloc(224 * 224);
  for (let y = 0; y < 224; y++) {
    const c = coefficients[y]!;
    for (let x = 0; x < 224; x++) {
      let sum = 2 ** 21;
      for (let k = 0; k < c.count; k++)
        sum += horizontal[(c.start + k) * 224 + x]! * c.values[k]!;
      const v = clip(Math.floor(sum / 2 ** 22));
      output[y * 224 + x] = Math.floor((v * 127 + 127) / 255);
    }
  }
  return output;
}
