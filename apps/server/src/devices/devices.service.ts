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
import { ZynqUdpTransport } from "./zynq.js";
import type { DeviceTransport, CapturedFrame } from "./transport.js";
@Injectable()
export class DevicesService implements OnModuleInit, OnModuleDestroy {
  private transports = new Map<string, DeviceTransport>();
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
    const transport: DeviceTransport =
      device.type === "SIMULATOR"
        ? new SimulatorTransport(device.reportedState as DeviceState)
        : new ZynqUdpTransport(
            config.ZYNQ_HOST,
            config.ZYNQ_PORT,
            config.ZYNQ_LOCAL_PORT,
          );
    this.transports.set(id, transport);
    transport.subscribeTelemetry((type, payload) =>
      this.events.emit(
        type,
        id,
        payload,
        device.type === "SIMULATOR" ? "SIMULATION" : "BOARD",
      ),
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
                ] ??
                (device.type === "SIMULATOR"
                  ? box.label
                  : `类别 ${box.classId + 1}`),
            })) ?? null,
        },
        device.type === "SIMULATOR" ? "SIMULATION" : "BOARD",
      );
    });
    await this.db.device.update({
      where: { id },
      data: {
        capabilities: (isLinuxTerminal(device)
          ? terminalCapabilities
          : transport.capabilities) as unknown as Prisma.InputJsonValue,
      },
    });
    if (device.type === "SIMULATOR") await transport.connect();
    return transport;
  }
  transport(id: string) {
    const t = this.transports.get(id);
    if (!t) throw new DomainError("NOT_FOUND", "Device not registered", 404);
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
                : state?.paused
                  ? ("READY" as const)
                  : state?.fresh
                    ? ("RUNNING" as const)
                    : ("READY" as const),
            desiredState: {},
            reportedState: {
              modelVersion: state?.modelVersion ?? null,
              inspectionEnabled: state ? !state.paused : undefined,
            },
            syncState: !state
              ? ("UNKNOWN" as const)
              : state.pendingSync
                ? ("DESYNCED" as const)
                : ("SYNCED" as const),
            telemetry: null,
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
          executionMode:
            d.type === "SIMULATOR"
              ? ("SIMULATOR" as const)
              : s.lastSeen
                ? ("BARE_METAL" as const)
                : ("UNCONFIRMED" as const),
          terminal: null,
          id: d.id,
          name: d.name,
          type: d.type,
          source: d.type === "SIMULATOR" ? "SIMULATION" : "BOARD",
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
      throw new DomainError(
        "NO_CAPABILITY",
        "Linux 板端通过作业领取和心跳运行，不支持旧裸机控制、直接模型部署或固件 OTA",
        422,
      );
  }
  async persist() {
    for (const model of await this.db.model.findMany({
      select: { version: true, manifest: true },
    })) {
      const classes = (model.manifest as { classes?: string[] }).classes;
      if (classes) this.modelClasses.set(model.version, classes);
    }
    for (const snapshot of await this.snapshots()) {
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
    }
  }
  async onModuleDestroy() {
    if (this.timer) clearInterval(this.timer);
    for (const transport of this.transports.values())
      await transport.disconnect();
  }
}
