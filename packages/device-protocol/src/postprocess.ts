import type { DetectionBox } from "@vision/contracts";
export const labels = ["龟裂", "夹杂", "斑块", "麻点", "轧入氧化皮", "划痕"];
const anchors = [
  [
    1.3629538461538462, 1.3798076923076923, 2.2716615384615384,
    2.843723076923077, 5.788461538461538, 5.367815384615384,
  ],
  [
    0.7740384615384615, 0.9086538461538461, 1.2451923076923077,
    1.9519230769230769, 2.7259615384615383, 2.7596153846153846,
  ],
];
const sigmoid = (v: number) => 1 / (1 + Math.exp(-v));
export function overlap(a: DetectionBox, b: DetectionBox): number {
  const i =
    Math.max(0, Math.min(a.x2, b.x2) - Math.max(a.x1, b.x1)) *
    Math.max(0, Math.min(a.y2, b.y2) - Math.max(a.y1, b.y1));
  const u = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - i;
  return u > 0 ? i / u : 0;
}
export function detect(
  out0: Buffer,
  out1: Buffer,
  threshold = 0.35,
  iou = 0.45,
): DetectionBox[] {
  if (out0.length !== 1617 || out1.length !== 6468)
    throw new Error("Tensor length mismatch");
  const candidates: DetectionBox[] = [];
  [out0, out1].forEach((raw, head) => {
    const size = head === 0 ? 7 : 14,
      scale = head === 0 ? 0.11581249687615341 : 0.15977688286248154;
    const value = (a: number, c: number, cell: number) =>
      raw.readInt8((a * 11 + c) * size * size + cell) * scale;
    for (let a = 0; a < 3; a++)
      for (let cell = 0; cell < size * size; cell++) {
        const obj = sigmoid(value(a, 4, cell));
        if (obj < threshold) continue;
        let cls = 0;
        for (let c = 1; c < 6; c++)
          if (value(a, 5 + c, cell) > value(a, 5 + cls, cell)) cls = c;
        const score = obj * sigmoid(value(a, 5 + cls, cell));
        if (score < threshold) continue;
        const x = ((sigmoid(value(a, 0, cell)) + (cell % size)) * 416) / size,
          y =
            ((sigmoid(value(a, 1, cell)) + Math.floor(cell / size)) * 416) /
            size,
          w =
            (Math.exp(value(a, 2, cell)) * anchors[head]![a * 2]! * 416) / size,
          h =
            (Math.exp(value(a, 3, cell)) * anchors[head]![a * 2 + 1]! * 416) /
            size;
        candidates.push({
          classId: cls,
          label: labels[cls]!,
          confidence: score,
          x1: x - w / 2,
          y1: y - h / 2,
          x2: x + w / 2,
          y2: y + h / 2,
        });
      }
  });
  const kept: DetectionBox[] = [];
  for (const b of candidates.sort((a, b) => b.confidence - a.confidence))
    if (!kept.some((k) => k.classId === b.classId && overlap(k, b) > iou))
      kept.push(b);
  return kept.map((b) => ({
    ...b,
    x1: Math.max(0, b.x1),
    y1: Math.max(0, b.y1),
    x2: Math.min(416, b.x2),
    y2: Math.min(416, b.y2),
  }));
}
