import { test } from "node:test";
import assert from "node:assert/strict";
import { evaluateInspection } from "../../packages/shared/src/acceptance.js";
import {
  planRulesSchema,
  type DetectionBox,
} from "../../packages/contracts/src/index.js";

const rules = planRulesSchema.parse({
  product: "包装",
  purpose: "COUNT",
  classes: ["牛奶"],
  instructions: "每套放一个牛奶盒",
  coordinateSpace: "NORMALIZED_FRAME",
  region: { x: 0.1, y: 0.1, width: 0.8, height: 0.8 },
  checks: [{ classId: 0, min: 1, max: 1 }],
});
const box = (confidence = 0.9, classId = 0, x = 100): DetectionBox => ({
  classId,
  label: "牛奶",
  confidence,
  x1: x,
  y1: 100,
  x2: x + 40,
  y2: 160,
});
const evaluate = (detections: DetectionBox[] | null, extra = {}) =>
  evaluateInspection({
    rules,
    acceptance: { confidence: 0.7, qualityGate: true },
    width: 416,
    height: 416,
    quality: "PASS",
    detections,
    ...extra,
  });
test("business acceptance: exact counts, missing, extra, uncertainty and ROI", () => {
  assert.equal(evaluate([box()]).result, "PASS");
  assert.equal(evaluate([]).result, "FAIL");
  assert.equal(evaluate([box(), box(0.9, 0, 200)]).result, "FAIL");
  assert.equal(evaluate([box(0.5)]).result, "REVIEW");
  assert.equal(evaluate([box(), box(0.5, 0, 200)]).result, "REVIEW");
  const outside = { ...box(), x1: 0, x2: 10 };
  assert.equal(evaluate([box(), outside]).result, "PASS");
  assert.equal(evaluate([box(), outside]).outsideRegion, 1);
  assert.equal(evaluate([box(), box(0.9, 1)]).result, "FAIL");
  assert.equal(evaluate([box(), box(0.5, 1)]).result, "REVIEW");
});
test("faults, missing tensors, quality warnings and malformed geometry cannot pass", () => {
  assert.equal(evaluate(null).result, "REVIEW");
  assert.equal(evaluate([box()], { errorCode: 4 }).result, "ERROR");
  assert.equal(evaluate([box()], { quality: "WARNING" }).result, "REVIEW");
  assert.equal(evaluate([{ ...box(), confidence: NaN }]).result, "ERROR");
  assert.equal(evaluate([{ ...box(), x2: 500 }]).result, "ERROR");
  assert.equal(evaluate([box()], { width: 0 }).result, "ERROR");
});
test("defect-absence rules only pass with valid output and useful image", () => {
  const appearance = {
    ...rules,
    purpose: "APPEARANCE" as const,
    checks: [{ classId: 0, min: 0, max: 0 }],
  };
  assert.equal(evaluate([], { rules: appearance }).result, "PASS");
  assert.equal(evaluate(null, { rules: appearance }).result, "REVIEW");
  assert.equal(evaluate([box(0.5)], { rules: appearance }).result, "REVIEW");
  assert.equal(evaluate([box()], { rules: appearance }).result, "FAIL");
});
