import { reactive } from "vue";
import { session, uid, serverErrorMessage, logout } from "./state";
export interface QueuedSample {
  id: string;
  server: string;
  clientId: string;
  idempotencyKey: string;
  localSequence: number;
  capturedAt: string;
  taskId?: string;
  captureSetClientId?: string;
  source: "MOBILE";
  metadata: Record<string, unknown>;
  path: string;
  status: "QUEUED" | "SYNCING" | "FAILED" | "SYNCED";
  attempts: number;
  nextRetryAt: number;
  error: string | null;
  serverId?: string;
}
const client = (uni.getStorageSync("vision.client") as string) || uid();
uni.setStorageSync("vision.client", client);
export const queue = reactive<{ items: QueuedSample[]; syncing: boolean }>({
  items: ((uni.getStorageSync("vision.queue") as QueuedSample[]) || []).map(
    (i) => (i.status === "SYNCING" ? { ...i, status: "QUEUED" } : i),
  ),
  syncing: false,
});
let retryTimer: ReturnType<typeof setTimeout> | null = null;
const persist = () => uni.setStorageSync("vision.queue", queue.items);
export function updateNote(id: string, note: string) {
  const item = queue.items.find((i) => i.id === id);
  if (item && item.status !== "SYNCED") {
    item.metadata.note = note;
    persist();
  }
}
async function browserDb() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const open = indexedDB.open("field-vision-originals", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("images");
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(new Error("浏览器持久存储不可用"));
  });
}
async function browserStore(id: string, value?: Blob, remove = false) {
  const db = await browserDb();
  return new Promise<Blob | undefined>((resolve, reject) => {
    const transaction = db.transaction(
        "images",
        value || remove ? "readwrite" : "readonly",
      ),
      store = transaction.objectStore("images");
    const operation = remove
      ? store.delete(id)
      : value
        ? store.put(value, id)
        : store.get(id);
    operation.onerror = () => reject(new Error("本地原图保存失败"));
    transaction.oncomplete = () => {
      resolve(operation.result as Blob | undefined);
      db.close();
    };
    transaction.onabort = () => {
      reject(new Error("本地事务失败"));
      db.close();
    };
  });
}
export async function enqueue(
  path: string,
  metadata: Record<string, unknown>,
  captureSetClientId?: string,
) {
  const id = uid();
  let durable = path;
  // #ifdef H5
  const file = await fetch(path).then((r) => r.blob());
  await browserStore(id, file);
  durable = `indexeddb:${id}`;
  // #endif
  // #ifndef H5
  const saved = await uni.saveFile({ tempFilePath: path });
  durable = saved.savedFilePath;
  // #endif
  const sequence = Math.max(
    Number(uni.getStorageSync("vision.sequence") || 0) + 1,
    Date.now() % 2147483647,
  );
  uni.setStorageSync("vision.sequence", sequence);
  const item: QueuedSample = {
    id,
    server: session.server,
    clientId: client,
    idempotencyKey: id,
    localSequence: sequence,
    capturedAt: new Date().toISOString(),
    taskId: session.taskId || undefined,
    captureSetClientId,
    source: "MOBILE",
    metadata,
    path: durable,
    status: "QUEUED",
    attempts: 0,
    nextRetryAt: 0,
    error: null,
  };
  queue.items.push(item);
  persist();
  return item;
}
async function upload(item: QueuedSample) {
  let path = item.path,
    revoke = false;
  // #ifdef H5
  const file = await browserStore(item.id);
  if (!file) throw new Error("原始图像未找到，保留队列项以便检查");
  path = URL.createObjectURL(file);
  revoke = true;
  // #endif
  try {
    const result = await uni.uploadFile({
      url: `${session.server}/api/samples/upload`,
      filePath: path,
      name: "file",
      header: { authorization: `Bearer ${session.token}` },
      formData: {
        metadata: JSON.stringify({
          source: item.source,
          clientId: item.clientId,
          idempotencyKey: item.idempotencyKey,
          localSequence: item.localSequence,
          capturedAt: item.capturedAt,
          taskId: item.taskId,
          captureSetClientId: item.captureSetClientId,
          metadata: item.metadata,
        }),
      },
      timeout: 30000,
    });
    session.serverAvailable = result.statusCode < 500;
    if (result.statusCode === 401) logout();
    if (result.statusCode >= 400) {
      throw new Error(serverErrorMessage(result.data));
    }
    const acknowledgement = JSON.parse(result.data) as { id?: unknown };
    if (typeof acknowledgement.id !== "string")
      throw new Error("INVALID_SERVER_RESPONSE: 未收到样本 ID");
    return { id: acknowledgement.id };
  } finally {
    // #ifdef H5
    if (revoke) URL.revokeObjectURL(path);
    // #endif
  }
}
export async function syncQueue(force = false) {
  if (queue.syncing || !session.online || !session.token) return;
  if (retryTimer) clearTimeout(retryTimer);
  retryTimer = null;
  queue.syncing = true;
  try {
    for (const item of queue.items) {
      if (!session.token || !session.online) break;
      if (
        item.status === "SYNCED" ||
        item.server !== session.server ||
        (!force && Date.now() < item.nextRetryAt)
      )
        continue;
      item.status = "SYNCING";
      item.attempts++;
      persist();
      try {
        const sample = await upload(item);
        item.serverId = sample.id;
        item.status = "SYNCED";
        item.error = null;
        persist();
        try {
          // #ifdef H5
          await browserStore(item.id, undefined, true);
          // #endif
          // #ifndef H5
          await uni.removeSavedFile({ filePath: item.path });
          // #endif
        } catch (cleanupError) {
          item.metadata.cleanupError = String(cleanupError);
          persist();
        }
      } catch (error) {
        item.status = "FAILED";
        item.error = error instanceof Error ? error.message : String(error);
        item.nextRetryAt =
          Date.now() + Math.min(60000, 1000 * 2 ** Math.min(6, item.attempts));
        persist();
      }
    }
  } finally {
    queue.syncing = false;
    persist();
    const waiting = queue.items.filter(
      (i) => i.status !== "SYNCED" && i.server === session.server,
    );
    if (waiting.length && session.online && session.token) {
      const next = Math.min(...waiting.map((i) => i.nextRetryAt));
      retryTimer = setTimeout(
        () => {
          void syncQueue();
        },
        Math.max(1000, next - Date.now()),
      );
    }
  }
}
