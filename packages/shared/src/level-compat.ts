import type {
  DetectionBox,
  InspectionDecision,
  LevelEvidence,
  LevelReport,
} from "@vision/contracts";

const roundEven = (value: number) => {
  const floor = Math.floor(value),
    fraction = value - floor;
  return fraction === 0.5 ? floor + (floor % 2) : Math.round(value);
};
const median = (values: number[]) => {
  values.sort((a, b) => a - b);
  const middle = values.length >> 1;
  return values.length % 2
    ? values[middle]!
    : (values[middle - 1]! + values[middle]!) / 2;
};
/** Same normalized image and measurement as the LEVEL-v3 board compatibility path. */
export function measureLevelGray(
  gray: Uint8Array,
  labelTop: number,
  labelHeight: number,
) {
  if (gray.length !== 224 * 224) throw new Error("液位测量图像长度无效");
  const lo = Math.max(3, Math.trunc(labelTop - 1.2 * labelHeight));
  const hi = Math.min(220, Math.trunc(labelTop - 0.25 * labelHeight));
  const n = hi - lo,
    sup = Math.max(1, roundEven(0.03 * labelHeight));
  // No visible surface above the label: report no row at all. The missing
  // line is itself the evidence (LEVEL-ROW-v1.3 "invisible = low").
  const miss = (strength: number) => ({ row: null, strength });
  if (n < 6 || 2 * sup >= n) return miss(0);
  const base = Array.from({ length: 67 }, (_, x) =>
    median(Array.from({ length: n }, (_, y) => gray[(lo + y) * 224 + x + 78]!)),
  );
  const profile = Array.from({ length: n }, (_, y) =>
    median(base.map((value, x) => gray[(lo + y) * 224 + x + 78]! - value)),
  );
  const score = (i: number) => {
    let difference = 0;
    for (let k = 0; k < sup; k++)
      difference += profile[i + k]! - profile[i - sup + k]!;
    return Math.abs(difference / sup);
  };
  let best = -1,
    bestIndex = sup;
  for (let i = sup; i < n - sup; i++) {
    const value = score(i);
    if (value > best) {
      best = value;
      bestIndex = i;
    }
  }
  if (best < 4) return miss(best);
  // A liquid line is a broad dark-below step across the measured columns.
  // Cap/neck edges are narrow and shallow; reject them instead of reporting
  // the cap as the level (empty bottles used to pass this way).
  const support = Array.from({ length: 67 }, (_, x) => {
    let above = 0,
      below = 0;
    for (let k = 0; k < sup; k++) {
      above += gray[(lo + bestIndex - sup + k) * 224 + x + 78]!;
      below += gray[(lo + bestIndex + k) * 224 + x + 78]!;
    }
    return below - above;
  });
  const ordered = [...support].sort((left, right) => left - right);
  const medianDark = ordered[ordered.length >> 1]!;
  const dark = support.filter((value) => value <= -4 * sup).length;
  if (medianDark > -9 * sup || dark * 10 < 7 * support.length)
    return miss(best);
  const a = bestIndex >= 2 * sup ? score(bestIndex - sup) : best;
  const c = bestIndex + 2 * sup <= n ? score(bestIndex + sup) : best;
  const d = a - 2 * best + c;
  return {
    row: lo + bestIndex + (Math.abs(d) > 1e-9 ? (0.5 * (a - c)) / d : 0),
    strength: best,
  };
}
export function mapLevelBoxes(boxes: DetectionBox[], level: LevelReport) {
  if (!level.labelFound) return [];
  const best = boxes
    .filter((box) => box.classId === 0)
    .sort((a, b) => b.confidence - a.confidence)[0];
  if (!best) return [];
  const [x0, y0, x1, y1] = level.crop,
    width = Math.max(8, roundEven(((x1 - x0) * 224) / (y1 - y0)));
  const offset =
    width < 224
      ? -Math.floor((224 - width) / 2)
      : Math.floor((width - 224) / 2);
  const clamp = (value: number) => Math.min(416, Math.max(0, value));
  const x = (value: number) =>
    clamp(x0 + (((value * 224) / 416 + offset) * (x1 - x0)) / width);
  const y = (value: number) => clamp(y0 + (value * (y1 - y0)) / 416);
  return [
    { ...best, x1: x(best.x1), x2: x(best.x2), y1: y(best.y1), y2: y(best.y2) },
  ];
}
export function recomputeLevelReport(
  evidence: LevelEvidence,
  gray: Uint8Array,
): LevelReport {
  const { gray224: _gray, ...report } = evidence;
  if (!report.labelFound) {
    if (report.row !== null)
      throw new Error("未定位标签的液位证据包含测量行号");
    return { ...report, row: null, strength: 0, status: "未找到红标签" };
  }
  const [x, y, w, h] = report.bbox,
    [x0, y0, x1, y1] = report.crop;
  if (
    w < 12 ||
    h < 12 ||
    x + w > 416 ||
    y + h > 416 ||
    x1 - x0 < 32 ||
    y1 - y0 < 32 ||
    y < y0 ||
    y >= y1 ||
    Math.abs(report.labelTopRow - ((y - y0) * 224) / (y1 - y0)) > 1e-6 ||
    Math.abs(report.labelRows - (Math.min(w, h) * 224) / (y1 - y0)) > 1e-6
  )
    throw new Error("液位裁窗几何与测量坐标不一致");
  const measured = measureLevelGray(
    gray,
    report.labelTopRow,
    report.labelRows,
  );
  if (
    (measured.row === null) !== (report.row === null) ||
    (measured.row !== null && Math.abs(measured.row - report.row!) > 0.001) ||
    Math.abs(measured.strength - report.strength) > 0.001
  )
    throw new Error("液位测量值与归一化图像不一致");
  return { ...report, ...measured };
}
export function applyLevelDecision(
  decision: InspectionDecision,
  level: LevelReport,
  target: boolean,
) {
  if (decision.result === "ERROR") return;
  if (!level.labelFound || !target) {
    decision.result = "REVIEW";
    decision.reason = level.labelFound ? "未检出本产品" : "未找到红标签";
    return;
  }
  if (decision.result !== "PASS") return;
  if (level.row === null) {
    // Bottle present but no valid liquid line (cap/neck edge rejected, or the
    // surface hidden by the label): treat it as an underfilled bottle.
    decision.result = "FAIL";
    decision.reason = "液位过低：未测到液面";
    for (const finding of decision.findings)
      if (finding.classId === 0) finding.result = "FAIL";
    return;
  }
  // LEVEL-ROW-v1.3 two-sided band: good bottles measure 91.2~96.1,
  // underfilled ones 108.5~110.0.
  const failed = level.row < 85 || level.row > 102.9;
  decision.result = failed ? "FAIL" : "PASS";
  decision.reason = `${level.row < 85 ? "液位过高" : level.row > 102.9 ? "液位过低" : "液位合格"}：${level.row.toFixed(2)} 行，合格带 85.00–102.90`;
  if (failed)
    for (const finding of decision.findings)
      if (finding.classId === 0) finding.result = "FAIL";
}
