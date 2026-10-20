import { z } from "zod";
import type { PlanRules } from "./plans.js";
import type { InspectionResult } from "./index.js";

export const acceptanceSchema = z
  .object({
    confidence: z.number().min(0.35).max(0.99).default(0.7),
    qualityGate: z.boolean().default(true),
  })
  .strict();
export type AcceptancePolicy = z.infer<typeof acceptanceSchema>;
export interface CheckFinding {
  classId: number;
  label: string;
  min: number;
  max: number;
  count: number;
  uncertain: number;
  result: InspectionResult;
}
export interface InspectionDecision {
  algorithm: "ACCEPTANCE_V1";
  result: InspectionResult;
  reason: string;
  findings: CheckFinding[];
  outsideRegion: number;
}
export interface BatchSnapshot {
  formatVersion: 1;
  planId: string;
  planName: string;
  planVersion: number;
  rules: PlanRules;
  acceptance: AcceptancePolicy;
  modelId: string;
  modelVersion: string;
  modelClasses: string[];
  modelPayloadSha256: string | null;
}
export interface InspectionBatch {
  id: string;
  name: string;
  deviceId: string;
  taskId: string;
  target: number;
  status: "OPEN" | "CLOSED";
  productionRunId: string | null;
  snapshot: BatchSnapshot;
  createdAt: string;
  closedAt: string | null;
  _count?: { inspections: number };
}
export interface BatchSummary {
  total: number;
  machine: Record<InspectionResult, number>;
  final: Record<InspectionResult, number>;
  resolved: number;
  pending: number;
  passRate: number | null;
}
