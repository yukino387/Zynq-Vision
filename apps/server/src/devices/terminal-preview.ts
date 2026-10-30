import type { Device } from "@prisma/client";
import sharp from "sharp";
import { decodeRgb565 } from "@vision/device-protocol";
import type { DetectionBox } from "@vision/contracts";
import { DomainError } from "../core/errors.js";
import { terminalPreviewStream } from "./terminal-client.js";

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
  capturedMonotonicNs: string;
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

export async function* readPreviewPackets(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  let pending: Buffer = Buffer.alloc(0);
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) throw new DomainError("UNAVAILABLE", "设备预览流已断开", 503);
      pending = pending.length
        ? Buffer.concat([pending, value])
        : Buffer.from(value);
      while (pending.length >= 8) {
        const size = pending.readUInt32LE(0);
        const bufferMs = pending.readUInt32LE(4);
        if (size < 4 || size > 4 + 65536 + 416 * 416 * 2)
          throw new DomainError("INVALID_FRAME", "设备预览流长度无效", 502);
        if (pending.length < 8 + size) break;
        const binary = pending.subarray(8, 8 + size);
        pending = pending.subarray(8 + size);
        yield { binary, bufferMs };
      }
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      /* Already aborted. */
    }
    reader.releaseLock();
  }
}

export async function* readTerminalPreviewStream(
  device: Device,
  signal: AbortSignal,
) {
  const body = await terminalPreviewStream(device, signal);
  for await (const { binary, bufferMs } of readPreviewPackets(body)) {
    const { metadata, raw } = parseTerminalFrame(binary);
    if (!metadata.fresh || bufferMs > 1000)
      throw new DomainError("DEVICE_TIMEOUT", "当前画面已过期", 409);
    if (!/^\d{1,20}$/.test(metadata.capturedMonotonicNs ?? ""))
      throw new DomainError("INVALID_FRAME", "设备画面缺少采集时间", 502);
    const image = sharp(decodeRgb565(raw), {
      raw: { width: 416, height: 416, channels: 3 },
    });
    const jpeg = await image.jpeg({ quality: 80 }).toBuffer();
    const frame: TerminalPreview = {
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
        label:
          metadata.modelClasses?.[box.classId] ?? `类别 ${box.classId + 1}`,
      })),
    };
    yield { frame, capturedNs: BigInt(metadata.capturedMonotonicNs) };
  }
}
