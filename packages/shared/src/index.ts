import type {
  ConnectionState,
  DeviceState,
  ModelManifest,
  TerminalStatus,
} from "@vision/contracts";
export {
  defectClasses,
  chinese,
  displayName,
  reasonLabel,
  fieldLabel,
  errorMessage,
} from "./display.js";
export { statusTone, type Tone } from "./status.js";
export { evaluateInspection, assessInspectionImage } from "./acceptance.js";
/** Business classes occupy the first slots; the fixed hardware head has six slots. */
export function productClassesMatch(
  product: string[],
  model: string[],
): boolean {
  return (
    product.length > 0 &&
    product.length <= 6 &&
    model.length === 6 &&
    model.every((name, i) => name === (product[i] ?? `_unused_${i}`))
  );
}

export function terminalActivity(
  state: TerminalStatus["state"],
  online: boolean,
) {
  const blocked =
    !online || !state
      ? "设备未连接"
      : state.pendingRequestId
        ? "上次记录尚未确认，请先核对保存结果"
        : state.error
          ? `检测异常：${state.error}`
          : !state.model
            ? "未部署模型"
            : !state.product
              ? "未分配产品方案"
              : state.paused
                ? "检测服务已暂停"
                : !state.fresh
                  ? "等待有效图像"
                  : "";
  const phase = {
    STOPPED: "已停止自动检测",
    CLEARING: "请移走当前产品，等待空场景",
    WAITING: "自动检测 · 等待产品",
    INSPECTING: "正在检查 · 离开后自动保存",
    SAVING: "正在保存单件记录",
  };
  return {
    label: blocked || phase[state!.passagePhase],
    startBlocked: blocked,
    checkBlocked:
      blocked ||
      (state?.production ? "自动检测进行中，请先停止后再检查一件" : ""),
  };
}
export function connectionState(
  lastSeen: number | null,
  now: number,
  stale: number,
  offline: number,
): ConnectionState {
  return lastSeen === null || now - lastSeen > offline
    ? "OFFLINE"
    : now - lastSeen > stale
      ? "STALE"
      : "ONLINE";
}
export function syncState(
  desired: DeviceState,
  reported: DeviceState,
): "UNKNOWN" | "SYNCED" | "DESYNCED" {
  const keys = Object.keys(desired) as (keyof DeviceState)[];
  if (
    !keys.length ||
    keys.some((k) => reported[k] === undefined || reported[k] === null)
  )
    return "UNKNOWN";
  return keys.every((k) => desired[k] === reported[k]) ? "SYNCED" : "DESYNCED";
}
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object")
    return `{${Object.entries(value)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`)
      .join(",")}}`;
  return JSON.stringify(value) ?? "null";
}
export function compatibility(
  expected: ModelManifest,
  candidate: ModelManifest,
): string[] {
  const keys = [
    "networkTemplate",
    "firmwareInterfaceVersion",
    "preprocessProfile",
    "input",
    "output",
    "classCount",
    "classes",
    "quantization",
  ] as const;
  return keys.filter((k) => {
    if (k !== "quantization")
      return canonical(expected[k]) !== canonical(candidate[k]);
    const a = expected.quantization,
      b = candidate.quantization;
    // JSON storage may round a double by a few ULPs. Hardware scales still
    // must match to floating-point precision, not an application tolerance.
    const sameScale = (x: number, y: number) =>
      x === y ||
      Math.abs(x - y) <=
        4 * Number.EPSILON * Math.max(Math.abs(x), Math.abs(y));
    return (
      a.scheme !== b.scheme ||
      a.inputZeroPoint !== b.inputZeroPoint ||
      !sameScale(a.inputScale, b.inputScale) ||
      a.outputScales.length !== b.outputScales.length ||
      a.outputScales.some((scale, i) => !sameScale(scale, b.outputScales[i]!))
    );
  });
}
export function motionSummary(
  x: number,
  y: number,
  z: number,
  pitch: number | null,
  roll: number | null,
) {
  const motionScore = Math.sqrt(x * x + y * y + z * z);
  return {
    motionScore,
    pitch,
    roll,
    captureStability:
      motionScore < 0.1
        ? "STABLE"
        : motionScore < 0.5
          ? "SLIGHT MOTION"
          : "HOLD STEADY",
  };
}
