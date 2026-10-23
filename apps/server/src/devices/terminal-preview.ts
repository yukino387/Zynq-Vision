import type { Device } from "@prisma/client";
import sharp from "sharp";
import { decodeRgb565 } from "@vision/device-protocol";
import type { DetectionBox } from "@vision/contracts";
import { DomainError } from "../core/errors.js";
import { terminalRequest } from "./terminal-client.js";

export interface TerminalPreview {
  frameId: number;
  level?: import("@vision/contracts").LevelReport;
  postprocess?: import("@vision/contracts").PostprocessReport;
  planId?: string | null;
  planVersion?: number | null;
  receivedAt: string;
  width: number;
  height: number;
  jpeg: string;
  detections: DetectionBox[];
}

interface TerminalFrameMetadata {
  frameId: number;
  level?: import("@vision/contracts").LevelReport;
  postprocess?: import("@vision/contracts").PostprocessReport;
  planId?: string | null;
  planVersion?: number | null;
  fresh: boolean;
  boxes?: Omit<DetectionBox, "label">[];
  modelClasses?: string[];
}

export function parseTerminalFrame(binary: Buffer) {
  if (binary.length < 4)
    throw new DomainError("INVALID_FRAME", "设备画面不完整", 502);
  const length = binary.readUInt32LE(0);
  if (length > 65536 || binary.length !== 4 + length + 416 * 416 * 2)
    throw new DomainError("INVALID_FRAME", "设备画面格式异常", 502);
  const metadata = JSON.parse(
    binary.subarray(4, 4 + length).toString(),
  ) as TerminalFrameMetadata;
  return { metadata, raw: binary.subarray(4 + length) };
}

export async function readTerminalPreview(
  device: Device,
  after = 0,
): Promise<TerminalPreview | null> {
  const response = await terminalRequest(
    device,
    after > 0 ? `/preview?after=${after}` : "/preview",
    "",
    undefined,
    1500,
  );
  const binary = Buffer.from(await response.arrayBuffer());
  const { metadata, raw } = parseTerminalFrame(binary);
  if (metadata.frameId === after) return null;
  if (!metadata.fresh)
    throw new DomainError("DEVICE_TIMEOUT", "当前画面已过期", 409);
  const jpeg = await sharp(decodeRgb565(raw), {
    raw: { width: 416, height: 416, channels: 3 },
  })
    .jpeg({ quality: 80 })
    .toBuffer();
  return {
    frameId: metadata.frameId,
    level: metadata.level,
    postprocess: metadata.postprocess,
    planId: metadata.planId,
    planVersion: metadata.planVersion,
    receivedAt: new Date().toISOString(),
    width: 416,
    height: 416,
    jpeg: jpeg.toString("base64"),
    detections: (metadata.boxes ?? []).map((box) => ({
      ...box,
      label: metadata.modelClasses?.[box.classId] ?? `类别 ${box.classId + 1}`,
    })),
  };
}
