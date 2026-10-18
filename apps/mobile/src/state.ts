import { reactive } from "vue";
import { errorMessage } from "@vision/shared";
import type { Role, DeviceSnapshot, Page, Task } from "@vision/contracts";
export function uid() {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `mobile-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
  );
}
/** 板端采样身份：同一台手机固定 clientId，localSequence 递增。
 *  服务端按 (clientId, localSequence) 唯一，重复用 0 会 409。 */
export function captureIdentity(prefix: string) {
  let client = uni.getStorageSync("vision.client") as string;
  if (!client) {
    client = uid();
    uni.setStorageSync("vision.client", client);
  }
  const stored = Number(uni.getStorageSync("vision.boardSequence") || 0);
  // 时间基准兜底：即使本地存储被清空，也不会再撞上历史 (clientId, localSequence)。
  const localSequence = Math.max(stored + 1, Date.now() % 2147483647);
  uni.setStorageSync("vision.boardSequence", localSequence);
  return { clientId: `${prefix}-${client}`, localSequence };
}
const initialServer = () => {
  let origin = "";
  // #ifdef H5
  origin = /^https?:$/.test(location.protocol) ? location.origin : "";
  // #endif
  return (uni.getStorageSync("vision.server") as string) || origin;
};
export const session = reactive({
  server: initialServer(),
  token: (uni.getStorageSync("vision.token") as string) || "",
  user: uni.getStorageSync("vision.user") as {
    id: string;
    name: string;
    role: Role;
  } | null,
  stationId: (uni.getStorageSync("vision.station") as string) || "",
  deviceId: (uni.getStorageSync("vision.device") as string) || "",
  taskId: (uni.getStorageSync("vision.task") as string) || "",
  online: true,
  serverAvailable: true,
  error: "",
});
export function setServer(server: string) {
  const next = server.trim().replace(/\/+$/, "");
  if (!/^https?:\/\/[^\s/?#]+$/i.test(next))
    throw new Error("请输入完整服务器地址，例如 http://192.168.1.100:3000");
  if (session.server !== next) {
    logout();
    session.stationId = "";
    session.deviceId = "";
    session.taskId = "";
    for (const key of ["vision.station", "vision.device", "vision.task"])
      uni.removeStorageSync(key);
  }
  session.server = next;
  uni.setStorageSync("vision.server", session.server);
}
export function selectTask(id: string) {
  session.taskId = id;
  uni.setStorageSync("vision.task", id);
}
export function requireLogin() {
  if (!session.token) {
    const pages = getCurrentPages();
    if (pages[pages.length - 1]?.route !== "pages/login/index")
      uni.navigateTo({ url: "/pages/login/index" });
    return false;
  }
  return true;
}
export function serverErrorMessage(value: unknown): string {
  let body = value;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body) as unknown;
    } catch {
      body = null;
    }
  }
  const error =
    body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  return errorMessage(error.code ?? "SERVER_UNREACHABLE", error.message);
}
export async function request<T>(
  path: string,
  method: "GET" | "POST" = "GET",
  data?: unknown,
): Promise<T> {
  let received = false;
  try {
    const response = await uni.request({
      url: `${session.server}/api${path}`,
      method,
      data: data as Record<string, unknown> | undefined,
      header: {
        authorization: `Bearer ${session.token}`,
        "content-type": "application/json",
      },
      timeout: 12000,
    });
    received = true;
    session.serverAvailable = response.statusCode < 500;
    if (response.statusCode >= 400) {
      if (response.statusCode === 401) {
        logout();
        requireLogin();
      }
      throw new Error(serverErrorMessage(response.data));
    }
    session.online = true;
    return response.data as T;
  } catch (error) {
    if (!received) session.serverAvailable = false;
    throw error instanceof Error
      ? error
      : new Error("服务器不可达，请检查局域网连接");
  }
}
export async function login(username: string, password: string) {
  const result = await request<{ token: string; user: typeof session.user }>(
    "/auth/login",
    "POST",
    { username, password },
  );
  session.token = result.token;
  session.user = result.user;
  uni.setStorageSync("vision.token", result.token);
  uni.setStorageSync("vision.user", result.user);
}
export async function register(body: {
  code: string;
  name: string;
  username: string;
  password: string;
}) {
  const result = await request<{ token: string; user: typeof session.user }>(
    "/auth/register",
    "POST",
    body,
  );
  session.token = result.token;
  session.user = result.user;
  uni.setStorageSync("vision.token", result.token);
  uni.setStorageSync("vision.user", result.user);
}
export async function devices() {
  return request<DeviceSnapshot[]>("/devices/snapshot");
}
export type { Task } from "@vision/contracts";
export const tasks = () =>
  request<Page<Task>>(
    `/tasks${session.stationId ? `?stationId=${encodeURIComponent(session.stationId)}` : ""}`,
  );
export function notify(error: unknown) {
  session.error = error instanceof Error ? error.message : String(error);
  uni.showToast({ title: session.error, icon: "none", duration: 3500 });
}
export function logout() {
  session.token = "";
  session.user = null;
  uni.removeStorageSync("vision.token");
  uni.removeStorageSync("vision.user");
}
