import type {
  AcceptancePolicy,
  DetectionBox,
  InspectionDecision,
  PlanRules,
} from "@vision/contracts";

export function assessInspectionImage(raw: Uint8Array) {
  if (raw.length !== 416 * 416 * 2)
    throw new Error("RGB565 evidence size mismatch");
  const luma = (x: number, y: number) => {
    const i = 2 * (y * 416 + x),
      p = raw[i]! | (raw[i + 1]! << 8),
      r = p >> 11,
      g = (p >> 5) & 63,
      b = p & 31;
    return (
      (19595 * ((r << 3) | (r >> 2)) +
        38470 * ((g << 2) | (g >> 4)) +
        7471 * ((b << 3) | (b >> 2)) +
        32768) >>
      16
    );
  };
  let mean = 0,
    lap = 0,
    squares = 0,
    n = 0;
  for (let y = 4; y < 412; y += 4)
    for (let x = 4; x < 412; x += 4) {
      const v = luma(x, y),
        d =
          4 * v -
          luma(x - 4, y) -
          luma(x + 4, y) -
          luma(x, y - 4) -
          luma(x, y + 4);
      mean += v;
      lap += d;
      squares += d * d;
      n++;
    }
  const brightness = mean / n,
    sharpness = squares / n - (lap / n) ** 2;
  return {
    status:
      brightness >= 30 && brightness <= 230 && sharpness >= 20
        ? "PASS"
        : "WARNING",
    metrics: { brightness, sharpness, algorithm: "RGB565_GRID4_LAPLACIAN_V1" },
  };
}

/** Coordinates are original-image pixels; ROI membership uses the box centre. */
export function evaluateInspection(input: {
  rules: PlanRules;
  acceptance: AcceptancePolicy;
  detections: DetectionBox[] | null;
  width: number;
  height: number;
  quality: string;
  errorCode?: number;
}): InspectionDecision {
  const { rules, acceptance, detections, width, height } = input;
  const decision: InspectionDecision = {
    algorithm: "ACCEPTANCE_V1",
    result: "REVIEW",
    reason: "",
    findings: [],
    outsideRegion: 0,
  };
  const finish = (result: InspectionDecision["result"], reason: string) => ({
    ...decision,
    result,
    reason,
  });
  if (input.errorCode)
    return finish("ERROR", `设备执行错误：${input.errorCode}`);
  if (
    !Number.isFinite(width) ||
    !Number.isFinite(height) ||
    width <= 0 ||
    height <= 0
  )
    return finish("ERROR", "图像尺寸无效");
  if (detections === null)
    return finish("REVIEW", "本次没有有效推理输出，请重新检查");
  if (acceptance.qualityGate && input.quality !== "PASS")
    return finish("REVIEW", "图像质量未通过检查，请调整光照或摆放后重新检查");
  if (
    rules.checks.length !== rules.classes.length ||
    rules.classes.some((_, id) => !rules.checks.some((c) => c.classId === id))
  )
    return finish("REVIEW", "方案尚未为每个类别配置数量要求");
  const counts = rules.classes.map(() => ({ count: 0, uncertain: 0 }));
  let unexpected = false,
    unexpectedUncertain = false;
  for (const box of detections) {
    if (
      ![box.x1, box.y1, box.x2, box.y2, box.confidence, box.classId].every(
        Number.isFinite,
      ) ||
      box.x1 < 0 ||
      box.y1 < 0 ||
      box.x2 > width ||
      box.y2 > height ||
      box.x2 <= box.x1 ||
      box.y2 <= box.y1 ||
      box.confidence < 0 ||
      box.confidence > 1 ||
      !Number.isInteger(box.classId) ||
      box.classId < 0
    )
      return finish("ERROR", "检测框或置信度数据无效");
    const x = (box.x1 + box.x2) / (2 * width),
      y = (box.y1 + box.y2) / (2 * height),
      r = rules.region;
    if (x < r.x || y < r.y || x > r.x + r.width || y > r.y + r.height) {
      decision.outsideRegion++;
      continue;
    }
    if (box.confidence < 0.35) continue;
    const count = counts[box.classId];
    if (!count) {
      if (box.confidence >= acceptance.confidence) unexpected = true;
      else unexpectedUncertain = true;
    } else if (box.confidence >= acceptance.confidence) count.count++;
    else count.uncertain++;
  }
  decision.findings = rules.checks.map((check) => {
    const { count, uncertain } = counts[check.classId]!;
    const result =
      count > check.max || count + uncertain < check.min
        ? "FAIL"
        : count < check.min || count + uncertain > check.max
          ? "REVIEW"
          : "PASS";
    return {
      ...check,
      label: rules.classes[check.classId]!,
      count,
      uncertain,
      result,
    };
  });
  if (unexpected) return finish("FAIL", "检查区域内出现方案以外的类别");
  const failed = decision.findings.filter((f) => f.result === "FAIL");
  if (failed.length)
    return finish(
      "FAIL",
      failed
        .map(
          (f) =>
            `${f.label}：确认 ${f.count} 个${f.uncertain ? `，待确认 ${f.uncertain} 个` : ""}，要求 ${f.min === f.max ? f.min : `${f.min}–${f.max}`} 个`,
        )
        .join("；"),
    );
  if (
    unexpectedUncertain ||
    decision.findings.some((f) => f.result === "REVIEW")
  )
    return finish("REVIEW", "存在影响数量判断的低置信度目标，请人工复核");
  return finish("PASS", "检查区域内的类别和数量均符合当前批次方案");
}
