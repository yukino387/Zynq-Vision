export const WIRE = {
  frameMagic: 0x314f4c59,
  statusMagic: 0x31545343,
  commandMagic: 0x31434e43,
  device: 0x7020,
  fragment: 1400,
  width: 416,
  height: 416,
  sizes: [1617, 6468, 346112],
} as const;
export interface WireStatus {
  request: number;
  flags: number;
  frame: number;
  captureUs: number;
  conversionUs: number;
  inferenceUs: number;
  transferUs: number;
  cycleUs: number;
  errorCode: number;
  brightness: number;
}
export function readStatus(packet: Buffer): WireStatus | null {
  if (
    packet.length !== 48 ||
    packet.readUInt32LE(0) !== WIRE.statusMagic ||
    packet.readUInt32LE(8) !== WIRE.device
  )
    return null;
  return {
    request: packet.readUInt32LE(4),
    flags: packet.readUInt32LE(12),
    frame: packet.readUInt32LE(16),
    captureUs: packet.readUInt32LE(20),
    conversionUs: packet.readUInt32LE(24),
    inferenceUs: packet.readUInt32LE(28),
    transferUs: packet.readUInt32LE(32),
    cycleUs: packet.readUInt32LE(36),
    errorCode: packet.readUInt32LE(40),
    brightness: packet.readInt32LE(44),
  };
}
export function commandPacket(
  request: number,
  command: number,
  value = 0,
): Buffer {
  const b = Buffer.alloc(16);
  b.writeUInt32LE(WIRE.commandMagic);
  b.writeUInt32LE(request >>> 0, 4);
  b.writeUInt32LE(command, 8);
  b.writeInt32LE(value, 12);
  return b;
}
/** 板端 SD 模型库协议（camera/int8/model_store.cpp）。op0–5 是原双槽语义，op7–9 是模型库新增的。 */
export const MODEL = {
  magic: 0x314c444d,
  replyMagic: 0x3152444d,
  replySize: 124,
  packet: 1400,
  size: 6416360,
  /** 槽位编号从 0 起，板端用 op0 的 total 报容量，所以这里不写死容量。 */
  noSlot: 0xffffffff,
  ops: {
    INFO: 0,
    BEGIN: 1,
    DATA: 2,
    FINISH: 3,
    COMMIT: 4,
    ROLLBACK: 5,
    ABORT: 6,
    LIST: 7,
    SELECT: 8,
    DELETE: 9,
  },
  result: {
    OK: 0,
    INVALID: 1,
    BUSY: 2,
    STORAGE: 3,
    REJECTED: 4,
    FULL: 5,
    NOT_FOUND: 6,
    UNUSABLE: 7,
    PROTECTED: 8,
  },
  flags: {
    MOUNTED: 1,
    AVAILABLE: 2,
    STAGED: 4,
    READY: 8,
    BUSY: 16,
    ENTRY_ACTIVE: 32,
    ENTRY_PREVIOUS: 64,
  },
} as const;
export interface WireModelReply {
  request: number;
  result: number;
  /** op0 是当前激活槽号（noSlot 表示没有），op7 是被查询的槽号，其余是已接收字节数。 */
  received: number;
  /** op0 是库容量，op7 是库内条目数，其余是制品总字节数。 */
  total: number;
  generation: number;
  flags: number;
  version: string;
  sha256: string;
}
export function modelPacket(
  request: number,
  operation: number,
  offset = 0,
  data: Buffer = Buffer.alloc(0),
): Buffer {
  const b = Buffer.alloc(20 + data.length);
  b.writeUInt32LE(MODEL.magic);
  b.writeUInt32LE(request >>> 0, 4);
  b.writeUInt32LE(operation, 8);
  b.writeUInt32LE(offset >>> 0, 12);
  b.writeUInt32LE(data.length, 16);
  data.copy(b, 20);
  return b;
}
export function readModelReply(packet: Buffer): WireModelReply | null {
  if (
    packet.length !== MODEL.replySize ||
    packet.readUInt32LE(0) !== MODEL.replyMagic
  )
    return null;
  return {
    request: packet.readUInt32LE(4),
    result: packet.readUInt32LE(8),
    received: packet.readUInt32LE(12),
    total: packet.readUInt32LE(16),
    generation: packet.readUInt32LE(20),
    flags: packet.readUInt32LE(24),
    version: packet.subarray(28, 92).toString("ascii").split("\0")[0]!,
    sha256: packet.subarray(92, 124).toString("hex"),
  };
}
interface Partial {
  streams: Map<number, { data: Buffer; offsets: Set<number> }>;
  created: number;
}
export interface WireFrame {
  frameId: number;
  raw: Buffer;
  out0: Buffer | null;
  out1: Buffer | null;
  receivedAt: string;
}
export class FrameAssembler {
  private frames = new Map<number, Partial>();
  private completed = new Map<number, number>();
  rejected = 0;
  push(
    packet: Buffer,
    previewOnly = false,
    now = Date.now(),
  ): WireFrame | null {
    for (const [id, f] of this.frames)
      if (now - f.created > 2000) this.frames.delete(id);
    for (const [id, t] of this.completed)
      if (now - t > 2000) this.completed.delete(id);
    if (packet.length <= 20 || packet.readUInt32LE(0) !== WIRE.frameMagic) {
      this.rejected++;
      return null;
    }
    const frameId = packet.readUInt32LE(4),
      kind = packet.readUInt32LE(8),
      length = packet.readUInt32LE(12),
      offset = packet.readUInt32LE(16),
      expected = WIRE.sizes[kind];
    if (
      expected === undefined ||
      length !== expected ||
      offset >= length ||
      offset % WIRE.fragment !== 0 ||
      packet.length - 20 !== Math.min(WIRE.fragment, length - offset)
    ) {
      this.rejected++;
      return null;
    }
    if (this.completed.has(frameId)) return null;
    let frame = this.frames.get(frameId);
    if (!frame) {
      frame = { streams: new Map(), created: now };
      this.frames.set(frameId, frame);
      while (this.frames.size > 3)
        this.frames.delete(this.frames.keys().next().value!);
    }
    let stream = frame.streams.get(kind);
    if (!stream) {
      stream = { data: Buffer.alloc(expected), offsets: new Set() };
      frame.streams.set(kind, stream);
    }
    if (
      stream.offsets.has(offset) &&
      !stream.data
        .subarray(offset, offset + packet.length - 20)
        .equals(packet.subarray(20))
    ) {
      this.frames.delete(frameId);
      this.rejected++;
      return null;
    }
    packet.copy(stream.data, offset, 20);
    stream.offsets.add(offset);
    if (
      !(previewOnly ? [2] : [0, 1, 2]).every((k) => {
        const s = frame!.streams.get(k);
        return s && s.offsets.size === Math.ceil(s.data.length / WIRE.fragment);
      })
    )
      return null;
    this.frames.delete(frameId);
    this.completed.set(frameId, now);
    return {
      frameId,
      raw: frame.streams.get(2)!.data,
      out0: frame.streams.get(0)?.data ?? null,
      out1: frame.streams.get(1)?.data ?? null,
      receivedAt: new Date(now).toISOString(),
    };
  }
  clear() {
    this.frames.clear();
    this.completed.clear();
  }
}
export function decodeRgb565(raw: Buffer): Buffer {
  if (raw.length !== WIRE.sizes[2]) throw new Error("RGB565 length mismatch");
  const rgb = Buffer.alloc(WIRE.width * WIRE.height * 3);
  for (let i = 0; i < raw.length / 2; i++) {
    const p = raw.readUInt16LE(i * 2),
      r = p >>> 11,
      g = (p >>> 5) & 63,
      b = p & 31;
    rgb[i * 3] = (r << 3) | (r >>> 2);
    rgb[i * 3 + 1] = (g << 2) | (g >>> 4);
    rgb[i * 3 + 2] = (b << 3) | (b >>> 2);
  }
  return rgb;
}
