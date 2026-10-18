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
  FIRMWARE,
  firmwarePacket,
  readFirmwareReply,
  type WireModelReply,
  type WireFirmwareReply,
} from "@vision/device-protocol";
import type {
  Capabilities,
  ModelManifest,
  DeviceState,
  ResidentModel,
  FirmwareInfo,
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
  type FirmwareStage,
  type FirmwareReceipt,
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
  private firmwarePending = new Map<
    number,
    {
      resolve: (reply: WireFirmwareReply) => void;
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
    // 老固件不认 FMR1：一次短超时探测即可，之后按能力决定是否轮询。
    await this.refreshFirmwareInfo().catch(() => {
      this.capabilities.firmwareUpdate = false;
    });
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
            if (this.capabilities.firmwareUpdate)
              await this.refreshFirmwareInfo().catch(() => undefined);
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
        packet.length === FIRMWARE.replySize &&
        packet.readUInt32LE(0) === FIRMWARE.replyMagic
      ) {
        const reply = readFirmwareReply(packet)!;
        const pending = this.firmwarePending.get(reply.request);
        if (pending) {
          clearTimeout(pending.timer);
          this.firmwarePending.delete(reply.request);
          pending.resolve(reply);
        }
        return;
      }
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
    for (const pending of this.firmwarePending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error("Disconnected"));
    }
    this.firmwarePending.clear();
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
  private firmwareErrorCode(result: number): string {
    switch (result) {
      case FIRMWARE.result.INVALID:
        return "FIRMWARE_INVALID";
      case FIRMWARE.result.BUSY:
        return "DEVICE_BUSY";
      case FIRMWARE.result.STORAGE:
        return "FIRMWARE_STORAGE";
      case FIRMWARE.result.REJECTED:
        return "FIRMWARE_REJECTED";
      case FIRMWARE.result.FULL:
        return "FIRMWARE_FULL";
      case FIRMWARE.result.NOT_FOUND:
        return "NOT_FOUND";
      case FIRMWARE.result.UNUSABLE:
        return "NO_CAPABILITY";
      case FIRMWARE.result.PROTECTED:
        return "FIRMWARE_PROTECTED";
      case FIRMWARE.result.NOT_ARMED:
        return "FIRMWARE_NOT_ARMED";
      case FIRMWARE.result.ROLLED_BACK:
        return "FIRMWARE_ROLLED_BACK";
      default:
        return "COMMAND_REJECTED";
    }
  }
  private async firmwareRpc(
    operation: number,
    offset = 0,
    size = 0,
    data: Buffer = Buffer.alloc(0),
    timeout = operation === FIRMWARE.ops.INFO ? 1500 : 5000,
  ): Promise<WireFirmwareReply> {
    if (!this.socket)
      throw new DomainError("DEVICE_OFFLINE", "Connect device first", 409);
    const attempts =
      operation === FIRMWARE.ops.DATA || operation === FIRMWARE.ops.FINISH
        ? 3
        : 1;
    for (let attempt = 0; attempt < attempts; attempt++) {
      const id = ++this.sequence,
        packet = firmwarePacket(id, operation, offset, size, data);
      try {
        const reply = await new Promise<WireFirmwareReply>((resolve, reject) => {
          const timer = setTimeout(() => {
            this.firmwarePending.delete(id);
            reject(
              new DomainError(
                "DEVICE_TIMEOUT",
                "Firmware protocol response timed out",
                504,
              ),
            );
          }, timeout);
          this.firmwarePending.set(id, { resolve, reject, timer });
          this.socket!.send(packet, this.port, this.host, (error) => {
            if (error) {
              clearTimeout(timer);
              this.firmwarePending.delete(id);
              reject(error);
            }
          });
        });
        if (reply.result)
          throw new DomainError(
            this.firmwareErrorCode(reply.result),
            `Board firmware operation ${operation} rejected: ${reply.result}`,
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
    throw new Error("Firmware request failed");
  }
  private toFirmwareInfo(reply: WireFirmwareReply): FirmwareInfo {
    return {
      supported: Boolean(reply.flags & FIRMWARE.flags.SUPPORTED),
      version: reply.version,
      sha256: reply.sha256,
      generation: reply.generation,
      flags: reply.flags,
      runningSlot: reply.runningSlot,
      activeSlot: reply.activeSlot,
      previousSlot: reply.previousSlot,
      pendingSlot: reply.pendingSlot,
      attempts: reply.attempts,
      maxAttempts: reply.maxAttempts,
      stage: reply.stage,
      slotImageSize: [reply.slotAImageSize, reply.slotBImageSize],
    };
  }
  private applyFirmwareInfo(reply: WireFirmwareReply): FirmwareInfo {
    const info = this.toFirmwareInfo(reply);
    this.capabilities.firmwareUpdate = info.supported;
    this.state.reportedState = {
      ...this.state.reportedState,
      firmwareVersion: info.version,
      firmware: info,
    };
    return info;
  }
  private async refreshFirmwareInfo(): Promise<FirmwareInfo> {
    return this.applyFirmwareInfo(
      await this.firmwareRpc(FIRMWARE.ops.INFO, 0, 0, Buffer.alloc(0), 1500),
    );
  }
  async getFirmwareInfo(): Promise<FirmwareInfo> {
    if (!this.owned)
      throw new DomainError(
        "DEVICE_OFFLINE",
        "Connect the device before reading firmware state",
        409,
      );
    return this.refreshFirmwareInfo();
  }
  /** 等 FINISH 后的板端校验完成。 */
  private async awaitVerified(timeout: number): Promise<FirmwareInfo> {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      try {
        const info = await this.refreshFirmwareInfo();
        if (info.flags & FIRMWARE.flags.VERIFIED) return info;
      } catch {
        // 校验期间主循环可能暂时无法响应，继续等。
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new DomainError(
      "FIRMWARE_VERIFY_TIMEOUT",
      "Board did not verify the firmware package",
      504,
    );
  }
  private async awaitActivation(
    version: string,
    sha256: string,
    slot: number,
    timeout: number,
    progress?: (stage: FirmwareStage) => Promise<void>,
  ): Promise<FirmwareReceipt> {
    const deadline = Date.now() + timeout;
    let sawTarget = false;
    while (Date.now() < deadline) {
      try {
        const info = await this.refreshFirmwareInfo();
        if (info.version === version && info.sha256 === sha256) {
          if (!sawTarget && progress) {
            sawTarget = true;
            await progress("SELF_TEST");
          } else sawTarget = true;
          if (
            info.pendingSlot === FIRMWARE.noneSlot &&
            info.runningSlot === slot &&
            info.activeSlot === slot &&
            !(info.flags & (FIRMWARE.flags.BUSY | FIRMWARE.flags.TRIAL))
          )
            return {
              version: info.version,
              sha256: info.sha256,
              runningSlot: info.runningSlot,
              activeSlot: info.activeSlot,
              previousSlot: info.previousSlot,
              confirmed: true,
              golden: slot === FIRMWARE.goldenSlot,
              attempts: info.attempts,
              simulated: false,
            };
        } else if (sawTarget) {
          throw new DomainError(
            "FIRMWARE_ROLLED_BACK",
            "Board booted a different firmware after the trial",
            409,
          );
        }
      } catch (error) {
        if (error instanceof DomainError && error.getStatus() !== 504) throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
    throw new DomainError(
      "FIRMWARE_TIMEOUT",
      "Board did not confirm the new firmware after reboot",
      504,
    );
  }
  async deployFirmware(
    version: string,
    sha256: string,
    data: Buffer,
    progress: (stage: FirmwareStage) => Promise<void>,
  ): Promise<FirmwareReceipt> {
    if (!this.owned)
      throw new DomainError(
        "DEVICE_OFFLINE",
        "Connect the device before updating firmware",
        409,
      );
    const info = await this.refreshFirmwareInfo();
    if (!info.supported)
      throw new DomainError(
        "NO_CAPABILITY",
        "Device firmware has no PS application OTA support",
        422,
      );
    if (
      info.pendingSlot !== FIRMWARE.noneSlot ||
      info.flags & (FIRMWARE.flags.BUSY | FIRMWARE.flags.TRIAL)
    )
      throw new DomainError(
        "DEVICE_BUSY",
        "Device has a pending firmware trial or update",
        409,
      );
    if (info.version === version && info.sha256 === sha256)
      throw new DomainError(
        "INVALID_STATE",
        "The device is already running this firmware version",
        409,
      );
    const target = info.activeSlot === 0 ? 1 : 0;
    this.updating = true;
    try {
      await progress("DOWNLOADING");
      await this.firmwareRpc(
        FIRMWARE.ops.BEGIN,
        FIRMWARE.armToken,
        data.length,
      );
      for (let offset = 0; offset < data.length; offset += FIRMWARE.packet) {
        const chunk = data.subarray(offset, offset + FIRMWARE.packet),
          reply = await this.firmwareRpc(
            FIRMWARE.ops.DATA,
            offset,
            chunk.length,
            chunk,
          );
        if (reply.received < offset + chunk.length)
          throw new DomainError(
            "COMMAND_REJECTED",
            "Board did not acknowledge firmware bytes",
            409,
          );
      }
      await progress("VERIFYING");
      await this.firmwareRpc(FIRMWARE.ops.FINISH);
      await this.awaitVerified(30000);
      await progress("VERIFIED");
      await progress("WRITING");
      await this.firmwareRpc(FIRMWARE.ops.COMMIT);
      await progress("REBOOTING");
      const receipt = await this.awaitActivation(
        version,
        sha256,
        target,
        90000,
        progress,
      );
      this.latest = null;
      this.assembler.clear();
      return receipt;
    } finally {
      this.updating = false;
    }
  }
  async rollbackFirmware(target: "PREVIOUS" | "GOLDEN"): Promise<FirmwareReceipt> {
    if (!this.owned)
      throw new DomainError(
        "DEVICE_OFFLINE",
        "Connect the device before rolling back firmware",
        409,
      );
    const info = await this.refreshFirmwareInfo();
    if (!info.supported)
      throw new DomainError(
        "NO_CAPABILITY",
        "Device firmware has no PS application OTA support",
        422,
      );
    if (info.flags & FIRMWARE.flags.BUSY)
      throw new DomainError("DEVICE_BUSY", "Device is busy", 409);
    let slot: number;
    if (target === "GOLDEN") slot = FIRMWARE.goldenSlot;
    else if (info.previousSlot === 0 || info.previousSlot === 1)
      slot = info.previousSlot;
    else if (info.previousSlot === FIRMWARE.goldenSlot)
      // The previous image can itself be the golden application.
      slot = FIRMWARE.goldenSlot;
    else
      throw new DomainError(
        "NOT_FOUND",
        "No previous application slot; roll back to golden instead",
        409,
      );
    if (info.runningSlot === slot && info.pendingSlot === FIRMWARE.noneSlot)
      throw new DomainError(
        "INVALID_STATE",
        "Device is already running that firmware slot",
        409,
      );
    this.updating = true;
    try {
      await this.firmwareRpc(
        FIRMWARE.ops.ROLLBACK,
        slot === FIRMWARE.goldenSlot
          ? FIRMWARE.rollbackTarget.GOLDEN
          : FIRMWARE.rollbackTarget.PREVIOUS,
      );
      const deadline = Date.now() + 90000;
      while (Date.now() < deadline) {
        try {
          const next = await this.refreshFirmwareInfo();
          if (
            next.runningSlot === slot &&
            next.pendingSlot === FIRMWARE.noneSlot &&
            !(next.flags & FIRMWARE.flags.BUSY)
          )
            return {
              version: next.version,
              sha256: next.sha256,
              runningSlot: next.runningSlot,
              activeSlot: next.activeSlot,
              previousSlot: next.previousSlot,
              confirmed: true,
              golden: slot === FIRMWARE.goldenSlot,
              attempts: next.attempts,
              simulated: false,
            };
        } catch (error) {
          if (error instanceof DomainError && error.getStatus() !== 504)
            throw error;
        }
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
      throw new DomainError(
        "FIRMWARE_TIMEOUT",
        "Board did not confirm the rollback after reboot",
        504,
      );
    } finally {
      this.updating = false;
    }
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
