import dgram from "node:dgram";
import { createHash } from "node:crypto";
import sharp from "sharp";
import {
  FrameAssembler,
  commandPacket,
  readStatus,
  decodeRgb565,
  detect,
  MODEL,
  modelPacket,
  readModelReply,
  type WireModelReply,
} from "@vision/device-protocol";
import type {
  Capabilities,
  ModelManifest,
  DeviceState,
  ResidentModel,
} from "@vision/contracts";
import { DomainError } from "../core/errors.js";
import { validateZynqPackage } from "../models/zynq-profile.js";
import {
  baseCapabilities,
  type DeviceTransport,
  type CapturedFrame,
  type Sink,
  type TransportStatus,
  type DeploymentReceipt,
} from "./transport.js";
export class ZynqUdpTransport implements DeviceTransport {
  readonly capabilities: Capabilities = { ...baseCapabilities };
  private socket: dgram.Socket | null = null;
  private assembler = new FrameAssembler();
  private sequence = 0;
  private updating = false;
  private modelPending = new Map<
    number,
    {
      resolve: (reply: WireModelReply) => void;
      reject: (error: Error) => void;
      timer: ReturnType<typeof setTimeout>;
    }
  >();
  /** 板端 SD 模型库快照，由 op7 逐槽拉取；只是缓存，权威永远在板子上。 */
  private resident: ResidentModel[] = [];
  private activeSlot: number | null = null;
  private libraryPolledAt = 0;
  private timer: ReturnType<typeof setInterval> | null = null;
  private latest: CapturedFrame | null = null;
  private previewOnly = false;
  private previewEnabled = false;
  private polling = false;
  private running = false;
  private decoding = false;
  private owned = false;
  private sinks = new Set<Sink>();
  private previews = new Set<Sink>();
  private pending = new Map<
    number,
    {
      resolve: (status: TransportStatus) => void;
      reject: (error: Error) => void;
      timer: ReturnType<typeof setTimeout>;
    }
  >();
  private state: TransportStatus = {
    runtimeState: "UNKNOWN",
    reportedState: {},
    telemetry: null,
    lastSeen: null,
    error: null,
  };
  constructor(
    private host: string,
    private port: number,
    private localPort: number,
  ) {}
  async connect() {
    await this.open();
    await this.request(1);
    this.owned = true;
    await this.refreshModelState(true).catch(() => undefined);
    if (!this.timer)
      this.timer = setInterval(() => {
        if (this.polling) return;
        this.polling = true;
        void this.request(0)
          .then(async () => {
            // A board reboot clears its UDP destination but status reads still
            // succeed. Re-register preview only when that subscription is lost.
            if (!this.owned || this.previewEnabled || this.updating) return;
            this.latest = null;
            this.assembler.clear();
            await this.request(1);
            await this.refreshModelState(
              Date.now() - this.libraryPolledAt > 15000,
            ).catch(() => undefined);
          })
          .catch((e) => {
            this.state.error = String(e);
          })
          .finally(() => {
            this.polling = false;
          });
      }, 3000);
  }
  private async open() {
    if (this.socket) return;
    const socket = dgram.createSocket("udp4");
    this.socket = socket;
    socket.on("message", (packet, remote) => {
      if (remote.address !== this.host || remote.port !== this.port) return;
      if (
        packet.length === MODEL.replySize &&
        packet.readUInt32LE(0) === MODEL.replyMagic
      ) {
        const reply = readModelReply(packet)!;
        const pending = this.modelPending.get(reply.request);
        if (pending) {
          clearTimeout(pending.timer);
          this.modelPending.delete(reply.request);
          pending.resolve(reply);
        }
        return;
      }
      const status = readStatus(packet);
      if (status) {
        if (this.previewOnly !== Boolean(status.flags & 2))
          this.assembler.clear();
        this.previewOnly = Boolean(status.flags & 2);
        this.previewEnabled = Boolean(status.flags & 4);
        this.running = Boolean(status.flags & 1);
        this.state = {
          runtimeState: status.errorCode
            ? "FAULT"
            : status.flags & 1
              ? "RUNNING"
              : "READY",
          reportedState: {
            ...this.state.reportedState,
            inspectionEnabled: Boolean(status.flags & 1) && !this.previewOnly,
            cameraOnly: this.previewOnly,
          },
          lastSeen: Date.now(),
          error: status.errorCode ? `BOARD_ERROR_${status.errorCode}` : null,
          telemetry: {
            ...status,
            frameId: status.frame,
            receivedAt: new Date().toISOString(),
            timestamp: null,
            fps: status.cycleUs ? 1e6 / status.cycleUs : null,
            layerTiming: null,
          },
        };
        const pending = this.pending.get(status.request);
        if (pending) {
          clearTimeout(pending.timer);
          pending.resolve(this.getStatus());
          this.pending.delete(status.request);
        }
        for (const sink of this.sinks) sink("device.telemetry", this.state);
        return;
      }
      const frame = this.assembler.push(packet, this.previewOnly);
      if (!frame || this.decoding || this.updating) return;
      this.decoding = true;
      void sharp(decodeRgb565(frame.raw), {
        raw: { width: 416, height: 416, channels: 3 },
      })
        .jpeg({ quality: 80 })
        .toBuffer()
        .then((preview) => {
          this.latest = {
            ...frame,
            preview,
            width: 416,
            height: 416,
            format: "RGB565_LE",
            outputs:
              frame.out0 && frame.out1
                ? { out0: frame.out0, out1: frame.out1 }
                : undefined,
            detections:
              frame.out0 && frame.out1 ? detect(frame.out0, frame.out1) : null,
            telemetry:
              this.state.telemetry?.frameId === frame.frameId
                ? this.state.telemetry
                : null,
            modelState: this.getCurrentConfig(),
          };
          for (const sink of this.previews)
            sink("device.preview.frame", this.latest);
        })
        .catch((error) => {
          this.state.error = String(error);
        })
        .finally(() => {
          this.decoding = false;
        });
    });
    socket.on("error", (e) => {
      this.state.error = e.message;
    });
    await new Promise<void>((resolve, reject) => {
      socket.once("error", reject);
      socket.bind(this.localPort, "0.0.0.0", () => {
        socket.off("error", reject);
        socket.setRecvBufferSize(4 * 1024 * 1024);
        resolve();
      });
    });
  }
  private request(command: number, value = 0): Promise<TransportStatus> {
    if (!this.socket)
      return Promise.reject(
        new DomainError("DEVICE_OFFLINE", "UDP transport not connected", 409),
      );
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(
          new DomainError(
            "DEVICE_TIMEOUT",
            "No matching UDP status response",
            504,
          ),
        );
      }, 3000);
      this.pending.set(id, { resolve, reject, timer });
      this.socket!.send(
        commandPacket(id, command, value),
        this.port,
        this.host,
        (error) => {
          if (error) {
            clearTimeout(timer);
            this.pending.delete(id);
            reject(error);
          }
        },
      );
    });
  }
  async disconnect() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    for (const item of this.pending.values()) {
      clearTimeout(item.timer);
      item.reject(new Error("Disconnected"));
    }
    this.pending.clear();
    for (const pending of this.modelPending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error("Disconnected"));
    }
    this.modelPending.clear();
    this.socket?.close();
    this.socket = null;
    this.owned = false;
    this.previewEnabled = false;
    this.state.lastSeen = null;
    this.state.runtimeState = "UNKNOWN";
    this.latest = null;
    this.assembler.clear();
  }
  getStatus() {
    return structuredClone(this.state);
  }
  async sendCommand(type: string, value?: string | number) {
    if (type === "GET_STATUS") {
      await this.open();
      return this.request(0);
    }
    if (!this.owned)
      throw new DomainError(
        "INVALID_STATE",
        "Connect transport before sending controls",
        409,
      );
    const map: Record<string, [number, number]> = {
      START_INSPECTION: [2, 1],
      STOP_INSPECTION: [2, 0],
      CAMERA_ONLY: [3, Number(value)],
      SET_BRIGHTNESS: [4, Number(value)],
    };
    const command = map[type];
    if (!command)
      throw new DomainError(
        "NO_CAPABILITY",
        "Command not supported by current firmware",
        422,
      );
    let status = await this.request(...command);
    if (type === "SET_BRIGHTNESS") {
      const deadline = Date.now() + 2000;
      while (status.telemetry?.brightness !== value && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 50));
        status = await this.request(0);
      }
    }
    if (type === "SET_BRIGHTNESS" && status.telemetry?.brightness !== value)
      throw new DomainError(
        "COMMAND_REJECTED",
        "Board did not report requested brightness",
        409,
      );
    if (
      (type === "START_INSPECTION" && !this.running) ||
      (type === "STOP_INSPECTION" && this.running) ||
      (type === "CAMERA_ONLY" && this.previewOnly !== Boolean(value))
    )
      throw new DomainError(
        "COMMAND_REJECTED",
        "Board did not report running state",
        409,
      );
    return status;
  }
  async captureOnce() {
    if (
      !this.owned ||
      !this.latest ||
      Date.now() - Date.parse(this.latest.receivedAt) > 2000
    )
      throw new DomainError(
        "FRAME_UNAVAILABLE",
        "No recent complete RGB565 frame; connect preview first",
        409,
      );
    return this.latest;
  }
  subscribeTelemetry(sink: Sink) {
    this.sinks.add(sink);
    return () => this.sinks.delete(sink);
  }
  subscribePreview(sink: Sink) {
    this.previews.add(sink);
    return () => this.previews.delete(sink);
  }
  private async modelRpc(
    operation: number,
    offset = 0,
    data: Buffer = Buffer.alloc(0),
  ): Promise<WireModelReply> {
    if (!this.socket)
      throw new DomainError("DEVICE_OFFLINE", "Connect device first", 409);
    const attempts =
      operation === MODEL.ops.DATA || operation === MODEL.ops.FINISH ? 3 : 1;
    for (let attempt = 0; attempt < attempts; attempt++) {
      const id = ++this.sequence,
        packet = modelPacket(id, operation, offset, data);
      try {
        const reply = await new Promise<WireModelReply>((resolve, reject) => {
          const timer = setTimeout(
            () => {
              this.modelPending.delete(id);
              reject(
                new DomainError(
                  "DEVICE_TIMEOUT",
                  "Model protocol response timed out",
                  504,
                ),
              );
            },
            operation === MODEL.ops.INFO ? 1200 : 5000,
          );
          this.modelPending.set(id, { resolve, reject, timer });
          this.socket!.send(packet, this.port, this.host, (error) => {
            if (error) {
              clearTimeout(timer);
              this.modelPending.delete(id);
              reject(error);
            }
          });
        });
        if (reply.result)
          throw new DomainError(
            reply.result === MODEL.result.REJECTED
              ? "CHECKSUM_ERROR"
              : "COMMAND_REJECTED",
            `Board model operation ${operation} rejected: ${reply.result}`,
            409,
          );
        return reply;
      } catch (error) {
        if (
          !(error instanceof DomainError) ||
          error.getStatus() !== 504 ||
          attempt === attempts - 1
        )
          throw error;
      }
    }
    throw new Error("Model request failed");
  }
  /** op0 永远可用；顺带按需刷新模型库（op7 逐槽拉，一次十几包）。 */
  private async refreshModelState(includeLibrary: boolean) {
    const info = await this.modelRpc(MODEL.ops.INFO);
    const capacity = info.total;
    if (
      includeLibrary &&
      info.flags & MODEL.flags.MOUNTED &&
      capacity > 0 &&
      capacity <= 64
    )
      await this.refreshLibrary(capacity);
    this.updateModelState(info);
  }
  private async refreshLibrary(capacity: number) {
    const models: ResidentModel[] = [];
    for (let index = 0; index < capacity; index++) {
      const entry = await this.modelRpc(MODEL.ops.LIST, index);
      if (!entry.version) continue;
      models.push({
        index,
        version: entry.version,
        sha256: entry.sha256,
        generation: entry.generation,
        active: Boolean(entry.flags & MODEL.flags.ENTRY_ACTIVE),
        previous: Boolean(entry.flags & MODEL.flags.ENTRY_PREVIOUS),
      });
    }
    this.resident = models;
    this.libraryPolledAt = Date.now();
  }
  private updateModelState(reply: WireModelReply) {
    const flags = reply.flags,
      available = Boolean(flags & MODEL.flags.AVAILABLE);
    this.capabilities.modelUpdate = Boolean(flags & MODEL.flags.MOUNTED);
    this.capabilities.localStorage = Boolean(flags & MODEL.flags.MOUNTED);
    this.capabilities.offlineInference = available;
    this.capabilities.modelVersion = true;
    this.activeSlot =
      available && reply.received !== MODEL.noSlot ? reply.received : null;
    this.state.reportedState = {
      ...this.state.reportedState,
      modelVersion: available ? reply.version : null,
      modelPayloadSha256: available ? reply.sha256 : null,
      models: flags & MODEL.flags.MOUNTED ? this.resident : null,
    };
    return { flags, version: reply.version, digest: reply.sha256 };
  }
  async deployModel(
    version: string,
    manifest: ModelManifest,
    weights: Buffer,
    progress: (stage: string) => Promise<void>,
  ): Promise<DeploymentReceipt> {
    validateZynqPackage(weights, version, manifest);
    if (!this.owned || !this.capabilities.modelUpdate)
      throw new DomainError(
        "NO_CAPABILITY",
        "Connect CNC2 firmware with an available SD card",
        422,
      );
    if (
      weights.length !== 6416360 ||
      weights.readUInt32LE(0) !== 0x314e4e43 ||
      weights.readUInt32LE(4) !== 1 ||
      weights.readUInt32LE(8) !== 6350208 ||
      weights.readUInt32LE(12) !== 66024 ||
      weights.readUInt32LE(16) ||
      weights.readUInt32LE(20) ||
      weights.subarray(24, 88).toString("ascii").split("\0")[0] !== version ||
      createHash("sha256").update(weights).digest("hex") !==
        manifest.weights.sha256 ||
      createHash("sha256").update(weights.subarray(128)).digest("hex") !==
        weights.subarray(88, 120).toString("hex")
    )
      throw new DomainError(
        "MODEL_INCOMPATIBLE",
        "Invalid fixed-graph SD model package or version",
        422,
      );
    const digest = weights.subarray(88, 120).toString("hex"),
      wasRunning = this.running;
    this.updating = true;
    try {
      await this.sendCommand("STOP_INSPECTION");
      // 板端库里认"载荷摘要 + 版本号"两个都一致的条目；命中就不传字节，直接切。
      await this.refreshModelState(true).catch(() => undefined);
      const resident = this.resident.find(
        (m) => m.sha256 === digest && m.version === version,
      );
      if (resident) {
        await progress("VERIFYING");
        await progress("ACTIVATING");
        await this.modelRpc(MODEL.ops.SELECT, resident.index);
      } else {
        await progress("DOWNLOADING");
        await this.modelRpc(MODEL.ops.BEGIN);
        for (let offset = 0; offset < weights.length; offset += MODEL.packet) {
          const data = weights.subarray(offset, offset + MODEL.packet),
            reply = await this.modelRpc(MODEL.ops.DATA, offset, data);
          if (reply.received < offset + data.length)
            throw new DomainError(
              "COMMAND_REJECTED",
              "Board did not acknowledge model bytes",
              409,
            );
        }
        await progress("VERIFYING");
        await this.modelRpc(MODEL.ops.FINISH);
        await progress("VERIFIED");
        await progress("ACTIVATING");
        await this.modelRpc(MODEL.ops.COMMIT);
      }
      await progress("SELF_TEST");
      const deadline = Date.now() + 15000;
      while (Date.now() < deadline) {
        const info = this.updateModelState(await this.modelRpc(MODEL.ops.INFO));
        if (
          info.version === version &&
          info.digest === digest &&
          (info.flags & (MODEL.flags.READY | MODEL.flags.AVAILABLE)) ===
            (MODEL.flags.READY | MODEL.flags.AVAILABLE) &&
          !(info.flags & MODEL.flags.BUSY)
        ) {
          await this.refreshModelState(true).catch(() => undefined);
          this.latest = null;
          this.assembler.clear();
          return {
            modelVersion: version,
            sha256: manifest.weights.sha256,
            downloaded: !resident,
            verified: true,
            loaded: true,
            selfTest: true,
            active: true,
            simulated: false,
            resident: Boolean(resident),
          };
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      throw new DomainError(
        "COMMAND_REJECTED",
        "Board did not confirm model activation and inference self-test",
        409,
      );
    } finally {
      this.updating = false;
      if (wasRunning) await this.sendCommand("START_INSPECTION");
    }
  }
  async deleteModel(index: number) {
    if (!this.owned || !this.capabilities.localStorage)
      throw new DomainError(
        "NO_CAPABILITY",
        "Device firmware has no readable SD model library",
        422,
      );
    await this.modelRpc(MODEL.ops.DELETE, index);
    await this.refreshModelState(true).catch(() => undefined);
  }
  async restartInference() {
    await this.sendCommand("CAMERA_ONLY", 0);
    return this.sendCommand("START_INSPECTION");
  }
  getCurrentModel(): string | null {
    return this.state.reportedState.modelVersion ?? null;
  }
  getCurrentConfig(): DeviceState {
    return structuredClone(this.state.reportedState);
  }
}
