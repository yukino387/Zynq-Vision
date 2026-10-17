import { createHash } from "node:crypto";
import type { ModelManifest } from "@vision/contracts";
import { compatibility } from "@vision/shared";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { crc32 } from "node:zlib";
import { root } from "../config.js";
import { DomainError } from "../core/errors.js";
const commands = (
  JSON.parse(
    readFileSync(resolve(root, "camera/training/graph.json"), "utf8"),
  ) as { commands: number[][] }
).commands;
export function zynqManifest(
  weights: Buffer,
  channels: 1 | 3 = 1,
): ModelManifest {
  return {
    formatVersion: 1,
    networkTemplate: "ZYNQ7020_NEU_INT8_V1",
    firmwareInterfaceVersion: "CNC2-SD-25",
    preprocessProfile:
      channels === 1 ? "RGB565_GRAY224_INT8_V1" : "RGB565_RGB224_INT8_V1",
    input: { width: 224, height: 224, channels, dtype: "INT8" },
    output: [
      [1, 33, 7, 7],
      [1, 33, 14, 14],
    ],
    classCount: 6,
    classes: ["龟裂", "夹杂", "斑块", "麻点", "轧入氧化皮", "划痕"],
    quantization: {
      scheme: "FIXED_INT8",
      inputScale: 1 / 127,
      inputZeroPoint: 0,
      outputScales: [0.11581249687615341, 0.15977688286248154],
    },
    weights: {
      size: weights.length,
      sha256: createHash("sha256").update(weights).digest("hex"),
    },
  };
}

export function validateZynqPackage(
  weights: Buffer,
  version: string,
  manifest: ModelManifest,
) {
  const fail = () => {
    throw new DomainError(
      "MODEL_INCOMPATIBLE",
      "Invalid fixed-graph PL model package, metadata or manifest",
      422,
    );
  };
  if (
    weights.length !== 6416360 ||
    version.length < 1 ||
    version.length > 63 ||
    [...version].some((c) => c.charCodeAt(0) < 1 || c.charCodeAt(0) > 127)
  )
    return fail();
  const channels = manifest.input.channels;
  if (channels !== 1 && channels !== 3) return fail();
  if (
    compatibility(zynqManifest(weights, channels), manifest).length ||
    weights.readUInt32LE(0) !== 0x314e4e43 ||
    weights.readUInt32LE(4) !== 1 ||
    weights.readUInt32LE(8) !== 6350208 ||
    weights.readUInt32LE(12) !== 66024 ||
    weights.readUInt32LE(16) !== 0 ||
    weights.readUInt32LE(20) !== 0 ||
    weights.readUInt32LE(124) !== 0 ||
    crc32(weights.subarray(0, 120)) !== weights.readUInt32LE(120) ||
    !weights
      .subarray(24, 88)
      .equals(
        Buffer.concat([
          Buffer.from(version, "ascii"),
          Buffer.alloc(64 - version.length),
        ]),
      ) ||
    createHash("sha256").update(weights).digest("hex") !==
      manifest.weights.sha256 ||
    manifest.weights.size !== weights.length ||
    createHash("sha256").update(weights.subarray(128)).digest("hex") !==
      weights.subarray(88, 120).toString("hex")
  )
    return fail();
  const metadata = weights.subarray(128 + 6350208);
  commands.forEach((command, i) =>
    command.forEach((value, j) => {
      if (
        metadata.readInt32LE((i * 10 + j) * 4) !==
        (i === 0 && j === 4 ? channels : value)
      )
        fail();
    }),
  );
  for (const command of commands) {
    const offset = command[3]!,
      co = command[5]!,
      kernel = command[8]!;
    if (kernel === 1 || kernel === 3) {
      for (let c = 0; c < co; c++)
        for (const scale of [1, 3]) {
          const multiplier = metadata.readInt32LE(
              (offset + scale * co + c) * 4,
            ),
            shift = metadata.readInt32LE((offset + (scale + 1) * co + c) * 4);
          if (multiplier <= 0 || shift < 1 || shift > 62) fail();
        }
    } else if (
      kernel === 5 &&
      (metadata.readInt32LE(offset * 4) <= 0 ||
        metadata.readInt32LE((offset + 1) * 4) < 1 ||
        metadata.readInt32LE((offset + 1) * 4) > 62)
    )
      fail();
  }
}
