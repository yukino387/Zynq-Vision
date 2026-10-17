/** 状态到视觉色调的映射。标签在 display.ts，色调在这里——同一个值的两个展示属性。 */

/** quiet：正常，不需要注意力。ok：设备肯定地报告为正常。
 *  info：进行中。warn：需要人处理。crit：失败或下线。 */
export type Tone = "quiet" | "ok" | "info" | "warn" | "crit";

const tones: Record<string, Tone> = {
  // 合格是预期状态，在屏幕上占多数，必须安静——否则异常会被淹没。
  PASS: "quiet",
  COMPLETED: "quiet",
  REVIEWED: "quiet",
  SYNCED: "quiet",
  APPROVED: "quiet",
  FROZEN: "quiet",
  UNKNOWN: "quiet",
  CANCELLED: "quiet",
  SUPERSEDED: "quiet",
  DISABLED: "quiet",
  NONE: "quiet",
  COMPLETE: "quiet",
  CORRECT: "quiet",
  ACCEPTABLE: "quiet",

  ONLINE: "ok",
  READY: "ok",
  RUNNING: "ok",
  HEALTHY: "ok",
  VERIFIED: "ok",
  ACTIVE: "ok",
  SUCCESS: "ok",
  STABLE: "ok",
  OK: "ok",
  ENABLED: "ok",
  SYNC: "ok",

  // 过去这些和失败一起落进同一档，训练跑起来看起来像故障。
  QUEUED: "info",
  DOWNLOADING: "info",
  VERIFYING: "info",
  ACTIVATING: "info",
  SELF_TEST: "info",
  UPLOADING: "info",
  SYNCING: "info",
  CONNECTING: "info",
  BUSY: "info",
  UPDATING: "info",
  OPEN: "info",
  ROLLBACK: "info",

  REVIEW: "warn",
  PENDING: "warn",
  CANDIDATE: "warn",
  DRAFT: "warn",
  NEEDS_WORK: "warn",
  NEEDS_REVIEW: "warn",
  DESYNCED: "warn",
  STALE: "warn",
  "SLIGHT MOTION": "warn",
  "HOLD STEADY": "warn",
  LOW_CONFIDENCE: "warn",
  LIGHTING: "warn",
  OCCLUSION: "warn",
  OTHER: "warn",
  LOW_FPS: "warn",
  HIGH_LATENCY: "warn",
  QUEUE_OVERFLOW: "warn",

  FAIL: "crit",
  FAILED: "crit",
  ERROR: "crit",
  FAULT: "crit",
  OFFLINE: "crit",
  REJECTED: "crit",
  ROLLED_BACK: "crit",
  DEPLOYMENT_FAILED: "crit",
  NETWORK_LOST: "crit",
  DEVICE_TIMEOUT: "crit",
  INVALID_MODEL: "crit",
  CHECKSUM_ERROR: "crit",
  INFERENCE_ERROR: "crit",
  MISSED: "crit",
  FALSE_POSITIVE: "crit",
};

/** 未在表中出现的非空值给 warn：那是"我们还没有规则"，值得看一眼，
 *  与枚举里的 UNKNOWN（已知含义＝未上报，quiet）不同。 */
export function statusTone(value: unknown): Tone {
  if (value === null || value === undefined || value === "") return "quiet";
  if (typeof value === "boolean") return value ? "ok" : "quiet";
  return tones[String(value)] ?? "warn";
}
