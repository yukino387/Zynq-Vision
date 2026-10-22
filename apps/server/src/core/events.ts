import { Injectable, Inject, type OnModuleDestroy } from "@nestjs/common";
import { JwtService } from "@nestjs/jwt";
import { WebSocketServer, WebSocket } from "ws";
import { randomUUID } from "node:crypto";
import type { Server } from "node:http";
import type { PlatformEvent, Source } from "@vision/contracts";
import { config } from "../config.js";
import { Db } from "./db.js";
@Injectable()
export class Events implements OnModuleDestroy {
  private server: WebSocketServer | null = null;
  private sequence = 0;
  private watchers = new Map<string, Set<WebSocket>>();
  private subscriptions = new WeakMap<WebSocket, Set<string>>();
  watching(deviceId: string) {
    return (this.watchers.get(deviceId)?.size ?? 0) > 0;
  }
  private setWatch(ws: WebSocket, deviceId: string, on: boolean) {
    if (on) {
      let devices = this.watchers.get(deviceId);
      if (!devices) {
        devices = new Set();
        this.watchers.set(deviceId, devices);
      }
      devices.add(ws);
      let subscriptions = this.subscriptions.get(ws);
      if (!subscriptions) {
        subscriptions = new Set();
        this.subscriptions.set(ws, subscriptions);
      }
      subscriptions.add(deviceId);
      return;
    }
    const devices = this.watchers.get(deviceId);
    devices?.delete(ws);
    if (devices && !devices.size) this.watchers.delete(deviceId);
    this.subscriptions.get(ws)?.delete(deviceId);
  }
  private forget(ws: WebSocket) {
    const subscriptions = this.subscriptions.get(ws);
    if (!subscriptions) return;
    for (const deviceId of subscriptions) {
      const devices = this.watchers.get(deviceId);
      devices?.delete(ws);
      if (devices && !devices.size) this.watchers.delete(deviceId);
    }
    this.subscriptions.delete(ws);
  }
  constructor(
    @Inject(JwtService) private jwt: JwtService,
    @Inject(Db) private db: Db,
  ) {}
  attach(server: Server) {
    this.server = new WebSocketServer({ noServer: true, maxPayload: 8192 });
    server.on("upgrade", (req, socket, head) => {
      if (
        new URL(req.url ?? "/", "http://localhost").pathname !== config.WS_PATH
      ) {
        socket.destroy();
        return;
      }
      this.server!.handleUpgrade(req, socket, head, (ws) => {
        let authenticated = false;
        let expiration: ReturnType<typeof setTimeout> | null = null;
        const timeout = setTimeout(
          () => ws.close(1008, "Authentication required"),
          5000,
        );
        ws.once("message", (data) => {
          void (async () => {
            try {
              const { token } = JSON.parse(data.toString()) as {
                token: string;
              };
              const claims = await this.jwt.verifyAsync<{
                sub: string;
                exp: number;
                sessionVersion?: number;
              }>(token);
              const user = await this.db.user.findUnique({
                where: { id: claims.sub },
              });
              if (
                !user ||
                user.disabled ||
                user.sessionVersion !== (claims.sessionVersion ?? 0)
              )
                throw new Error("Unauthorized");
              authenticated = true;
              Object.defineProperty(ws, "actorId", { value: user.id });
              expiration = setTimeout(
                () => ws.close(1008, "Session expired"),
                Math.max(0, claims.exp * 1000 - Date.now()),
              );
              clearTimeout(timeout);
              ws.on("message", (message) => {
                try {
                  const value = JSON.parse(message.toString()) as {
                    type?: string;
                    deviceId?: string;
                  };
                  if (
                    typeof value.deviceId !== "string" ||
                    !value.deviceId ||
                    value.deviceId.length > 100 ||
                    (value.type !== "preview.watch" &&
                      value.type !== "preview.unwatch")
                  )
                    return;
                  this.setWatch(
                    ws,
                    value.deviceId,
                    value.type === "preview.watch",
                  );
                } catch {
                  /* Ignore malformed subscription messages. */
                }
              });
              ws.send(
                JSON.stringify(
                  this.envelope("session.ready", "session", {
                    snapshotUrl: "/api/devices/snapshot",
                  }),
                ),
              );
            } catch {
              ws.close(1008, "Unauthorized");
            }
          })();
        });
        ws.on("close", () => {
          clearTimeout(timeout);
          if (expiration) clearTimeout(expiration);
          this.forget(ws);
        });
        Object.defineProperty(ws, "authorized", { get: () => authenticated });
      });
    });
  }
  private envelope(
    type: string,
    entityId: string,
    payload: unknown,
    source: PlatformEvent["source"] = "SERVER",
    requestId: string = randomUUID(),
  ): PlatformEvent {
    return {
      type,
      entityId,
      payload,
      source,
      requestId,
      timestamp: new Date().toISOString(),
      version: 1,
      sequence: ++this.sequence,
      schemaVersion: 1,
    };
  }
  emit(
    type: string,
    entityId: string,
    payload: unknown,
    source: Source | "SERVER" = "SERVER",
    requestId?: string,
  ) {
    const e = this.envelope(type, entityId, payload, source, requestId);
    for (const ws of this.server?.clients ?? [])
      if (
        ws.readyState === WebSocket.OPEN &&
        (ws as WebSocket & { authorized: boolean }).authorized
      ) {
        if (ws.bufferedAmount > 2 * 1024 * 1024) {
          if (type === "device.preview.frame") continue;
          ws.close(1013, "Client too slow");
          continue;
        }
        ws.send(JSON.stringify(e));
      }
    return e;
  }
  closeUser(id: string, reason = "User disabled") {
    for (const ws of this.server?.clients ?? [])
      if ((ws as WebSocket & { actorId?: string }).actorId === id)
        ws.close(1008, reason);
  }
  count() {
    return this.server?.clients.size ?? 0;
  }
  onModuleDestroy() {
    for (const ws of this.server?.clients ?? []) ws.terminate();
    this.server?.close();
  }
}
