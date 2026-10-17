<script setup lang="ts">
import { ref, onUnmounted } from "vue";
import { uid } from "../state";
const message = ref("点击启用实时相机，或使用快门调用系统相机。"),
  active = ref(false);
let stream: MediaStream | null = null,
  video: HTMLVideoElement | null = null;
const hostId = `camera-${uid()}`;
async function start() {
  // #ifdef H5
  try {
    if (!navigator.mediaDevices?.getUserMedia) {
      message.value =
        "当前浏览器环境无法使用实时相机；可点快门调用系统相机或选取原图。";
      return;
    }
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" } },
      audio: false,
    });
    const host = document.getElementById(hostId);
    video = document.createElement("video");
    video.srcObject = stream;
    video.autoplay = true;
    video.playsInline = true;
    video.muted = true;
    video.style.cssText = "width:100%;height:100%;object-fit:cover";
    host?.append(video);
    await video.play();
    active.value = true;
  } catch {
    message.value = "未获得实时相机权限。快门仍可使用系统相机 / 图片选择。";
  }
  // #endif
  // #ifndef H5
  message.value = "点击快门使用系统相机，拍摄后原图将保存到本地队列。";
  // #endif
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
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
  video?.remove();
  video = null;
  active.value = false;
}
onUnmounted(stop);
defineExpose({ capture, stop, start });
</script>
<template>
  <view :id="hostId" class="camera-host"
    ><view v-if="!active" class="camera-placeholder"
      ><text>{{ message || "正在请求相机权限…" }}</text
      ><button
        @click="start"
        style="
          margin-top: 20px;
          background: #424e35;
          color: #eff4e8;
          font-size: 12px;
        "
      >
        启用实时相机
      </button></view
    ></view
  >
</template>
<style scoped>
.camera-host {
  position: absolute;
  inset: 0;
  background: #1b2117;
  overflow: hidden;
}
.camera-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #bdc9ad;
  padding: 40px;
  font-size: 12px;
  line-height: 1.9;
  text-align: center;
}
</style>
