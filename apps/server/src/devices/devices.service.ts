import {
  Injectable,
  Inject,
  type OnModuleInit,
  type OnModuleDestroy,
} from "@nestjs/common";
import { Prisma } from "@prisma/client";
import type { DeviceState, DeviceSnapshot } from "@vision/contracts";
import { connectionState, syncState } from "@vision/shared";
import { Db } from "../core/db.js";
import { Events } from "../core/events.js";
import { DomainError } from "../core/errors.js";
import { config } from "../config.js";
import {
  isLinuxTerminal,
  terminalStatus,
  terminalCapabilities,
} from "./terminal-state.js";
import { SimulatorTransport } from "./simulator.js";
import { readTerminalPreview } from "./terminal-preview.js";
import type { DeviceTransport, CapturedFrame } from "./transport.js";
@Injectable()
export class DevicesService implements OnModuleInit, OnModuleDestroy {
  private transports = new Map<string, DeviceTransport>();
  private previewPollers = new Map<
    string,
    {
      timer: ReturnType<typeof setTimeout> | null;
      busy: boolean;
      frameId: number;
      stopped: boolean;
    }
  >();
  private states = new Map<string, string>();
  private timer: ReturnType<typeof setInterval> | null = null;
  private persisting = false;
  private modelClasses = new Map<string, string[]>();
  constructor(
    @Inject(Db) private db: Db,
    @Inject(Events) private events: Events,
  ) {}
  async onModuleInit() {
    for (const device of await this.db.device.findMany()) {
      await this.attach(device.id);
    }
    this.timer = setInterval(() => {
      if (this.persisting) return;
      this.persisting = true;
      void this.persist()
        .catch((error) =>
          console.error(
            JSON.stringify({
              timestamp: new Date().toISOString(),
              level: "error",
              module: "devices",
              message: String(error),
            }),
          ),
        )
        .finally(() => {
          this.persisting = false;
        });
    }, 2000);
  }
  async attach(id: string) {
    if (this.transports.has(id)) return this.transports.get(id)!;
    const device = await this.db.device.findUniqueOrThrow({ where: { id } });
    if (device.type !== "SIMULATOR") {
      await this.db.device.update({
        where: { id },
        data: {
          capabilities:
            terminalCapabilities as unknown as Prisma.InputJsonValue,
        },
      });
      return undefined;
    }
    const transport = new SimulatorTransport(
      device.reportedState as DeviceState,
    );
    this.transports.set(id, transport);
    transport.subscribeTelemetry((type, payload) =>
      this.events.emit(type, id, payload, "SIMULATION"),
    );
    transport.subscribePreview((type, payload) => {
      const frame = payload as CapturedFrame;
      this.events.emit(
        type,
        id,
        {
          frameId: frame.frameId,
          receivedAt: frame.receivedAt,
          width: frame.width,
          height: frame.height,
          jpeg: frame.preview.toString("base64"),
          detections:
            frame.detections?.map((box) => ({
              ...box,
              label:
                this.modelClasses.get(frame.modelState.modelVersion ?? "")?.[
                  box.classId
                ] ?? box.label,
            })) ?? null,
        },
        "SIMULATION",
      );
    });
    await this.db.device.update({
      where: { id },
      data: {
        capabilities:
          transport.capabilities as unknown as Prisma.InputJsonValue,
      },
    });
    await transport.connect();
    return transport;
  }
  transport(id: string) {
    const t = this.transports.get(id);
    if (!t)
      throw new DomainError(
        "NO_CAPABILITY",
        "该设备不使用传输层，请通过终端接口操作",
        422,
      );
    return t;
  }
  async snapshots(): Promise<DeviceSnapshot[]> {
    const devices = await this.db.device.findMany({
      orderBy: { createdAt: "asc" },
    });
    return Promise.all(
      devices.map(async (d) => {
        if (isLinuxTerminal(d)) {
          const terminal = await terminalStatus(this.db, d),
            state = terminal.state;
          return {
            id: d.id,
            name: d.name,
            type: d.type,
            source: "BOARD" as const,
            executionMode: "LINUX_TERMINAL" as const,
            terminal,
            connectionState: terminal.online
              ? ("ONLINE" as const)
              : ("OFFLINE" as const),
            runtimeState: !terminal.online
              ? ("UNKNOWN" as const)
              : state?.error
                ? ("FAULT" as const)
                : state?.production
                  ? ("RUNNING" as const)
                  : state?.model &&
                      state.product &&
                      state.fresh &&
                      !state.paused &&
                      !state.pendingRequestId
                    ? ("READY" as const)
                    : ("UNKNOWN" as const),
            desiredState: {},
            reportedState: {
              modelVersion: state?.model?.version ?? null,
              planVersion: state?.product
                ? `${state.product.id}@${state.product.version}`
                : null,
              inspectionEnabled: state?.production ?? false,
            },
            syncState:
              !terminal.online || !state
                ? ("UNKNOWN" as const)
                : state.pendingSync
                  ? ("DESYNCED" as const)
                  : ("SYNCED" as const),
            telemetry:
              state?.timing && state
                ? {
                    frameId: state.timing.frameId,
                    receivedAt: state.receivedAt,
                    timestamp: null,
                    captureUs: state.timing.prepareMs * 1000,
                    conversionUs: state.timing.prepareMs * 1000,
                    inferenceUs: state.timing.convMs * 1000,
                    transferUs: state.timing.extractMs * 1000,
                    cycleUs: state.timing.captureMs * 1000,
                    fps:
                      state.fps ??
                      (state.timing.captureMs
                        ? 1000 / state.timing.captureMs
                        : null),
                    errorCode: 0,
                    brightness: 0,
                    layerTiming: [
                      state.timing.prepareMs,
                      state.timing.convMs,
                      state.timing.forwardMs,
                      state.timing.postMs,
                      state.timing.extractMs,
                    ].map((value) => value * 1000),
                  }
                : null,
            capabilities: terminalCapabilities,
            lastSeenAt: terminal.lastSeenAt,
            firmwareVersion: null,
            protocolVersion: null,
            error: state?.error || state?.syncError || null,
          };
        }
        const t = this.transport(d.id),
          s = t.getStatus(),
          desired = d.desiredState as DeviceState;
        return {
          executionMode: "SIMULATOR" as const,
          terminal: null,
          id: d.id,
          name: d.name,
          type: d.type,
          source: "SIMULATION" as const,
          connectionState: connectionState(
            s.lastSeen,
            Date.now(),
            config.DEVICE_STALE,
            config.DEVICE_TIMEOUT,
          ),
          runtimeState:
            s.lastSeen && Date.now() - s.lastSeen <= config.DEVICE_TIMEOUT
              ? s.runtimeState
              : "UNKNOWN",
          desiredState: desired,
          reportedState: s.reportedState,
          syncState: syncState(desired, s.reportedState),
          telemetry: s.telemetry,
          capabilities: t.capabilities,
          lastSeenAt: s.lastSeen ? new Date(s.lastSeen).toISOString() : null,
          firmwareVersion:
            (s.reportedState as DeviceState).firmwareVersion ??
            d.firmwareVersion,
          protocolVersion: d.protocolVersion,
          error: s.error,
        };
      }),
    );
  }
  async assertLegacyTransport(id: string) {
    const device = await this.db.device.findUniqueOrThrow({ where: { id } });
    if (isLinuxTerminal(device))
      throw new DomainError("NO_CAPABILITY", "当前设备不支持此维护操作", 422);
  }
  async persist() {
    for (const model of await this.db.model.findMany({
      select: { version: true, manifest: true },
    })) {
      const classes = (model.manifest as { classes?: string[] }).classes;
      if (classes) this.modelClasses.set(model.version, classes);
    }
    const snapshots = await this.snapshots();
    for (const snapshot of snapshots) {
      await this.db.device.update({
        where: { id: snapshot.id },
        data: {
          lastSeenAt: snapshot.lastSeenAt
            ? new Date(snapshot.lastSeenAt)
            : null,
          connectionState: snapshot.connectionState,
          runtimeState: snapshot.runtimeState,
          firmwareVersion: snapshot.firmwareVersion,
          reportedState: snapshot.reportedState as Prisma.InputJsonValue,
        },
      });
      const state = JSON.stringify([
        snapshot.connectionState,
        snapshot.runtimeState,
        snapshot.syncState,
        snapshot.error,
      ]);
      if (this.states.get(snapshot.id) !== state) {
        this.states.set(snapshot.id, state);
        await this.db.deviceEvent.create({
          data: {
            deviceId: snapshot.id,
            type: "device.status.changed",
            source: snapshot.source,
            payload: snapshot as unknown as Prisma.InputJsonValue,
            requestId: crypto.randomUUID(),
          },
        });
        this.events.emit(
          "device.status.changed",
          snapshot.id,
          snapshot,
          snapshot.source,
        );
      }
      if (snapshot.executionMode === "LINUX_TERMINAL" && snapshot.telemetry)
        this.events.emit(
          "device.telemetry",
          snapshot.id,
          {
            telemetry: snapshot.telemetry,
            reportedState: snapshot.reportedState,
            runtimeState: snapshot.runtimeState,
            lastSeen: snapshot.lastSeenAt
              ? Date.parse(snapshot.lastSeenAt)
              : null,
            error: snapshot.error,
          },
          "BOARD",
        );
    }
    this.syncPreviewPollers(snapshots);
  }
  private syncPreviewPollers(snapshots: DeviceSnapshot[]) {
    const online = new Set(
      snapshots
        .filter(
          (snapshot) =>
            snapshot.executionMode === "LINUX_TERMINAL" &&
            snapshot.terminal?.online,
        )
        .map((snapshot) => snapshot.id),
    );
    for (const [id, poller] of this.previewPollers) {
      if (online.has(id) && this.events.count() > 0) continue;
      poller.stopped = true;
      if (poller.timer) clearTimeout(poller.timer);
      this.previewPollers.delete(id);
    }
    if (this.events.count() === 0) return;
    for (const id of online) {
      if (this.previewPollers.has(id)) continue;
      const poller: {
        timer: ReturnType<typeof setTimeout> | null;
        busy: boolean;
        frameId: number;
        stopped: boolean;
      } = { busy: false, frameId: -1, timer: null, stopped: false };
      this.previewPollers.set(id, poller);
      const loop = async () => {
        if (poller.stopped) return;
        try {
          await this.pollTerminalPreview(id);
        } finally {
          if (!poller.stopped) poller.timer = setTimeout(() => void loop(), 0);
        }
      };
      poller.timer = setTimeout(() => void loop(), 0);
    }
  }
  private async pollTerminalPreview(id: string) {
    const poller = this.previewPollers.get(id);
    if (!poller || poller.busy) return;
    poller.busy = true;
    try {
      const device = await this.db.device.findUnique({ where: { id } });
      if (!device || !isLinuxTerminal(device)) return;
      const frame = await readTerminalPreview(device, poller.frameId);
      if (frame.frameId === poller.frameId) return;
      poller.frameId = frame.frameId;
      this.events.emit("device.preview.frame", id, frame, "BOARD");
    } catch {
      // Paused, stale or unreachable terminals simply skip this tick.
    } finally {
      poller.busy = false;
    }
  }
  async onModuleDestroy() {
    if (this.timer) clearInterval(this.timer);
    for (const poller of this.previewPollers.values()) {
      poller.stopped = true;
      if (poller.timer) clearTimeout(poller.timer);
    }
    this.previewPollers.clear();
    for (const transport of this.transports.values())
      await transport.disconnect();
  }
}
