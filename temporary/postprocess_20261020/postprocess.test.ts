import assert from "node:assert/strict";
import { writeFileSync } from "node:fs";
import { postprocessSchema } from "../../packages/contracts/src/index.js";
import {
  postprocessBoxes,
  detectObjects,
  detect,
} from "../../packages/device-protocol/src/postprocess.js";
const cases: any[] = [];
const b = (
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  classId = 0,
  confidence = 0.9,
) => ({ classId, label: "fixture", confidence, x1, y1, x2, y2 });
function test(
  name: string,
  boxes: any[],
  count: number,
  policy: any = {},
  checks?: (r: any) => void,
) {
  const output = postprocessBoxes(boxes, policy);
  assert.equal(output.boxes.length, count, name);
  checks?.(output);
  cases.push({
    name,
    boxes,
    policy: postprocessSchema.parse(policy),
    expected: output,
  });
}
test(
  "nested-high-confidence-outer",
  [b(10, 10, 300, 300, 0, 0.99), b(90, 90, 170, 170, 0, 0.8)],
  1,
  {},
  (r) => {
    assert.equal(r.boxes[0].x1, 90);
    assert.equal(r.report.nested, 1);
  },
);
test(
  "nested-before-nms",
  [b(10, 10, 120, 120, 0, 0.99), b(20, 20, 100, 100, 0, 0.8)],
  1,
  {},
  (r) => assert.equal(r.boxes[0].x1, 20),
);
test(
  "nested-chain",
  [b(0, 0, 400, 400), b(20, 20, 250, 250), b(40, 40, 80, 80)],
  1,
  {},
  (r) => assert.equal(r.report.nested, 2),
);
test(
  "container-has-three-items-same-class",
  [
    b(0, 0, 400, 400),
    b(20, 20, 70, 70),
    b(150, 20, 200, 70),
    b(280, 20, 330, 70),
  ],
  3,
);
test(
  "different-class-container-preserved",
  [b(0, 0, 400, 400), b(20, 20, 70, 70, 1)],
  2,
);
test(
  "same-size-high-confidence-wins",
  [b(20, 20, 100, 100, 0, 0.7), b(23, 23, 103, 103, 0, 0.95)],
  1,
  {},
  (r) => assert.equal(r.boxes[0].confidence, 0.95),
);
test(
  "deterministic-tie",
  [b(0, 0, 100, 100), b(10, 10, 100, 100)],
  1,
  {},
  (r) => assert.equal(r.boxes[0].x1, 10),
);
test("adjacent-objects-preserved", [b(20, 20, 70, 70), b(65, 20, 115, 70)], 2);
test(
  "clip-before-overlap",
  [b(-100, -100, 60, 60), b(0, 0, 60, 60)],
  1,
  {},
  (r) => assert.equal(r.boxes[0].x1, 0),
);
test(
  "outside-and-degenerate",
  [b(-10, -10, -1, -1), b(10, 10, 10, 20), b(20, 20, 15, 25)],
  0,
  {},
  (r) => assert.equal(r.report.invalid, 2),
);
test("invalid-data", [b(0, 0, 10, 10, 6), b(0, 0, 10, 10, 0, 2)], 0, {}, (r) =>
  assert.equal(r.report.invalid, 2),
);
test("tiny-box", [b(10, 10, 10.5, 30), b(10, 10, 11, 11)], 0);
test(
  "confidence-floor",
  [b(10, 10, 20, 20, 0, 0.34), b(30, 30, 40, 40, 0, 0.35)],
  1,
);
test("liquid-thin-line", [b(50, 160, 350, 162, 1)], 1);
test(
  "candidate-limit-review",
  [b(0, 0, 20, 20), b(40, 40, 60, 60), b(80, 80, 100, 100)],
  2,
  { maxDetections: 2 },
  (r) => assert(r.report.overflow),
);
test("programmable-area", [b(0, 0, 20, 20)], 0, { minArea: 0.01 });
test("programmable-nms", [b(0, 0, 100, 100), b(20, 0, 120, 100)], 2, {
  nmsIou: 0.9,
});
test("coverage-not-containment", [b(0, 0, 100, 100), b(90, 0, 190, 100)], 2);
let seed = 7123;
function random() {
  seed = (1664525 * seed + 1013904223) >>> 0;
  return seed / 2 ** 32;
}
for (let c = 0; c < 80; c++) {
  const boxes = Array.from({ length: 25 }, () => {
    const x = random() * 480 - 32,
      y = random() * 480 - 32;
    return b(
      x,
      y,
      x + 1 + random() * 200,
      y + 1 + random() * 200,
      Math.floor(random() * 4),
      0.2 + random() * 0.8,
    );
  });
  test(`random-${c}`, boxes, postprocessBoxes(boxes).boxes.length);
}
const tensorCases: any[] = [];
for (let i = 0; i < 5; i++) {
  const out0 = Buffer.alloc(1617, -128),
    out1 = Buffer.alloc(6468, -128);
  const inject = (
    raw: Buffer,
    size: number,
    a: number,
    cell: number,
    cls: number,
    offset = 0,
  ) => {
    const set = (channel: number, v: number) =>
      raw.writeInt8(v, (a * 11 + channel) * size * size + cell);
    set(0, offset);
    set(1, offset);
    set(2, i - 2);
    set(3, i - 2);
    set(4, 60);
    set(5 + cls, 50);
  };
  inject(out0, 7, 0, 24, i % 3);
  inject(out1, 14, 0, 105, i % 3, 3);
  inject(out1, 14, 2, 25, (i + 1) % 3, -3);
  const output = detectObjects(out0, out1);
  tensorCases.push({
    out0: [...new Int8Array(out0)],
    out1: [...new Int8Array(out1)],
    expected: output,
  });
  assert(output.boxes.length > 0);
  assert(detect(out0, out1).length > 0);
}
assert.throws(() => postprocessBoxes([], {}, 0, 416));
assert(!postprocessSchema.safeParse({ maxDetections: 0 }).success);
assert(!postprocessSchema.safeParse({ nmsIou: 1 }).success);
const invalid = postprocessBoxes([b(0, 0, 10, 10, 0, NaN)]);
assert.equal(invalid.report.invalid, 1);
writeFileSync(
  "temporary/postprocess_20261020/cases.json",
  JSON.stringify({ cases, tensorCases }),
);
console.log(
  `POSTPROCESS_TS_PASS ${cases.length} box cases + ${tensorCases.length} tensor cases`,
);
