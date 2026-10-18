import type {
  Capabilities,
  DeviceState,
  Telemetry,
  DetectionBox,
  ModelManifest,
  RuntimeState,
  FirmwareInfo,
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
export type FirmwareStage =
  | "DOWNLOADING"
  | "VERIFYING"
  | "VERIFIED"
  | "WRITING"
  | "REBOOTING"
  | "SELF_TEST";
export interface FirmwareReceipt {
  version: string;
  sha256: string;
  runningSlot: number;
  activeSlot: number;
  previousSlot: number;
  /** 板端已确认为正式版本（pending 已清空）。 */
  confirmed: boolean;
  golden: boolean;
  attempts: number;
  simulated: boolean;
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
  /** PS 应用 OTA：读取板端槽位/版本状态；老固件会拒绝。 */
  getFirmwareInfo(): Promise<FirmwareInfo>;
  deployFirmware(
    version: string,
    sha256: string,
    data: Buffer,
    progress: (stage: FirmwareStage) => Promise<void>,
  ): Promise<FirmwareReceipt>;
  rollbackFirmware(target: "PREVIOUS" | "GOLDEN"): Promise<FirmwareReceipt>;
  restartInference(): Promise<TransportStatus>;
  getCurrentModel(): string | null;
  getCurrentConfig(): DeviceState;
}
export const baseCapabilities: Capabilities = {
  capture: true,
  preview: true,
  inference: true,
  modelUpdate: false,
  firmwareUpdate: false,
  localStorage: false,
  offlineInference: false,
  offlineSync: false,
  modelVersion: false,
  planUpdate: false,
  restartInference: true,
};
