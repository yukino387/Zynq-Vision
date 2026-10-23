import {
  postprocessSchema,
  type DetectionBox,
  type PostprocessPolicy,
  type PostprocessReport,
} from "@vision/contracts";
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
function decodeCandidates(
  out0: Buffer,
  out1: Buffer,
  threshold = 0.35,
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
  return candidates;
}

// Retained for evidence written before BOX_FILTER_V2 and the bare-metal protocol.
export function detect(
  out0: Buffer,
  out1: Buffer,
  threshold = 0.35,
  iou = 0.45,
): DetectionBox[] {
  const candidates = decodeCandidates(out0, out1, threshold);
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

/** One set of surviving boxes feeds display, counting and tracking. Coordinates are frame pixels. */
const sameCenter = (a: DetectionBox, b: DetectionBox, distance: number) => {
  const dx = (a.x1 + a.x2) / 2 - (b.x1 + b.x2) / 2,
    dy = (a.y1 + a.y2) / 2 - (b.y1 + b.y2) / 2;
  return dx * dx + dy * dy < distance * distance;
};

export function postprocessBoxes(
  candidates: DetectionBox[],
  configuration: Partial<PostprocessPolicy> = {},
  width = 416,
  height = 416,
): { boxes: DetectionBox[]; report: PostprocessReport } {
  if (
    !Number.isFinite(width) ||
    !Number.isFinite(height) ||
    width <= 0 ||
    height <= 0
  )
    throw new Error("Invalid frame dimensions");
  const policy = postprocessSchema.parse(configuration);
  // mergeDistance is defined in 224-px network units; boxes are frame pixels.
  const merge = policy.mergeDistance * (width / 224);
  const report: PostprocessReport = {
    policy,
    candidates: candidates.length,
    invalid: 0,
    tiny: 0,
    nested: 0,
    suppressed: 0,
    overflow: false,
  };
  const clean: DetectionBox[] = [];
  const area = (b: DetectionBox) => (b.x2 - b.x1) * (b.y2 - b.y1);
  for (const box of candidates) {
    if (
      ![box.classId, box.confidence, box.x1, box.y1, box.x2, box.y2].every(
        Number.isFinite,
      ) ||
      !Number.isInteger(box.classId) ||
      box.classId < 0 ||
      box.classId > 5 ||
      box.confidence < 0 ||
      box.confidence > 1 ||
      box.x2 <= box.x1 ||
      box.y2 <= box.y1
    ) {
      report.invalid++;
      continue;
    }
    if (box.confidence < policy.minScore) continue;
    const b = {
      ...box,
      x1: Math.max(0, Math.min(width, box.x1)),
      y1: Math.max(0, Math.min(height, box.y1)),
      x2: Math.max(0, Math.min(width, box.x2)),
      y2: Math.max(0, Math.min(height, box.y2)),
    };
    if (
      b.x2 - b.x1 < 1 ||
      b.y2 - b.y1 < 1 ||
      area(b) < policy.minArea * width * height
    ) {
      report.tiny++;
      continue;
    }
    clean.push(b);
  }
  if (policy.algorithm === "BOX_FILTER_V3") {
    clean.sort((a, b) => b.confidence - a.confidence || area(a) - area(b));
    const kept: DetectionBox[] = [];
    for (const b of clean) {
      let removed = false;
      for (const k of kept) {
        if (k.classId !== b.classId) continue;
        const small = Math.min(area(k), area(b)),
          large = Math.max(area(k), area(b));
        const intersection =
          Math.max(0, Math.min(k.x2, b.x2) - Math.max(k.x1, b.x1)) *
          Math.max(0, Math.min(k.y2, b.y2) - Math.max(k.y1, b.y1));
        // A weak nested box cannot delete a reliable product. Suppressed boxes
        // cannot suppress anything else, including through containment chains.
        if (
          large >= 1.5 * small &&
          intersection / small >= policy.containment
        ) {
          report.nested++;
          removed = true;
          break;
        }
        if (
          overlap(k, b) > policy.nmsIou ||
          (merge > 0 && sameCenter(k, b, merge))
        ) {
          report.suppressed++;
          removed = true;
          break;
        }
      }
      if (!removed) kept.push(b);
    }
    report.overflow = kept.length > policy.maxDetections;
    return { boxes: kept.slice(0, policy.maxDetections), report };
  }
  // Remove enclosing duplicates BEFORE NMS, so a confident large box cannot erase its smaller target.
  // Different classes remain independent: bottle/liquid and tray/items are valid nested objects.
  const leaves = clean.filter((outer, index) => {
    const removed = clean.some((inner, other) => {
      if (
        index === other ||
        outer.classId !== inner.classId ||
        area(outer) < 1.5 * area(inner)
      )
        return false;
      const intersection =
        Math.max(
          0,
          Math.min(outer.x2, inner.x2) - Math.max(outer.x1, inner.x1),
        ) *
        Math.max(
          0,
          Math.min(outer.y2, inner.y2) - Math.max(outer.y1, inner.y1),
        );
      return intersection / area(inner) >= policy.containment;
    });
    if (removed) report.nested++;
    return !removed;
  });
  leaves.sort((a, b) => b.confidence - a.confidence || area(a) - area(b));
  const kept: DetectionBox[] = [];
  for (const b of leaves) {
    if (
      kept.some(
        (k) =>
          k.classId === b.classId &&
          (overlap(k, b) > policy.nmsIou ||
            (merge > 0 && sameCenter(k, b, merge))),
      )
    )
      report.suppressed++;
    else kept.push(b);
  }
  report.overflow = kept.length > policy.maxDetections;
  return { boxes: kept.slice(0, policy.maxDetections), report };
}

export function detectObjects(
  out0: Buffer,
  out1: Buffer,
  policy: Partial<PostprocessPolicy> = {},
) {
  return postprocessBoxes(decodeCandidates(out0, out1), policy);
}
