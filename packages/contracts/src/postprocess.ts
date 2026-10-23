import { z } from "zod";

export const postprocessSchema = z
  .object({
    algorithm: z
      .enum(["BOX_FILTER_V2", "BOX_FILTER_V3"])
      .default("BOX_FILTER_V3"),
    nmsIou: z.number().min(0.05).max(0.95).default(0.45),
    containment: z.number().min(0.5).max(1).default(0.9),
    // Candidate score floor before NMS/merge. The caps package requires 0.65
    // so white caps (0.45~0.62) never enter the count.
    minScore: z.number().min(0.35).max(0.99).default(0.35),
    minArea: z.number().min(0).max(0.1).default(0.00002),
    maxDetections: z.number().int().min(1).max(300).default(100),
    // Same-class boxes whose centers are closer than this (224-px units) are
    // one object reported by two anchors; keep the higher score.
    mergeDistance: z.number().min(0).max(80).default(0),
    trackIou: z.number().min(0.05).max(0.95).default(0.3),
    trackMinHits: z.number().int().min(1).max(10).default(2),
    trackMaxMisses: z.number().int().min(0).max(30).default(3),
    trackMaxGapMs: z.number().int().min(100).max(5000).default(1000),
  })
  .strict();

export type PostprocessPolicy = z.infer<typeof postprocessSchema>;
export interface PostprocessReport {
  policy: PostprocessPolicy;
  candidates: number;
  invalid: number;
  tiny: number;
  nested: number;
  suppressed: number;
  overflow: boolean;
}
