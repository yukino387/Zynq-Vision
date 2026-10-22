import { z } from "zod";
export {
  planRulesSchema,
  createPlanSchema,
  inspectionRegionSchema,
  planPurposeSchema,
} from "./plans.js";
export type { PlanRules, InspectionPlan, InspectionScenario } from "./plans.js";
export { acceptanceSchema } from "./inspection.js";
export type {
  AcceptancePolicy,
  CheckFinding,
  InspectionDecision,
  BatchSnapshot,
  InspectionBatch,
  BatchSummary,
} from "./inspection.js";
export const roles = ["ADMIN", "ENGINEER", "OPERATOR"] as const;
export type Role = (typeof roles)[number];
export const sources = ["BOARD", "MOBILE", "IMPORT", "SIMULATION"] as const;
export type Source = (typeof sources)[number];
export type ConnectionState = "OFFLINE" | "CONNECTING" | "ONLINE" | "STALE";
export type RuntimeState =
  "UNKNOWN" | "READY" | "RUNNING" | "BUSY" | "UPDATING" | "FAULT";
export type InspectionResult = "PASS" | "FAIL" | "REVIEW" | "ERROR";
export interface Capabilities {
  capture: boolean;
  preview: boolean;
  inference: boolean;
  modelUpdate: boolean;
  firmwareUpdate: boolean;
  localStorage: boolean;
  offlineInference: boolean;
  offlineSync: boolean;
  modelVersion: boolean;
  planUpdate: boolean;
  restartInference: boolean;
}
/** 板端 running_slot/active_slot 等槽位：0=A、1=B、2=golden、0xFFFFFFFF=无。 */
export interface FirmwareInfo {
  supported: boolean;
  version: string;
  sha256: string;
  generation: number;
  flags: number;
  runningSlot: number;
  activeSlot: number;
  previousSlot: number;
  pendingSlot: number;
  attempts: number;
  maxAttempts: number;
  stage: number;
  /** [slot A, slot B] 包长度；未使用的槽为 0。 */
  slotImageSize: [number, number];
}
/** 板端 SD 模型库里的一个条目。板子自己维护这份清单，平台只读。 */
export interface ResidentModel {
  /** SD 槽位号，切换和删除都按它定位。 */
  index: number;
  version: string;
  /** 权重载荷摘要，对应制品包 88..120 偏移处那 32 字节。 */
  sha256: string;
  generation: number;
  active: boolean;
  previous: boolean;
}
export interface DeviceState {
  modelVersion?: string | null;
  planVersion?: string | null;
  inspectionEnabled?: boolean;
  cameraOnly?: boolean;
  modelPayloadSha256?: string | null;
  /** SD 模型库；capabilities.localStorage 为真时才有意义。 */
  models?: ResidentModel[] | null;
  firmwareVersion?: string | null;
  /** PS 应用 OTA 现场状态；老固件不上报。 */
  firmware?: FirmwareInfo | null;
}
export interface Telemetry {
  frameId: number;
  receivedAt: string;
  timestamp: string | null;
  captureUs: number;
  conversionUs: number;
  inferenceUs: number;
  transferUs: number;
  cycleUs: number;
  fps: number | null;
  errorCode: number;
  brightness: number;
  layerTiming: null | number[];
}
export interface DetectionBox {
  classId: number;
  label: string;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  trackId?: number;
  trackConfirmed?: boolean;
}
export interface TerminalModel {
  id: string;
  version: string;
  payloadSha256: string;
  weightsSha256: string;
  classes: string[];
  installedAt?: string;
}
export interface TerminalProduct {
  id: string;
  name: string;
  version: number;
  product?: string;
  instructions?: string;
  purpose?: import("./plans.js").PlanRules["purpose"];
  postprocess?: import("./postprocess.js").PostprocessPolicy;
  region?: import("./plans.js").PlanRules["region"];
  checks?: Array<
    import("./plans.js").PlanRules["checks"][number] & { label: string }
  >;
  acceptance: { confidence: number; qualityGate: boolean };
  assignedAt?: string;
}
export type PassagePhase =
  "STOPPED" | "CLEARING" | "WAITING" | "INSPECTING" | "SAVING";
export interface TerminalTiming {
  frameId: number;
  captureMs: number;
  prepareMs: number;
  convMs: number;
  forwardMs: number;
  postMs: number;
  extractMs: number;
}
export interface TerminalRunCounts {
  PASS: number;
  FAIL: number;
  REVIEW: number;
  ERROR: number;
}
export interface TerminalStatus {
  bound: boolean;
  online: boolean;
  lastSeenAt: string | null;
  state: null | {
    bootId: string;
    uptime: number;
    model: TerminalModel | null;
    product: TerminalProduct | null;
    total: number;
    counts: TerminalRunCounts;
    runTotal: number;
    runCounts: TerminalRunCounts;
    production: boolean;
    productionRunId: string | null;
    passagePhase: PassagePhase;
    fps?: number | null;
    timing?: TerminalTiming | null;
    paused: boolean;
    fresh: boolean;
    pendingSync: number;
    pendingRequestId: string | null;
    last: null | {
      sequence: number;
      result: InspectionResult;
      bootId?: string;
      productionRunId?: string | null;
      reason?: string;
      findings?: import("./inspection.js").CheckFinding[];
    };
    error: string;
    syncError: string;
    cpuPercent: number | null;
    memoryUsed: number;
    memoryTotal: number;
    receivedAt: string;
  };
}
export interface DeviceSnapshot {
  executionMode: "LINUX_TERMINAL" | "SIMULATOR";
  terminal: TerminalStatus | null;
  id: string;
  name: string;
  type: string;
  connectionState: ConnectionState;
  runtimeState: RuntimeState;
  source: Source;
  capabilities: Capabilities;
  desiredState: DeviceState;
  reportedState: DeviceState;
  syncState: "SYNCED" | "DESYNCED" | "UNKNOWN";
  telemetry: Telemetry | null;
  lastSeenAt: string | null;
  firmwareVersion: string | null;
  protocolVersion: string | null;
  error: string | null;
}
export interface PlatformEvent<T = unknown> {
  type: string;
  requestId: string;
  timestamp: string;
  entityId: string;
  version: 1;
  payload: T;
  source: Source | "SERVER";
  sequence: number;
  schemaVersion: 1;
}
export interface ApiError {
  code: string;
  message: string;
  requestId: string;
  details: unknown;
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
export const manifestSchema = z
  .object({
    formatVersion: z.literal(1),
    networkTemplate: z.string().min(1),
    firmwareInterfaceVersion: z.string().min(1),
    preprocessProfile: z.string().min(1),
    input: z
      .object({
        width: z.number().int().positive(),
        height: z.number().int().positive(),
        channels: z.number().int().positive(),
        dtype: z.enum(["INT8", "FLOAT32"]),
      })
      .strict(),
    output: z.array(z.array(z.number().int().positive())),
    classCount: z.number().int().positive(),
    classes: z.array(z.string().min(1)),
    quantization: z
      .object({
        scheme: z.string(),
        inputScale: z.number().positive(),
        inputZeroPoint: z.number().int(),
        outputScales: z.array(z.number().positive()),
      })
      .strict(),
    weights: z
      .object({
        sha256: z.string().regex(/^[a-f0-9]{64}$/),
        size: z.number().int().positive(),
      })
      .strict(),
  })
  .strict()
  .superRefine((v, c) => {
    if (v.classes.length !== v.classCount)
      c.addIssue({ code: "custom", message: "classCount must match classes" });
  });
export type ModelManifest = z.infer<typeof manifestSchema>;
export const trainingOptionsSchema = z
  .object({
    colorMode: z.enum(["GRAY", "RGB"]).default("GRAY"),
    epochs: z.number().int().min(1).max(1000).default(50),
    batchSize: z.number().int().min(1).max(32).default(32),
    learningRate: z.number().min(0.000001).max(0.1).default(0.001),
    seed: z.number().int().min(0).max(2147483647).default(7020),
    device: z.enum(["cpu", "cuda"]).default("cuda"),
    amp: z.boolean().default(true),
    workers: z.number().int().min(0).max(8).default(4),
  })
  .strict();
export type TrainingOptions = z.infer<typeof trainingOptionsSchema>;
export const boxSchema = z
  .object({
    classId: z.number().int().min(0),
    label: z.string().min(1),
    confidence: z.number().min(0).max(1),
    x1: z.number().min(0),
    y1: z.number().min(0),
    x2: z.number().positive(),
    y2: z.number().positive(),
  })
  .strict()
  .refine((b) => b.x2 > b.x1 && b.y2 > b.y1, "Invalid bounding box");
export const listSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(30),
  // 排序字段由各路由的白名单校验（见 apps/server/src/core/list.ts 的 listing()）。
  // 这里不再用枚举：枚举会把白名单里合法的字段（如 result、source）挡掉，
  // 让"点表头排序"变成 400。
  sort: z.string().default("createdAt"),
  order: z.enum(["asc", "desc"]).default("desc"),
  search: z.string().max(200).optional(),
  status: z.string().optional(),
  source: z.enum(sources).optional(),
  from: z.string().datetime().optional(),
  to: z.string().datetime().optional(),
  deviceId: z.string().optional(),
  taskId: z.string().optional(),
  planId: z.string().optional(),
  batchId: z.string().optional(),
  stationId: z.string().optional(),
  result: z.enum(["PASS", "FAIL", "REVIEW", "ERROR"]).optional(),
  reviewed: z.enum(["true", "false"]).optional(),
  realOnly: z.enum(["true", "false"]).optional(),
  annotation: z.enum(["pending", "complete"]).optional(),
  qualityStatus: z.enum(["PASS", "WARNING"]).optional(),
});

export type {
  Asset,
  Annotation,
  Sample,
  Inspection,
  Named,
  Task,
  Dataset,
  Model,
  Deployment,
  Firmware,
  FirmwareDeployment,
  FirmwareSegment,
} from "./entities.js";
export {
  postprocessSchema,
  type PostprocessPolicy,
  type PostprocessReport,
} from "./postprocess.js";
export { mqttConfigSchema, type MqttConfig } from "./mqtt.js";
