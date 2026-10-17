import { defineStore } from "pinia";
import { ref, computed, watch } from "vue";
import type {
  DeviceSnapshot,
  PlatformEvent,
  Telemetry,
  DeviceState,
  DetectionBox,
} from "@vision/contracts";
import { connectionState } from "@vision/shared";
import { api, RequestError } from "../api";
import { useNotificationStore } from "./notifications";
import { useAuthStore } from "./auth";
export interface Preview {
  frameId: number;
  receivedAt: string;
  width: number;
  height: number;
  jpeg: string;
  detections: DetectionBox[] | null;
}
export const useDeviceStore = defineStore("devices", () => {
  const devices = ref<DeviceSnapshot[]>([]),
    selected = ref(localStorage.getItem("vision.web.device") ?? ""),
    connected = ref(false),
    previews = ref<Record<string, Preview>>({}),
    recent = ref<PlatformEvent[]>([]),
    /** 最近若干帧的遥测，仅供趋势图；服务端不持久化遥测。 */
    history = ref<
      {
        at: number;
        inferenceUs: number | null;
        cycleUs: number | null;
        fps: number | null;
      }[]
    >([]);
  let policy = { staleMs: 10000, offlineMs: 30000, wsPath: "/ws" },
    generation = 0;
  let socket: WebSocket | null = null,
    retry: ReturnType<typeof setTimeout> | null = null,
    clock: ReturnType<typeof setInterval> | null = null,
    stopped = false;
  const current = computed(
    () =>
      devices.value.find((d) => d.id === selected.value) ?? devices.value[0],
  );
  watch(selected, (id) => {
    localStorage.setItem("vision.web.device", id);
    history.value = [];
  });
  async function snapshot() {
    policy = await api("/devices/policy");
    devices.value = await api("/devices/snapshot");
    if (!devices.value.some((d) => d.id === selected.value))
      selected.value =
        devices.value.find((d) => d.type === "ZYNQ")?.id ??
        devices.value[0]?.id ??
        "";
  }
  async function connect() {
    const attemptGeneration = generation;
    stopped = false;
    try {
      policy = await api("/devices/policy");
    } catch (error) {
      if (error instanceof RequestError && error.status === 401) {
        useAuthStore().logout();
        return;
      }
      if (!stopped && attemptGeneration === generation)
        retry = setTimeout(() => {
          void connect();
        }, 2000);
      return;
    }
    if (stopped || attemptGeneration !== generation) return;
    const currentSocket = new WebSocket(
      `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${policy.wsPath}`,
    );
    socket = currentSocket;
    socket.onopen = () =>
      socket?.send(
        JSON.stringify({ token: sessionStorage.getItem("vision.token") }),
      );
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data as string) as PlatformEvent;
      if (event.type === "session.ready") {
        connected.value = true;
        void snapshot().catch((e) => useNotificationStore().error(e));
        return;
      }
      const device = devices.value.find((d) => d.id === event.entityId);
      if (event.type === "device.preview.frame") {
        previews.value[event.entityId] = event.payload as Preview;
        return;
      }
      if (event.type === "device.telemetry" && device) {
        const p = event.payload as {
          telemetry: Telemetry;
          reportedState: DeviceState;
          runtimeState: DeviceSnapshot["runtimeState"];
          lastSeen: number | null;
          error: string | null;
        };
        device.telemetry = p.telemetry;
        device.reportedState = p.reportedState;
        device.runtimeState = p.runtimeState;
        device.lastSeenAt = p.lastSeen
          ? new Date(p.lastSeen).toISOString()
          : null;
        device.error = p.error;
        device.connectionState = p.lastSeen ? "ONLINE" : "OFFLINE";
        // 遥测不落库，所以趋势只能在客户端攒。只留最近 120 帧，够画一条趋势。
        if (device.id === current.value?.id)
          history.value = [
            ...history.value,
            {
              at: Date.now(),
              inferenceUs: p.telemetry?.inferenceUs ?? null,
              cycleUs: p.telemetry?.cycleUs ?? null,
              fps: p.telemetry?.fps ?? null,
            },
          ].slice(-120);
        return;
      }
      if (event.type === "device.status.changed") {
        void snapshot().catch((e) => useNotificationStore().error(e));
      }
      recent.value = [event, ...recent.value].slice(0, 30);
    };
    socket.onclose = (event) => {
      if (socket !== currentSocket) return;
      connected.value = false;
      if (event.code === 1008) {
        useNotificationStore().add("登录状态已变更或过期，请重新登录。", true);
        useAuthStore().logout();
        return;
      }
      if (!stopped) retry = setTimeout(connect, 2000);
    };
    socket.onerror = () => currentSocket.close();
  }
  async function start() {
    stop();
    stopped = false;
    await snapshot().catch((e) => useNotificationStore().error(e));
    connect();
    clock = setInterval(() => {
      for (const d of devices.value) {
        d.connectionState = connectionState(
          d.lastSeenAt ? Date.parse(d.lastSeenAt) : null,
          Date.now(),
          policy.staleMs,
          policy.offlineMs,
        );
        if (d.connectionState === "OFFLINE") d.runtimeState = "UNKNOWN";
      }
    }, 2000);
  }
  function stop() {
    generation++;
    stopped = true;
    if (socket) {
      socket.onclose = null;
      socket.onerror = null;
      socket.close();
    }
    socket = null;
    connected.value = false;
    if (retry) clearTimeout(retry);
    if (clock) clearInterval(clock);
  }
  return {
    devices,
    selected,
    current,
    connected,
    previews,
    recent,
    history,
    snapshot,
    start,
    stop,
  };
});
