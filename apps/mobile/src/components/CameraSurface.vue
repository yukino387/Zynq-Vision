<script setup lang="ts">
import { getCurrentInstance, nextTick, onMounted, onUnmounted, ref } from "vue";
import { onResize } from "@dcloudio/uni-app";
import { uid } from "../state";

const active = ref(false),
  starting = ref(false),
  error = ref("");
const facing = ref<"environment" | "user">("environment");
const torchOn = ref(false),
  torchSupported = ref(false);
const hostId = `camera-${uid()}`;
const instance = getCurrentInstance();
let stream: MediaStream | null = null,
  video: HTMLVideoElement | null = null;
let track: MediaStreamTrack | null = null,
  generation = 0;
let previewTimer: ReturnType<typeof setTimeout> | null = null;
interface NativeCamera {
  preview(): void;
  switchCamera(): void;
  close(): void;
  addEventListener(
    event: string,
    callback: (event: { detail: { code?: number; message?: string } }) => void,
  ): void;
  snapshot(
    success: (event: { tempImagePath: string }) => void,
    fail: (event: { message?: string }) => void,
  ): void;
}
let native: NativeCamera | null = null;

function stop() {
  generation++;
  if (previewTimer) clearTimeout(previewTimer);
  previewTimer = null;
  native?.close();
  native = null;
  stream?.getTracks().forEach((item) => item.stop());
  stream = null;
  track = null;
  video?.remove();
  video = null;
  active.value = false;
  starting.value = false;
  torchOn.value = false;
  torchSupported.value = false;
}
async function start() {
  if (starting.value || active.value) return;
  const attempt = ++generation;
  starting.value = true;
  error.value = "";
  try {
    // #ifdef H5
    if (!navigator.mediaDevices?.getUserMedia)
      throw new Error("实时相机需要 HTTPS 或 localhost");
    const acquired = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: facing.value },
        width: { ideal: 1920 },
        height: { ideal: 1440 },
      },
      audio: false,
    });
    if (attempt !== generation) {
      acquired.getTracks().forEach((item) => item.stop());
      return;
    }
    stream = acquired;
    await nextTick();
    const host = document.getElementById(hostId);
    if (!host) throw new Error("相机尚未就绪");
    const player = document.createElement("video");
    video = player;
    player.srcObject = acquired;
    player.autoplay = true;
    player.playsInline = true;
    player.muted = true;
    player.style.cssText =
      "width:100%;height:100%;object-fit:contain;display:block";
    host.appendChild(player);
    await player.play();
    if (attempt !== generation) return;
    track = acquired.getVideoTracks()[0] ?? null;
    torchSupported.value = Boolean(
      (track?.getCapabilities?.() as { torch?: boolean })?.torch,
    );
    active.value = true;
    starting.value = false;
    // #endif
    // #ifdef APP-PLUS
    if (plus.os.name === "Android") {
      await new Promise<void>((resolve, reject) =>
        plus.android.requestPermissions(
          ["android.permission.CAMERA", "android.permission.RECORD_AUDIO"],
          (result) =>
            result.deniedAlways.length || result.deniedPresent.length
              ? reject(new Error("请允许相机和麦克风权限后重试"))
              : resolve(),
          () => reject(new Error("无法获取相机权限")),
        ),
      );
    }
    if (attempt !== generation) return;
    await nextTick();
    const bounds = await new Promise<{
      left: number;
      top: number;
      width: number;
      height: number;
    }>((resolve) => {
      uni
        .createSelectorQuery()
        .in(instance?.proxy)
        .select(`#${hostId}`)
        .boundingClientRect((rect) =>
          resolve(
            rect as {
              left: number;
              top: number;
              width: number;
              height: number;
            },
          ),
        )
        .exec();
    });
    if (attempt !== generation) return;
    if (!bounds?.width || !bounds.height) throw new Error("相机尚未就绪");
    const camera = plus.video.createLivePusher(hostId, {
      top: `${bounds.top}px`,
      left: `${bounds.left}px`,
      width: `${bounds.width}px`,
      height: `${bounds.height}px`,
      position: "static",
      mode: "FHD",
      aspect: "3:4",
      muted: true,
      "auto-focus": true,
      beauty: 0,
      whiteness: 0,
    }) as unknown as NativeCamera;
    native = camera;
    const pages = getCurrentPages();
    const page = pages[pages.length - 1] as unknown as {
      $getAppWebview(): { append(view: unknown): void };
    };
    page.$getAppWebview().append(camera);
    camera.addEventListener("statechange", (event) => {
      if (attempt !== generation) return;
      if (event.detail.code === 1007) {
        active.value = true;
        starting.value = false;
      }
    });
    camera.addEventListener("error", () => {
      if (attempt !== generation) return;
      stop();
      error.value = "相机启动失败，请重试";
    });
    previewTimer = setTimeout(() => {
      previewTimer = null;
      if (attempt !== generation) return;
      camera.preview();
      if (facing.value === "environment") camera.switchCamera();
    }, 500);
    // #endif
  } catch (e) {
    if (attempt !== generation) return;
    stop();
    error.value =
      (e as { name?: string }).name === "NotAllowedError"
        ? "请在设置中允许相机权限"
        : e instanceof Error
          ? e.message
          : "相机启动失败，请重试";
  }
}
async function flip() {
  if (!active.value) return;
  facing.value = facing.value === "environment" ? "user" : "environment";
  // #ifdef APP-PLUS
  if (native) {
    native.switchCamera();
    return;
  }
  // #endif
  // #ifdef H5
  stop();
  await start();
  // #endif
}
async function toggleTorch() {
  if (!track || !torchSupported.value) return;
  try {
    await track.applyConstraints({
      advanced: [{ torch: !torchOn.value } as MediaTrackConstraintSet],
    });
    torchOn.value = !torchOn.value;
  } catch {
    torchSupported.value = false;
  }
}
async function capture(): Promise<string> {
  if (!active.value) throw new Error("等待相机就绪");
  // #ifdef APP-PLUS
  if (native)
    return new Promise((resolve, reject) =>
      native!.snapshot(
        (event) => resolve(event.tempImagePath),
        (event) => reject(new Error(event.message || "拍摄失败")),
      ),
    );
  // #endif
  // #ifdef H5
  if (video) {
    const player = video;
    if (!player?.videoWidth || player.readyState < 2)
      throw new Error("等待相机画面");
    const canvas = document.createElement("canvas");
    canvas.width = player.videoWidth;
    canvas.height = player.videoHeight;
    canvas.getContext("2d")!.drawImage(player, 0, 0);
    return new Promise((resolve, reject) =>
      canvas.toBlob(
        (blob) =>
          blob
            ? resolve(URL.createObjectURL(blob))
            : reject(new Error("拍摄失败")),
        "image/jpeg",
        0.95,
      ),
    );
  }
  // #endif
  throw new Error("当前平台不支持实时相机");
}
onMounted(() => void start());
onResize(() => {
  stop();
  void start();
});
onUnmounted(stop);
defineExpose({
  capture,
  stop,
  start,
  flip,
  toggleTorch,
  active,
  starting,
  error,
  torchOn,
  torchSupported,
});
</script>

<template>
  <view :id="hostId" class="camera-host">
    <view v-if="!active" class="camera-placeholder">
      <view v-if="starting" class="camera-spinner" />
      <text>{{ starting ? "相机启动中…" : error }}</text>
      <button v-if="!starting" class="camera-retry" @click.stop="start">
        重试
      </button>
    </view>
  </view>
</template>

<style scoped>
.camera-host {
  position: absolute;
  inset: 0;
  background: #102b36;
  overflow: hidden;
}
.camera-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #c9dfe5;
  padding: 24px;
  font-size: 13px;
  text-align: center;
}
.camera-retry {
  min-width: 100px;
  background: #244653;
  color: white;
}
.camera-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #ffffff26;
  border-top-color: #71ddc8;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
