<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { uid } from "../state";

const message = ref("点击快门打开系统相机，拍摄后原图会保存到本机。"),
  error = ref(""),
  active = ref(false),
  starting = ref(false),
  facing = ref<"environment" | "user">("environment"),
  torchOn = ref(false),
  torchSupported = ref(false);
let stream: MediaStream | null = null,
  video: HTMLVideoElement | null = null,
  track: MediaStreamTrack | null = null;
const hostId = `camera-${uid()}`;

async function start() {
  if (starting.value || active.value) return;
  // #ifdef H5
  if (!navigator.mediaDevices?.getUserMedia) {
    error.value = "当前浏览器不支持实时相机，请使用快门调用系统相机。";
    return;
  }
  starting.value = true;
  error.value = "";
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: facing.value },
        width: { ideal: 1920 },
        height: { ideal: 1920 },
      },
      audio: false,
    });
    const host = document.getElementById(hostId);
    if (!host) throw new Error("相机容器未就绪");
    video = document.createElement("video");
    video.srcObject = stream;
    video.autoplay = true;
    video.playsInline = true;
    video.muted = true;
    video.setAttribute("playsinline", "true");
    video.style.cssText =
      "width:100%;height:100%;object-fit:cover;display:block";
    host.appendChild(video);
    await video.play();
    track = stream.getVideoTracks()[0] ?? null;
    const capabilities = (
      track as unknown as {
        getCapabilities?: () => Record<string, unknown>;
      }
    )?.getCapabilities?.();
    torchSupported.value = Boolean(
      (capabilities as { torch?: boolean } | undefined)?.torch,
    );
    active.value = true;
    message.value = "";
  } catch (e) {
    const name = (e as { name?: string })?.name;
    error.value =
      name === "NotAllowedError"
        ? "相机权限未授权。请在浏览器设置中允许相机，或使用快门调用系统相机。"
        : name === "NotFoundError"
          ? "未找到可用相机。仍可使用快门调用系统相机。"
          : "无法启动实时相机，请重试或使用系统相机。";
  } finally {
    starting.value = false;
  }
  // #endif
  // #ifndef H5
  message.value = "点击快门使用系统相机，拍摄后原图将保存到本地队列。";
  // #endif
}

async function flip() {
  if (!active.value) {
    await start();
    return;
  }
  facing.value = facing.value === "environment" ? "user" : "environment";
  stop();
  await start();
}

async function toggleTorch() {
  if (!track || !torchSupported.value) return;
  const next = !torchOn.value;
  try {
    await track.applyConstraints({
      advanced: [{ torch: next } as unknown as MediaTrackConstraintSet],
    });
    torchOn.value = next;
  } catch {
    torchSupported.value = false;
    torchOn.value = false;
  }
}

async function capture(): Promise<string> {
  // #ifdef H5
  if (video && active.value) {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")!.drawImage(video, 0, 0);
    return new Promise((resolve, reject) =>
      canvas.toBlob(
        (blob) =>
          blob
            ? resolve(URL.createObjectURL(blob))
            : reject(new Error("相机帧读取失败")),
        "image/jpeg",
        0.95,
      ),
    );
  }
  // #endif
  const result = await uni.chooseImage({
    count: 1,
    sourceType: ["camera"],
    sizeType: ["original"],
  });
  return result.tempFilePaths[0]!;
}

function stop() {
  stream?.getTracks().forEach((item) => item.stop());
  stream = null;
  track = null;
  video?.remove();
  video = null;
  active.value = false;
  torchOn.value = false;
  torchSupported.value = false;
}

onMounted(() => {
  // #ifdef H5
  void start();
  // #endif
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
      <text class="camera-message">{{
        starting ? "正在启动相机…" : error || message
      }}</text>
      <!-- #ifdef H5 -->
      <button v-if="!starting" class="camera-retry" @click.stop="start">
        {{ error ? "重试相机" : "启用相机" }}
      </button>
      <!-- #endif -->
      <text v-if="error" class="camera-fallback">仍可点快门调用系统相机</text>
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
  gap: 12px;
  color: #c9dfe5;
  padding: 48px 36px;
  font-size: 12px;
  line-height: 1.8;
  text-align: center;
}
.camera-message {
  max-width: 280px;
}
.camera-retry {
  min-width: 132px;
  min-height: 44px;
  border: 1px solid #8b9a7c;
  background: #2a3323;
  color: #f0f8fa;
  font-size: 12px;
  padding: 0 18px;
}
.camera-retry:active {
  background: #3a4630;
}
.camera-fallback {
  font-size: 11px;
  color: #8db0bd;
}
.camera-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #ffffff26;
  border-top-color: #f28b61;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
