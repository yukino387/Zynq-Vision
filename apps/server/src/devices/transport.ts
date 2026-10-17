import type {
  Capabilities,
  DeviceState,
  Telemetry,
  DetectionBox,
  ModelManifest,
  RuntimeState,
} from "@vision/contracts";
export interface CapturedFrame {
  frameId: number;
  receivedAt: string;
  raw: Buffer;
  width: number;
  height: number;
  format: "RGB565_LE";
  preview: Buffer;
  detections: DetectionBox[] | null;
  telemetry: Telemetry | null;
  modelState: DeviceState;
  outputs?: { out0: Buffer; out1: Buffer };
}
export interface TransportStatus {
  runtimeState: RuntimeState;
  reportedState: DeviceState;
  telemetry: Telemetry | null;
  lastSeen: number | null;
  error: string | null;
}
export interface DeploymentReceipt {
  modelVersion: string;
  sha256: string;
  downloaded: boolean;
  verified: boolean;
  loaded: boolean;
  selfTest: boolean;
  active: boolean;
  simulated: boolean;
  /** 制品已经在设备 SD 卡上，这次只做了切换，没有传输字节。 */
  resident?: boolean;
}
export type Sink = (type: string, payload: unknown) => void;
export interface DeviceTransport {
  readonly capabilities: Capabilities;
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  getStatus(): TransportStatus;
  sendCommand(type: string, value?: number | string): Promise<TransportStatus>;
  captureOnce(): Promise<CapturedFrame>;
  subscribeTelemetry(sink: Sink): () => void;
  subscribePreview(sink: Sink): () => void;
  deployModel(
    version: string,
    manifest: ModelManifest,
    weights: Buffer,
    progress: (stage: string) => Promise<void>,
  ): Promise<DeploymentReceipt>;
  /** 删除设备 SD 模型库里的槽位；板端拒绝删当前版本和上一版。 */
  deleteModel(index: number): Promise<void>;
  restartInference(): Promise<TransportStatus>;
  getCurrentModel(): string | null;
  getCurrentConfig(): DeviceState;
}
export const baseCapabilities: Capabilities = {
  capture: true,
  preview: true,
  inference: true,
  modelUpdate: false,
  localStorage: false,
  offlineInference: false,
  offlineSync: false,
  modelVersion: false,
  planUpdate: false,
  restartInference: true,
};
