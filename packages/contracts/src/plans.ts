import { z } from "zod";
import { postprocessSchema } from "./postprocess.js";
export const planPurposeSchema = z.enum([
  "PRESENCE",
  "COUNT",
  "APPEARANCE",
  "POSITION",
]);

export const inspectionRegionSchema = z
  .object({
    x: z.number().min(0).max(1),
    y: z.number().min(0).max(1),
    width: z.number().positive().max(1),
    height: z.number().positive().max(1),
  })
  .strict()
  .refine(
    (r) => r.x + r.width <= 1.000001 && r.y + r.height <= 1.000001,
    "检查区域不能超出画面",
  );

export const planRulesSchema = z
  .object({
    product: z.string().trim().min(1).max(120),
    purpose: planPurposeSchema,
    postprocess: postprocessSchema.optional(),
    classes: z
      .array(z.string().trim().min(1).max(40))
      .min(1)
      .max(6)
      .refine(
        (values) => new Set(values).size === values.length,
        "类别名称不能重复",
      ),
    instructions: z.string().trim().min(1).max(2000),
    conditions: z.string().trim().max(1000).default(""),
    referenceUrl: z
      .string()
      .url()
      .max(2000)
      .or(z.literal(""))
      .default("")
      .refine(
        (value) => !value || /^https?:\/\//i.test(value),
        "参考图片使用 HTTP 或 HTTPS 地址",
      ),
    coordinateSpace: z.literal("NORMALIZED_FRAME"),
    region: inspectionRegionSchema,
    checks: z
      .array(
        z
          .object({
            classId: z.number().int().min(0).max(5),
            min: z.number().int().min(0).max(100),
            max: z.number().int().min(0).max(100),
            region: inspectionRegionSchema.optional(),
          })
          .strict()
          .refine((r) => r.max >= r.min, "最大数量不能小于最小数量"),
      )
      .min(1)
      .max(6),
  })
  .strict()
  .superRefine((rules, context) => {
    if (
      rules.checks.some((check) => check.classId >= rules.classes.length) ||
      new Set(rules.checks.map((check) => check.classId)).size !==
        rules.checks.length
    )
      context.addIssue({
        code: "custom",
        path: ["checks"],
        message: "请选择方案中的类别，每类仅设置一条规则",
      });
  });
export const createPlanSchema = z
  .object({
    name: z.string().trim().min(1).max(120),
    rules: planRulesSchema,
  })
  .strict();
export type PlanRules = z.infer<typeof planRulesSchema>;
export interface InspectionScenario {
  id: string;
  name: string;
  description: string;
  rules: PlanRules;
}
export interface InspectionPlan {
  id: string;
  name: string;
  version: number;
  rules: PlanRules;
  createdAt: string;
}
