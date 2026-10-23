import { z } from "zod";

export const LEVEL_V3_PAYLOAD_SHA256 =
  "2e020a0317258420d952a5575df43977bfe003498e8eff734f25c2fcf6874994";
const rectangle = z.tuple([
  z.number().int().min(0).max(416),
  z.number().int().min(0).max(416),
  z.number().int().min(0).max(416),
  z.number().int().min(0).max(416),
]);
export const levelReportSchema = z
  .object({
    profile: z.literal("LEVEL_V3_20261022"),
    labelFound: z.boolean(),
    bbox: rectangle,
    crop: rectangle,
    labelTopRow: z.number().min(0).max(224),
    labelRows: z.number().min(0).max(224),
    row: z.number().min(0).max(223).nullable(),
    strength: z.number().min(0).max(255),
    status: z.string().max(80),
    band: z.tuple([z.literal(85), z.literal(102.9)]),
  })
  .strict();
export const levelEvidenceSchema = levelReportSchema.extend({
  gray224: z.string().length(66904),
});
export type LevelReport = z.infer<typeof levelReportSchema>;
export type LevelEvidence = z.infer<typeof levelEvidenceSchema>;
