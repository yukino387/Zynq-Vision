import { computed, reactive, markRaw, watch } from "vue";
import type {
  DetectionBox,
  DeviceSnapshot,
  PlatformEvent,
  Telemetry,
} from "@vision/contracts";
import { request, session, logout, requireLogin } from "./state";

export interface LiveFrame {
  frameId: number;
  planId?: string | null;
  planVersion?: number | null;
  receivedAt: string;
  width: number;
  height: number;
  jpeg: string;
  detections: DetectionBox[] | null;
}

/** 与 Web 工作台同一条 /ws 预览流：只保留最近帧，不写存储。 */
export const live = reactive({
  ready: false,
  connecting: false,
  error: "",
  devices: [] as DeviceSnapshot[],
  deviceId: (uni.getStorageSync("vision.device") as string) || "",
  frame: null as LiveFrame | null,
  frames: [] as LiveFrame[],
  retainFrames: false,
  telemetry: null as Telemetry | null,
  runtimeState: "UNKNOWN" as DeviceSnapshot["runtimeState"],
  reportedState: {} as DeviceSnapshot["reportedState"],
  /** 每秒跳动一次，用于计算帧龄，避免在模板里读 Date.now()。 */
  now: Date.now(),
  fps: 0,
  lastFrameAt: 0,
  /** 任意检测完成时间戳；列表页据此自动刷新。 */
  completedAt: 0,
});

let socket: UniNamespace.SocketTask | null = null;
let retry: ReturnType<typeof setTimeout> | null = null;
let heartbeat: ReturnType<typeof setInterval> | null = null;
let snapshotTimer: ReturnType<typeof setInterval> | null = null;
let authTimer: ReturnType<typeof setTimeout> | null = null;
let stopped = true;
let starting = false;
let arrivals: number[] = [];
/** 胶片条只按每秒两帧留取，避免 30 FPS 时反复重建缩略图。 */
let lastStripAt = 0;
let reconnectAttempt = 0;
let previewConsumers = 0;
let watchedDevice = "";

function syncPreviewWatch() {
  if (!socket || !live.ready) return;
  const next = previewConsumers > 0 ? live.deviceId : "";
  if (next === watchedDevice) return;
  if (watchedDevice)
    socket.send({
      data: JSON.stringify({
        type: "preview.unwatch",
        deviceId: watchedDevice,
      }),
    });
  watchedDevice = next;
  if (next)
    socket.send({
      data: JSON.stringify({ type: "preview.watch", deviceId: next }),
    });
}

// 只在画面可见时向平台订阅；切设备与重连后重新订阅。
export function attachLivePreview() {
  previewConsumers++;
  syncPreviewWatch();
}
export function detachLivePreview() {
  previewConsumers = Math.max(0, previewConsumers - 1);
  syncPreviewWatch();
  if (!previewConsumers) {
    live.frame = null;
    live.frames = [];
  }
}
watch(() => live.deviceId, syncPreviewWatch);

export const liveDevice = computed<DeviceSnapshot | null>(
  () => live.devices.find((d) => d.id === live.deviceId) ?? null,
);
/** 服务器与设备都在线，才算真正能收到画面。 */
export const liveOnline = computed(
  () => live.ready && liveDevice.value?.connectionState === "ONLINE",
);
export const liveDetections = computed(() => live.frame?.detections ?? null);
export const frameAge = computed(() =>
  live.frame ? Math.max(0, live.now - live.lastFrameAt) : null,
);

function message(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function serverBase() {
  if (session.server) return session.server.replace(/\/$/, "");
  // #ifdef H5
  return location.origin;
  // #endif
  // #ifndef H5
  return "";
  // #endif
}

function socketUrl() {
  const base = serverBase();
  if (!base) throw new Error("尚未配对服务器");
  return `${base.replace(/^http/, "ws")}/ws`;
}

export function setDevice(id: string, persist = true) {
  if (!id || live.deviceId === id) return;
  live.deviceId = id;
  live.frame = null;
  live.frames = [];
  live.telemetry = null;
  live.runtimeState = "UNKNOWN";
  live.reportedState = {};
  lastStripAt = 0;
  live.fps = 0;
  live.lastFrameAt = 0;
  arrivals = [];
  if (persist) {
    session.deviceId = id;
    uni.setStorageSync("vision.device", id);
  }
}

/** 设备列表只由服务器快照决定；实时事件只用来补状态，不新增设备。 */
let refreshing = false;
export async function refreshDevices() {
  if (!session.token || refreshing) return live.devices;
  refreshing = true;
  try {
    const list = (await request<DeviceSnapshot[]>("/devices/snapshot")).filter(
      (d) => d.type !== "SIMULATOR",
    );
    live.devices = list;
    if (!list.some((d) => d.id === live.deviceId)) {
      const preferred =
        list.find((d) => d.id === session.deviceId) ??
        list.find(
          (d) => d.connectionState === "ONLINE" && d.capabilities.preview,
        ) ??
        list[0];
      if (preferred) setDevice(preferred.id);
      else {
        live.deviceId = "";
        live.frame = null;
        live.frames = [];
        live.telemetry = null;
      }
    }
    const selected = list.find((d) => d.id === live.deviceId);
    if (selected) {
      live.telemetry = selected.telemetry;
      live.runtimeState = selected.runtimeState;
      live.reportedState = selected.reportedState;
    }
    live.error = "";
    return list;
  } catch (error) {
    live.error = message(error);
    return live.devices;
  } finally {
    refreshing = false;
  }
}

function handle(event: PlatformEvent) {
  if (event.type === "session.ready") {
    live.ready = true;
    live.connecting = false;
    live.error = "";
    syncPreviewWatch();
    if (authTimer) {
      clearTimeout(authTimer);
      authTimer = null;
    }
    void refreshDevices();
    return;
  }
  if (event.type === "device.preview.frame") {
    if (!previewConsumers) return;
    const frame = event.payload as LiveFrame;
    if (!frame?.jpeg) return;
    if (live.deviceId && event.entityId !== live.deviceId) return;
    if (!live.deviceId) {
      // 快照还没到时不要被先到的帧抢走选择；用户在网页端配好的设备优先。
      if (session.deviceId) return;
      setDevice(event.entityId);
    }
    live.frame = markRaw(frame);
    live.lastFrameAt = Date.now();
    if (
      live.retainFrames &&
      (!live.frames.length || live.lastFrameAt - lastStripAt > 500)
    ) {
      lastStripAt = live.lastFrameAt;
      live.frames = [...live.frames, frame].slice(-6);
    }
    arrivals.push(live.lastFrameAt);
    return;
  }
  if (event.type === "device.telemetry") {
    const payload = event.payload as {
      telemetry: Telemetry | null;
      reportedState: DeviceSnapshot["reportedState"];
      runtimeState: DeviceSnapshot["runtimeState"];
      lastSeen: number | null;
      error: string | null;
    };
    const device = live.devices.find((d) => d.id === event.entityId);
    if (device) {
      device.telemetry = payload.telemetry;
      device.reportedState = payload.reportedState;
      device.runtimeState = payload.runtimeState;
      device.connectionState = payload.lastSeen ? "ONLINE" : "OFFLINE";
      device.error = payload.error;
      device.lastSeenAt = payload.lastSeen
        ? new Date(payload.lastSeen).toISOString()
        : null;
    }
    if (event.entityId === live.deviceId) {
      live.telemetry = payload.telemetry;
      live.runtimeState = payload.runtimeState;
      live.reportedState = payload.reportedState;
    }
    return;
  }
  if (event.type === "device.inspection.completed") {
    live.completedAt = Date.now();
    void refreshDevices();
    return;
  }
  if (
    event.type === "device.status.changed" ||
    event.type === "device.inspection.completed"
  )
    void refreshDevices();
}

function scheduleReconnect() {
  if (stopped || retry || !session.online) return;
  const delay = Math.min(15000, 1000 * 2 ** reconnectAttempt++);
  retry = setTimeout(() => {
    retry = null;
    startLive();
  }, delay);
}

export function startLive() {
  if (!session.token || !session.online) return;
  stopped = false;
  if (!heartbeat)
    heartbeat = setInterval(() => {
      live.now = Date.now();
      arrivals = arrivals.filter((at) => live.now - at < 2000);
      const span =
        arrivals.length > 1
          ? (arrivals[arrivals.length - 1]! - arrivals[0]!) / 1000
          : 0;
      live.fps =
        span > 0 ? Math.round(((arrivals.length - 1) / span) * 10) / 10 : 0;
    }, 1000);
  if (!snapshotTimer)
    snapshotTimer = setInterval(() => void refreshDevices(), 5000);
  if (socket || starting) return;
  if (retry) clearTimeout(retry);
  retry = null;
  let task: UniNamespace.SocketTask;
  try {
    starting = true;
    live.connecting = true;
    live.error = "";
    task = uni.connectSocket({ url: socketUrl(), complete: () => {} });
  } catch (error) {
    starting = false;
    live.connecting = false;
    live.error = message(error);
    scheduleReconnect();
    return;
  }
  socket = task;
  const disconnect = (reason: string) => {
    if (socket !== task) return;
    socket = null;
    watchedDevice = "";
    starting = false;
    live.connecting = false;
    live.ready = false;
    live.error = reason;
    if (authTimer) clearTimeout(authTimer);
    authTimer = null;
    try {
      task.close({});
    } catch {
      // 部分 Android 网络错误只触发 onError，不再触发 onClose。
    }
    scheduleReconnect();
  };
  // 包括 TCP 握手在内，防止 onOpen 永远不来的半连接卡住重试。
  authTimer = setTimeout(() => disconnect("实时连接超时，正在重连"), 10000);
  task.onOpen(() => {
    if (socket !== task || stopped) return;
    starting = false;
    task.send({
      data: JSON.stringify({ token: session.token }),
      fail: () => disconnect("实时连接鉴权发送失败"),
    });
    if (socket !== task) return;
    if (authTimer) clearTimeout(authTimer);
    // 连上了但服务器不认 token 时，onClose 也会到；这里兜底避免一直转圈。
    authTimer = setTimeout(() => {
      authTimer = null;
      if (live.ready || socket !== task) return;
      disconnect("实时连接鉴权超时");
    }, 6000);
  });
  task.onMessage((message) => {
    try {
      if (socket === task) {
        const event = JSON.parse(String(message.data)) as PlatformEvent;
        if (event.type === "session.ready") reconnectAttempt = 0;
        handle(event);
      }
    } catch {
      // 非 JSON 帧直接忽略，不让一帧坏数据拆掉整条连接。
    }
  });
  task.onClose((result) => {
    if (socket !== task) return;
    socket = null;
    watchedDevice = "";
    starting = false;
    live.connecting = false;
    live.ready = false;
    if (authTimer) {
      clearTimeout(authTimer);
      authTimer = null;
    }
    // 鉴权失败重连也不会成功，直接回到登录态。
    if (result?.code === 1008) {
      stopLive();
      logout();
      requireLogin();
      return;
    }
    scheduleReconnect();
  });
  task.onError(() => {
    disconnect("实时连接失败，正在重连");
  });
}

export function stopLive() {
  stopped = true;
  if (retry) clearTimeout(retry);
  retry = null;
  if (heartbeat) clearInterval(heartbeat);
  heartbeat = null;
  if (snapshotTimer) clearInterval(snapshotTimer);
  snapshotTimer = null;
  if (authTimer) clearTimeout(authTimer);
  authTimer = null;
  const task = socket;
  socket = null;
  watchedDevice = "";
  starting = false;
  live.ready = false;
  live.connecting = false;
  arrivals = [];
  live.fps = 0;
  try {
    task?.close({});
  } catch {
    // 连接已经断开时 close 会抛错，这里无需处理。
  }
}

/** 采样和详情页共享的“当前帧是否还能用”判断。 */
export function frameUsable(maxAge = 3000) {
  return Boolean(
    live.frame &&
    liveDevice.value?.connectionState === "ONLINE" &&
    Math.max(live.now, Date.now()) - live.lastFrameAt <= maxAge,
  );
}
