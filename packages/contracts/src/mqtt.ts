import { z } from "zod";
const topic = z
  .string()
  .min(1)
  .max(200)
  .refine((v) => !/[+#\x00]/.test(v), "Topic 不允许通配符");
export const mqttConfigSchema = z
  .object({
    enabled: z.boolean().default(false),
    host: z.string().max(200).default(""),
    port: z.number().int().min(1).max(65535).default(1883),
    tls: z.boolean().default(false),
    username: z.string().max(128).default(""),
    password: z.string().max(256).optional(),
    clientId: z.string().min(1).max(100).default("vision-terminal"),
    prefix: topic.default("vision/terminal"),
    topics: z
      .object({
        command: topic.optional(),
        reply: topic.optional(),
        state: topic.optional(),
        result: topic.optional(),
        event: topic.optional(),
        availability: topic.optional(),
        capabilities: topic.optional(),
      })
      .strict()
      .default({}),
    input: z
      .object({
        commandField: z.string().min(1).max(100).default("type"),
        requestIdField: z.string().min(1).max(100).default("requestId"),
        pieceIdField: z.string().min(1).max(100).default("pieceId"),
        aliases: z
          .record(
            z.enum([
              "TRIGGER",
              "START",
              "STOP",
              "GET_STATUS",
              "GET_RESULT",
              "ACK_RESULT",
            ]),
          )
          .default({}),
      })
      .strict()
      .default({}),
    rules: z
      .array(
        z
          .object({
            id: z.string().min(1).max(64),
            when: z.enum(["PASS", "FAIL", "REVIEW", "ERROR"]),
            topic,
            payload: z.record(z.unknown()),
            ackTopic: topic.optional(),
            ackIdField: z.string().default("actionId"),
            ackStatusField: z.string().default("status"),
            ackSuccessValue: z.string().default("EXECUTED"),
            timeoutMs: z.number().int().min(100).max(30000).default(2000),
            expiryMs: z.number().int().min(100).max(30000).default(2000),
          })
          .strict(),
      )
      .max(8)
      .default([]),
  })
  .strict()
  .refine((v) => !v.enabled || !!v.host.trim(), "请填写 Broker 地址")
  .refine(
    (v) => new Set(v.rules.map((r) => r.id)).size === v.rules.length,
    "规则 ID 不能重复",
  );
export type MqttConfig = z.infer<typeof mqttConfigSchema>;
