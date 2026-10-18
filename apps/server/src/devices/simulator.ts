import { createHash } from "node:crypto";
import sharp from "sharp";
import type {
  Capabilities,
  ModelManifest,
  DeviceState,
  ResidentModel,
  FirmwareInfo,
} from "@vision/contracts";
import { DomainError } from "../core/errors.js";
import {
  baseCapabilities,
  type DeviceTransport,
  type TransportStatus,
  type CapturedFrame,
  type Sink,
  type DeploymentReceipt,
  type FirmwareStage,
  type FirmwareReceipt,
} from "./transport.js";
export class SimulatorTransport implements DeviceTransport {
  readonly capabilities: Capabilities = {
    ...baseCapabilities,
    modelUpdate: true,
    firmwareUpdate: true,
    modelVersion: true,
    planUpdate: true,
    offlineInference: true,
  };
  private sinks = new Set<Sink>();
  private previews = new Set<Sink>();
  private timer: ReturnType<typeof setInterval> | null = null;
  private sequence = 0;
  private fault = "NONE";
  private state: TransportStatus;
  private frame: CapturedFrame | null = null;
  private producing = false;
  /** 假的 SD 模型库。模拟器没有制品包，sha256 直接用 manifest 的整包摘要。 */
  private library: ResidentModel[] = [];
  private slots = 0;
  private firmware: FirmwareInfo = {
    supported: true,
    version: "SIM-GOLDEN",
    sha256: "",
    generation: 1,
    flags: 64,
    runningSlot: 2,
    activeSlot: 2,
    previousSlot: 0xffffffff,
    pendingSlot: 0xffffffff,
    attempts: 0,
    maxAttempts: 3,
    stage: 0,
    slotImageSize: [0, 0],
  };
  private firmwareSlots = [
    { version: "", sha256: "" },
    { version: "", sha256: "" },
  ];
  constructor(
    reported: DeviceState = {
      modelVersion: "SIM-V1",
      inspectionEnabled: true,
      planVersion: "SIM-P1",
    },
  ) {
    this.state = {
      runtimeState: "UNKNOWN",
      reportedState: reported,
      telemetry: null,
      lastSeen: null,
      error: null,
    };
  }
  async connect() {
    this.state.runtimeState = "RUNNING";
    this.state.reportedState.firmwareVersion = this.firmware.version;
    this.state.reportedState.firmware = structuredClone(this.firmware);
    await this.tick();
    if (!this.timer)
      this.timer = setInterval(() => {
        void this.tick().catch((e) => {
          this.state.error = String(e);
        });
      }, 500);
  }
  async disconnect() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.state.lastSeen = null;
    this.state.runtimeState = "UNKNOWN";
    this.emit("device.status.changed", this.state);
  }
  getStatus() {
    return structuredClone(this.state);
  }
  private emit(type: string, payload: unknown) {
    for (const sink of this.sinks) sink(type, payload);
  }
  async sendCommand(type: string, value?: string | number) {
    if (type === "FAULT") {
      this.fault = String(value ?? "NONE");
      if (this.fault === "NETWORK_LOST") this.state.lastSeen = null;
      this.emit("device.error", { code: this.fault, simulated: true });
    } else if (type === "START_INSPECTION") {
      this.state.runtimeState = "RUNNING";
      this.state.reportedState.inspectionEnabled = true;
    } else if (type === "STOP_INSPECTION") {
      this.state.runtimeState = "READY";
      this.state.reportedState.inspectionEnabled = false;
    } else if (type === "SET_PLAN") {
      this.state.reportedState.planVersion = String(value);
    } else if (type !== "GET_STATUS")
      throw new DomainError(
        "NO_CAPABILITY",
        "Unsupported simulator command",
        422,
      );
    await this.tick();
    return this.getStatus();
  }
  private async tick() {
    if (
      this.producing ||
      ["NETWORK_LOST", "DEVICE_TIMEOUT"].includes(this.fault)
    )
      return;
    this.producing = true;
    try {
      const now = new Date().toISOString(),
        frameId = ++this.sequence;
      const inferenceUs =
        this.fault === "HIGH_LATENCY" ? 250000 : 48000 + (frameId % 7) * 1300;
      this.state.lastSeen = Date.now();
      this.state.error =
        this.fault === "INFERENCE_ERROR"
          ? "SIMULATED INFERENCE ERROR"
          : this.fault === "QUEUE_OVERFLOW"
            ? "SIMULATED QUEUE OVERFLOW"
            : null;
      this.state.telemetry = {
        frameId,
        receivedAt: now,
        timestamp: now,
        captureUs: 1200,
        conversionUs: 2500,
        inferenceUs,
        transferUs: 3100,
        cycleUs: this.fault === "LOW_FPS" ? 500000 : inferenceUs + 6800,
        fps: this.fault === "LOW_FPS" ? 2 : 1e6 / (inferenceUs + 6800),
        errorCode: this.state.error ? 1 : 0,
        brightness: 0,
        layerTiming: null,
      };
      this.emit("device.telemetry", this.state);
      if (this.state.runtimeState !== "RUNNING") return;
      const raw = Buffer.alloc(416 * 416 * 2);
      for (let y = 0; y < 416; y++)
        for (let x = 0; x < 416; x++) {
          let v = 110 + (Math.floor(x / 7) % 15);
          if (x > 100 && x < 118 && y > 90 && y < 290) v = 45;
          raw.writeUInt16LE(
            ((v >> 3) << 11) | ((v >> 2) << 5) | (v >> 3),
            (y * 416 + x) * 2,
          );
        }
      const svg = Buffer.from(
        `<svg width="416" height="416"><rect width="416" height="416" fill="#a7aba5"/><path d="M110 90 L120 150 L106 210 L118 290" fill="none" stroke="#424a43" stroke-width="6"/><text x="20" y="32" font-size="18" fill="#183e2a" font-family="Microsoft YaHei, sans-serif">模拟画面 ${frameId}</text></svg>`,
      );
      const preview = await sharp(svg).jpeg({ quality: 80 }).toBuffer();
      const detections =
        frameId % 3 === 0
          ? []
          : [
              {
                classId: 5,
                label: "SIMULATED 划痕",
                confidence: frameId % 3 === 1 ? 0.82 : 0.48,
                x1: 90,
                y1: 80,
                x2: 140,
                y2: 300,
              },
            ];
      this.frame = {
        frameId,
        receivedAt: now,
        raw,
        width: 416,
        height: 416,
        format: "RGB565_LE",
        preview,
        detections: this.state.error ? null : detections,
        telemetry: this.state.telemetry,
        modelState: structuredClone(this.state.reportedState),
      };
      for (const sink of this.previews)
        sink("device.preview.frame", this.frame);
    } finally {
      this.producing = false;
    }
  }
  async captureOnce() {
    if (
      !this.timer ||
      !this.state.lastSeen ||
      Date.now() - this.state.lastSeen > 3000
    )
      throw new DomainError(
        "DEVICE_TIMEOUT",
        "SIMULATED device is offline",
        504,
      );
    if (this.fault === "INFERENCE_ERROR")
      throw new DomainError(
        "INFERENCE_ERROR",
        "SIMULATED inference failure",
        502,
      );
    if (!this.frame)
      throw new DomainError(
        "FRAME_UNAVAILABLE",
        "No complete simulated frame",
        409,
      );
    return this.frame;
  }
  subscribeTelemetry(sink: Sink) {
    this.sinks.add(sink);
    return () => this.sinks.delete(sink);
  }
  subscribePreview(sink: Sink) {
    this.previews.add(sink);
    return () => this.previews.delete(sink);
  }
  async deployModel(
    version: string,
    manifest: ModelManifest,
    weights: Buffer,
    progress: (stage: string) => Promise<void>,
  ): Promise<DeploymentReceipt> {
    if (!this.timer || !this.state.lastSeen)
      throw new DomainError(
        "DEVICE_TIMEOUT",
        "SIMULATED device is offline",
        504,
      );
    const previous = this.state.reportedState.modelVersion;
    this.state.runtimeState = "UPDATING";
    try {
      for (const stage of [
        "DOWNLOADING",
        "VERIFYING",
        "VERIFIED",
        "ACTIVATING",
        "SELF_TEST",
      ]) {
        await progress(stage);
        if (["NETWORK_LOST", "DEVICE_TIMEOUT"].includes(this.fault))
          throw new Error("SIMULATED device timeout");
        if (this.fault === "DEPLOYMENT_FAILED")
          throw new Error("SIMULATED deployment failure");
        if (
          stage === "VERIFYING" &&
          (this.fault === "CHECKSUM_ERROR" ||
            createHash("sha256").update(weights).digest("hex") !==
              manifest.weights.sha256 ||
            weights.length !== manifest.weights.size)
        )
          throw new Error("Checksum mismatch");
        if (this.fault === "INVALID_MODEL")
          throw new Error("SIMULATED invalid model");
        await new Promise((r) => setTimeout(r, 40));
      }
      this.state.reportedState.modelVersion = version;
      const existing = this.library.find(
        (m) => m.sha256 === manifest.weights.sha256,
      );
      if (!existing?.active) {
        for (const m of this.library) {
          m.previous = m.active;
          m.active = false;
        }
        if (existing) existing.active = true;
        else
          this.library.push({
            index: this.slots++,
            version,
            sha256: manifest.weights.sha256,
            generation: this.library.length + 1,
            active: true,
            previous: false,
          });
        this.publishLibrary();
      }
      this.state.runtimeState = "RUNNING";
      await this.tick();
      return {
        modelVersion: version,
        sha256: manifest.weights.sha256,
        downloaded: true,
        verified: true,
        loaded: true,
        selfTest: true,
        active: true,
        simulated: true,
      };
    } catch (error) {
      this.state.reportedState.modelVersion = previous;
      this.state.runtimeState = "RUNNING";
      throw error;
    }
  }
  async restartInference() {
    await this.sendCommand("START_INSPECTION");
    return this.getStatus();
  }
  private publishFirmware() {
    this.state.reportedState = {
      ...this.state.reportedState,
      firmwareVersion: this.firmware.version,
      firmware: structuredClone(this.firmware),
    };
  }
  async getFirmwareInfo(): Promise<FirmwareInfo> {
    if (!this.timer || !this.state.lastSeen)
      throw new DomainError(
        "DEVICE_TIMEOUT",
        "SIMULATED device is offline",
        504,
      );
    return structuredClone(this.firmware);
  }
  async deployFirmware(
    version: string,
    sha256: string,
    data: Buffer,
    progress: (stage: FirmwareStage) => Promise<void>,
  ): Promise<FirmwareReceipt> {
    if (!this.timer || !this.state.lastSeen)
      throw new DomainError(
        "DEVICE_TIMEOUT",
        "SIMULATED device is offline",
        504,
      );
    if (this.firmware.pendingSlot !== 0xffffffff)
      throw new DomainError(
        "DEVICE_BUSY",
        "SIMULATED firmware trial already pending",
        409,
      );
    if (this.firmware.version === version && this.firmware.sha256 === sha256)
      throw new DomainError(
        "INVALID_STATE",
        "SIMULATED device already runs this firmware",
        409,
      );
    if (!data.length)
      throw new DomainError("FIRMWARE_INVALID", "Empty firmware package", 422);
    const previous = structuredClone(this.firmware),
      target = this.firmware.activeSlot === 0 ? 1 : 0;
    this.state.runtimeState = "UPDATING";
    try {
      for (const stage of [
        "DOWNLOADING",
        "VERIFYING",
        "VERIFIED",
        "WRITING",
        "REBOOTING",
        "SELF_TEST",
      ] as FirmwareStage[]) {
        await progress(stage);
        if (["NETWORK_LOST", "DEVICE_TIMEOUT"].includes(this.fault))
          throw new Error("SIMULATED device timeout");
        if (this.fault === "FIRMWARE_FAILED")
          throw new Error("SIMULATED firmware update failure");
        if (stage === "VERIFYING" && this.fault === "CHECKSUM_ERROR")
          throw new Error("SIMULATED firmware checksum mismatch");
        await new Promise((r) => setTimeout(r, 50));
      }
      this.firmware = {
        ...this.firmware,
        version,
        sha256,
        flags: 1,
        runningSlot: target,
        activeSlot: target,
        previousSlot: previous.runningSlot,
        pendingSlot: 0xffffffff,
        attempts: 0,
        stage: 9,
        generation: this.firmware.generation + 1,
        slotImageSize:
          target === 0
            ? [data.length, this.firmware.slotImageSize[1]]
            : [this.firmware.slotImageSize[0], data.length],
      };
      this.firmwareSlots[target] = { version, sha256 };
      this.publishFirmware();
      this.state.runtimeState = "RUNNING";
      await this.tick();
      return {
        version,
        sha256,
        runningSlot: target,
        activeSlot: target,
        previousSlot: previous.runningSlot,
        confirmed: true,
        golden: false,
        attempts: 0,
        simulated: true,
      };
    } catch (error) {
      this.firmware = previous;
      this.publishFirmware();
      this.state.runtimeState = "RUNNING";
      throw error;
    }
  }
  async rollbackFirmware(target: "PREVIOUS" | "GOLDEN"): Promise<FirmwareReceipt> {
    if (!this.timer || !this.state.lastSeen)
      throw new DomainError(
        "DEVICE_TIMEOUT",
        "SIMULATED device is offline",
        504,
      );
    const previous = structuredClone(this.firmware);
    let slot: number;
    if (target === "GOLDEN") slot = 2;
    else if (
      this.firmware.previousSlot === 0 ||
      this.firmware.previousSlot === 1
    )
      slot = this.firmware.previousSlot;
    else
      throw new DomainError(
        "NOT_FOUND",
        "SIMULATED device has no previous application slot",
        409,
      );
    this.firmware = {
      ...this.firmware,
      version:
        slot === 2
          ? "SIM-GOLDEN"
          : this.firmwareSlots[slot]!.version || `SIM-FW-SLOT-${slot + 1}`,
      sha256: slot === 2 ? "" : this.firmwareSlots[slot]!.sha256,
      flags: slot === 2 ? 64 : 1,
      runningSlot: slot,
      activeSlot: slot,
      previousSlot: previous.runningSlot,
      pendingSlot: 0xffffffff,
      attempts: 0,
      stage: 9,
      generation: this.firmware.generation + 1,
    };
    this.publishFirmware();
    await this.tick();
    return {
      version: this.firmware.version,
      sha256: this.firmware.sha256,
      runningSlot: slot,
      activeSlot: slot,
      previousSlot: previous.runningSlot,
      confirmed: true,
      golden: slot === 2,
      attempts: 0,
      simulated: true,
    };
  }
  private publishLibrary() {
    this.state.reportedState = {
      ...this.state.reportedState,
      models: [...this.library],
    };
  }
  async deleteModel(index: number) {
    const entry = this.library.find((m) => m.index === index);
    if (!entry)
      throw new DomainError("NOT_FOUND", "No such resident model", 404);
    if (entry.active || entry.previous)
      throw new DomainError(
        "COMMAND_REJECTED",
        "Cannot delete the active or previous model",
        409,
      );
    this.library = this.library.filter((m) => m.index !== index);
    this.publishLibrary();
  }
  getCurrentModel() {
    return this.state.reportedState.modelVersion ?? null;
  }
  getCurrentConfig() {
    return structuredClone(this.state.reportedState);
  }
}
