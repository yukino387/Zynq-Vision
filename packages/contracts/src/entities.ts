import type { DetectionBox, Source } from "./index.js";
import type { InspectionPlan } from "./plans.js";
export interface Asset {
  id: string;
  kind: string;
  mimeType: string;
  sha256: string;
  width: number | null;
  height: number | null;
  size: number;
}
export interface Annotation {
  id: string;
  version: number;
  status: string;
  boxes: DetectionBox[];
}
export interface Sample {
  plan?: InspectionPlan | null;
  task?: { plan: InspectionPlan | null } | null;
  id: string;
  name: string;
  source: Source;
  status: string;
  hard: boolean;
  createdAt: string;
  assets: Asset[];
  annotations: Annotation[];
  quality?: { status: string; metrics: Record<string, unknown> };
  metadata: Record<string, unknown>;
}
export interface Inspection {
  id: string;
  sampleId: string;
  batchId?: string | null;
  metadata?: {
    localResult?: import("./index.js").InspectionResult;
    manual?: boolean;
    productionRunId?: string;
    decision?: import("./inspection.js").InspectionDecision;
    snapshot?: import("./inspection.js").BatchSnapshot;
  };
  deviceId: string | null;
  source: Source;
  modelVersion: string | null;
  planVersion: string | null;
  firmwareVersion: string | null;
  result: string;
  reviewResult?: "PASS" | "FAIL" | "REVIEW" | null;
  reason: string;
  frameId: number | null;
  confidence: number | null;
  latency: number | null;
  createdAt: string;
  detections: DetectionBox[];
  sample: Sample;
  reviews: {
    verdict: string;
    note: string;
    finalResult?: "PASS" | "FAIL" | "REVIEW" | null;
    createdAt?: string;
  }[];
}
export interface Named {
  id: string;
  name: string;
  status?: string;
  version?: string | number;
  source?: Source;
  createdAt: string;
  [key: string]: unknown;
}
export interface Task extends Named {
  planId?: string | null;
  plan?: InspectionPlan | null;
  stationId: string | null;
  target: number;
  _count: { samples: number };
}
export interface Dataset extends Named {
  status: "DRAFT" | "READY" | "FROZEN";
  version: number;
  checksum: string | null;
  _count: { items: number };
}
export interface Model extends Named {
  version: string;
  status: string;
  manifest: Record<string, unknown>;
  benchmarks: unknown[];
}
export interface Deployment extends Named {
  deviceId: string;
  modelId: string;
  status: string;
  progress: number;
  previousVersion: string | null;
  error: string | null;
  /** 部署收据。resident=true 表示制品已经在设备 SD 卡上，这次没传字节，只做了切换。 */
  receipt: { resident?: boolean } | null;
  model: Model;
}
export interface FirmwareSegment {
  paddr: number;
  offset: number;
  size: number;
}
export interface Firmware extends Named {
  version: string;
  sha256: string;
  size: number;
  imageSize: number;
  entry: number;
  segments: FirmwareSegment[];
  status: string;
  notes: string | null;
  asset?: Asset;
}
export interface FirmwareDeployment {
  id: string;
  deviceId: string;
  firmwareId: string;
  previousVersion: string | null;
  previousSha256: string | null;
  previousSlot: number | null;
  status: string;
  progress: number;
  error: string | null;
  receipt: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  firmware: Firmware;
  device?: { id: string; name: string };
}
