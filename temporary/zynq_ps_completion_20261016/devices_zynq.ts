import dgram from "node:dgram";
import sharp from "sharp";
import {
  FrameAssembler,
  commandPacket,
  readStatus,
  decodeRgb565,
  detect,
} from "@vision/device-protocol";
import type {
  Capabilities,
  ModelManifest,
  DeviceState,
} from "@vision/contracts";
import { DomainError } from "../core/errors.js";
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
  private timer: ReturnType<typeof setInterval> | null = null;
  private latest: CapturedFrame | null = null;
  private previewOnly = false;
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
    if (!this.timer)
      this.timer = setInterval(() => {
        void this.request(0).catch((e) => {
          this.state.error = String(e);
        });
      }, 3000);
  }
  private async open() {
    if (this.socket) return;
    const socket = dgram.createSocket("udp4");
    this.socket = socket;
    socket.on("message", (packet, remote) => {
      if (remote.address !== this.host || remote.port !== this.port) return;
      const status = readStatus(packet);
      if (status) {
        if (this.previewOnly !== Boolean(status.flags & 2))
          this.assembler.clear();
        this.previewOnly = Boolean(status.flags & 2);
        this.running = Boolean(status.flags & 1);
        this.state = {
          runtimeState: status.errorCode
            ? "FAULT"
            : status.flags & 1
              ? "RUNNING"
              : "READY",
          reportedState: {
            inspectionEnabled: Boolean(status.flags & 1) && !this.previewOnly,
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
      if (!frame || this.decoding) return;
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
            modelState: {},
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
    this.socket?.close();
    this.socket = null;
    this.owned = false;
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
    const status = await this.request(...command);
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
  async deployModel(
    _version: string,
    _manifest: ModelManifest,
    _weights: Buffer,
    _progress: (stage: string) => Promise<void>,
  ): Promise<DeploymentReceipt> {
    throw new DomainError(
      "NO_CAPABILITY",
      "Current Zynq firmware has no model deployment protocol",
      422,
    );
  }
  async restartInference() {
    return this.sendCommand("START_INSPECTION");
  }
  getCurrentModel(): string | null {
    return null;
  }
  getCurrentConfig(): DeviceState {
    return structuredClone(this.state.reportedState);
  }
}
