import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { evaluateInspection } from "../../packages/shared/src/acceptance.js";
import { detect } from "../../packages/device-protocol/src/postprocess.js";
import {
  planRulesSchema,
  type DetectionBox,
} from "../../packages/contracts/src/index.js";
const root = resolve("temporary/inspection_terminal_20261018"),
  executable = resolve(root, "native_oracle.exe");
let seed = 1234567;
const random = () => {
  seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
  return seed / 4294967296;
};
test("native ARM-path acceptance logic matches the platform across 1000 deterministic cases", () => {
  const cases = Array.from({ length: 1000 }, (_, i) => {
    const n = 1 + Math.floor(random() * 6),
      classes = Array.from({ length: n }, (_, id) => `class ${id}`);
    const checks = classes.map((_, classId) => {
      const min = Math.floor(random() * 3);
      return { classId, min, max: min + Math.floor(random() * 2) };
    });
    const rules = planRulesSchema.parse({
      product: "TEST",
      purpose: "COUNT",
      instructions: "TEST",
      classes,
      checks,
      coordinateSpace: "NORMALIZED_FRAME",
      region: { x: 0.1, y: 0.1, width: 0.8, height: 0.8 },
    });
    const detections: DetectionBox[] = Array.from(
      { length: Math.floor(random() * 12) },
      () => {
        const x = Math.floor(random() * 350),
          y = Math.floor(random() * 350);
        return {
          classId: Math.floor(random() * 7),
          label: "TEST",
          confidence: [0.2, 0.35, 0.5, 0.7, 0.8, 0.95][
            Math.floor(random() * 6)
          ]!,
          x1: x,
          y1: y,
          x2: x + 40,
          y2: y + 40,
        };
      },
    );
    return {
      rules,
      acceptance: { confidence: 0.7, qualityGate: true },
      detections: i % 19 === 0 ? null : detections,
      width: 416,
      height: 416,
      quality: i % 17 === 0 ? "WARNING" : "PASS",
      errorCode: i % 23 === 0 ? 4 : 0,
    };
  });
  const file = resolve(root, "native-cases.json");
  writeFileSync(file, JSON.stringify(cases));
  const actual = JSON.parse(
    execFileSync(executable, [file], {
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
    }),
  );
  for (let i = 0; i < cases.length; i++) {
    const expected = evaluateInspection(cases[i]!);
    assert.deepEqual(
      actual[i],
      {
        result: expected.result,
        outsideRegion: expected.outsideRegion,
        findings: expected.findings.map(
          ({ classId, count, uncertain, result }) => ({
            classId,
            count,
            uncertain,
            result,
          }),
        ),
      },
      `case ${i}`,
    );
  }
});
test("native YOLO decode and NMS match the existing platform on quantized tensor fixtures", () => {
  const tensors = Array.from({ length: 12 }, () => ({
    out0: Array.from({ length: 1617 }, () => Math.floor(random() * 256) - 128),
    out1: Array.from({ length: 6468 }, () => Math.floor(random() * 256) - 128),
  }));
  const file = resolve(root, "native-tensors.json");
  writeFileSync(file, JSON.stringify({ tensors }));
  const actual = JSON.parse(
    execFileSync(executable, [file], {
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
    }),
  );
  tensors.forEach((tensor, i) => {
    const expected = detect(
      Buffer.from(tensor.out0.map((v) => v & 255)),
      Buffer.from(tensor.out1.map((v) => v & 255)),
    );
    assert.equal(actual[i].length, expected.length);
    expected.forEach((box, j) => {
      assert.equal(actual[i][j].classId, box.classId);
      for (const key of ["confidence", "x1", "y1", "x2", "y2"] as const)
        assert.ok(
          Math.abs(actual[i][j][key] - box[key]) < 1e-8,
          `tensor ${i} box ${j} ${key}`,
        );
    });
  });
});
