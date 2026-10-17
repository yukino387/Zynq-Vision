import { createHash } from "node:crypto";
import type { ModelManifest } from "@vision/contracts";
export const simulatedWeights = (version: string) =>
  Buffer.from(
    JSON.stringify({
      source: "SIMULATED",
      format: "SIMULATOR_FIXTURE_ONLY",
      version,
    }),
  );
export function simulatorManifest(weights: Buffer): ModelManifest {
  return {
    formatVersion: 1,
    networkTemplate: "SIMULATOR_DEFECT_V1",
    firmwareInterfaceVersion: "SIMULATED-v1",
    preprocessProfile: "SIMULATED-RGB565-RECONSTRUCTED-GRAY224",
    input: { width: 224, height: 224, channels: 1, dtype: "INT8" },
    output: [
      [33, 7, 7],
      [33, 14, 14],
    ],
    classCount: 6,
    classes: ["龟裂", "夹杂", "斑块", "麻点", "轧入氧化皮", "划痕"],
    quantization: {
      scheme: "SIMULATED_SYMMETRIC",
      inputScale: 1 / 127,
      inputZeroPoint: 0,
      outputScales: [0.1158124968761534, 0.1597768828624815],
    },
    weights: {
      size: weights.length,
      sha256: createHash("sha256").update(weights).digest("hex"),
    },
  };
}
