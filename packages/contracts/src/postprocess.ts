import { z } from "zod";

export const postprocessSchema = z
  .object({
    algorithm: z
      .enum(["BOX_FILTER_V2", "BOX_FILTER_V3"])
      .default("BOX_FILTER_V3"),
    nmsIou: z.number().min(0.05).max(0.95).default(0.45),
    containment: z.number().min(0.5).max(1).default(0.9),
    minArea: z.number().min(0).max(0.1).default(0.00002),
    maxDetections: z.number().int().min(1).max(300).default(100),
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
