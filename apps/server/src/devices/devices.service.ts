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
        capabilities:
          transport.capabilities as unknown as Prisma.InputJsonValue,
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
    return devices.map((d) => {
      const t = this.transport(d.id),
        s = t.getStatus(),
        desired = d.desiredState as DeviceState;
      return {
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
        firmwareVersion: d.firmwareVersion,
        protocolVersion: d.protocolVersion,
        error: s.error,
      };
    });
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
