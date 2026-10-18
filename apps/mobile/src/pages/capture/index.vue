<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { onShow, onHide } from "@dcloudio/uni-app";
import {
  motionSummary,
  chinese,
  displayName,
  statusTone,
} from "@vision/shared";
import { session, request, notify, uid, captureIdentity } from "../../state";
import { enqueue, syncQueue, queue } from "../../queue";
import {
  live,
  liveDevice,
  frameUsable,
  refreshDevices,
  setDevice,
  startLive,
} from "../../live";
import CameraSurface from "../../components/CameraSurface.vue";
import LiveFeed from "../../components/LiveFeed.vue";

type Mode = "BOARD" | "MOBILE" | "SYNC";
const stored = uni.getStorageSync("vision.captureMode") as Mode;
const mode = ref<Mode>(
  stored === "BOARD" || stored === "MOBILE" || stored === "SYNC"
    ? stored
    : "BOARD",
);
const camera = ref<InstanceType<typeof CameraSurface> | null>(null),
  motion = ref<{
    motionScore: number;
    pitch: number | null;
    roll: number | null;
    captureStability: string;
  } | null>(null),
  imuAvailable = ref(false),
  busy = ref(false),
  error = ref(""),
  lastResult = ref(""),
  lastInspection = ref<{ id: string; result: string } | null>(null),
  visible = ref(false),
  showSettings = ref(false),
  lastShot = ref(""),
  flash = ref(false);

const modes = [
  { key: "BOARD", label: "板端" },
  { key: "MOBILE", label: "手机" },
  { key: "SYNC", label: "同步" },
] as const;
const device = computed(() => liveDevice.value),
  detections = computed(() => live.frame?.detections ?? null);
const modeLabel = computed(
  () => modes.find((item) => item.key === mode.value)?.label ?? "板端",
);
const sourceName = computed(() =>
  mode.value === "MOBILE"
    ? "手机相机"
    : displayName(device.value?.name ?? "选择设备"),
);
const posture = computed(() => {
  if (!imuAvailable.value || !motion.value)
    return { label: "传感器不可用", tone: "unknown" };
  if (
    Math.abs(motion.value.roll ?? 0) > 15 ||
    Math.abs(motion.value.pitch ?? 0) > 30
  )
    return { label: "倾斜", tone: "tilt" };
  return motion.value.captureStability === "STABLE"
    ? { label: "稳定", tone: "stable" }
    : { label: "移动中", tone: "motion" };
});
const pending = computed(
  () => queue.items.filter((i) => i.status !== "SYNCED").length,
);
const verdict = computed(() => {
  if (mode.value === "MOBILE") return null;
  if (!live.frame) return { text: "等待设备画面", detail: "连接后自动显示" };
  if (detections.value === null)
    return { text: "仅图像", detail: "本帧没有推理输出" };
  if (detections.value.length)
    return {
      text: "待复核",
      detail: `${detections.value.length} 处候选目标`,
      candidate: true,
    };
  return { text: "未检出缺陷", detail: "本帧没有候选目标" };
});
const captureBlocked = computed(() => {
  if (busy.value) return "正在保存采样…";
  if (mode.value === "MOBILE") return "";
  if (!device.value) return "请先在任务与设备中选择设备";
  if (device.value.connectionState !== "ONLINE")
    return "设备离线；请工程师在 Web 端连接设备";
  if (!frameUsable()) return "等待设备返回完整画面";
  return "";
});
const shutterHint = computed(() => {
  if (captureBlocked.value) return captureBlocked.value;
  if (mode.value === "SYNC") return "手机与板端各拍一张，归入同一采样组";
  if (mode.value === "BOARD") return "保存设备当前帧与检测记录";
  return "保存原始图像到本机，联网后同步";
});

let accel = { x: 0, y: 0, z: 0 };
const gyro = (v: { x: number; y: number; z: number }) => {
  imuAvailable.value = true;
  const roll = (Math.atan2(accel.y, accel.z) * 180) / Math.PI,
    pitch =
      (Math.atan2(-accel.x, Math.hypot(accel.y, accel.z)) * 180) / Math.PI;
  motion.value = motionSummary(v.x, v.y, v.z, pitch, roll);
};
const accelerometer = (v: UniApp.OnAccelerometerChangeSuccess) => {
  accel = v;
};

function setMode(value: string) {
  if (busy.value) return;
  if (value === "BOARD" || value === "MOBILE" || value === "SYNC")
    mode.value = value;
}
function goHome() {
  uni.switchTab({ url: "/pages/home/index" });
}
function openRecords() {
  uni.switchTab({ url: "/pages/records/index" });
}
function openSync() {
  uni.navigateTo({ url: "/pages/sync/index" });
}
function openTasks() {
  showSettings.value = false;
  uni.switchTab({ url: "/pages/tasks/index" });
}
function openLive() {
  uni.navigateTo({ url: "/pages/live/index" });
}

watch(mode, (value) => {
  uni.setStorageSync("vision.captureMode", value);
  lastInspection.value = null;
  lastResult.value = "";
  error.value = "";
  if (value !== "MOBILE") void refreshDevices();
});

onShow(async () => {
  visible.value = true;
  uni.hideTabBar({ animation: false, fail: () => {} });
  if (!session.token) {
    uni.navigateTo({ url: "/pages/login/index" });
    return;
  }
  startLive();
  void refreshDevices();
  try {
    uni.startAccelerometer({
      interval: "ui",
      success: () => uni.onAccelerometerChange(accelerometer),
      fail: () => {},
    });
    uni.startGyroscope({
      interval: "ui",
      success: () => uni.onGyroscopeChange(gyro),
      fail: () => {
        imuAvailable.value = false;
      },
    });
  } catch {
    imuAvailable.value = false;
  }
});
onHide(() => {
  visible.value = false;
  camera.value?.stop();
  showSettings.value = false;
  uni.showTabBar({ animation: false, fail: () => {} });
  try {
    uni.stopAccelerometer({ fail: () => {} });
    uni.stopGyroscope({ fail: () => {} });
    uni.offAccelerometerChange(accelerometer);
    uni.offGyroscopeChange?.();
  } catch {
    // H5 没有传感器时停止接口也可能失败。
  }
});

function pickDevice() {
  if (!live.devices.length) {
    void refreshDevices();
    return;
  }
  uni.showActionSheet({
    itemList: live.devices.map(
      (d) => `${displayName(d.name)} · ${chinese(d.connectionState)}`,
    ),
    success: (result) => {
      const next = live.devices[result.tapIndex];
      if (next) setDevice(next.id);
    },
  });
}
async function board(captureSetClientId?: string) {
  if (!device.value?.capabilities.capture)
    throw new Error("设备不支持采样或尚未选择设备");
  const identity = captureIdentity("mobile-board");
  return request<{ id: string; inspections: { id: string; result: string }[] }>(
    "/samples/capture",
    "POST",
    {
      deviceId: device.value.id,
      clientId: identity.clientId,
      idempotencyKey: uid(),
      localSequence: identity.localSequence,
      taskId: session.taskId || undefined,
      captureSetClientId,
    },
  );
}
async function capture() {
  if (busy.value || captureBlocked.value) return;
  busy.value = true;
  error.value = "";
  lastResult.value = "";
  lastInspection.value = null;
  const capturing = mode.value;
  const captureSet = capturing === "SYNC" ? uid() : undefined;
  try {
    if (capturing !== "BOARD") {
      if (!camera.value) throw new Error("相机尚未准备就绪，请稍后重试");
      flash.value = true;
      setTimeout(() => {
        flash.value = false;
      }, 140);
      const path = await camera.value.capture();
      lastShot.value = path;
      const system = uni.getSystemInfoSync();
      await enqueue(
        path,
        {
          orientation: system.deviceOrientation ?? "UNKNOWN",
          deviceModel: system.model,
          appVersion: "0.2.0",
          imu: imuAvailable.value ? motion.value : null,
          imuAvailable: imuAvailable.value,
          cameraMetadata: {
            method: "system camera or browser getUserMedia",
            timestamp: new Date().toISOString(),
          },
          note: "",
          captureSetClientId: captureSet,
        },
        captureSet,
      );
      lastResult.value = "手机原图已保存到本地队列";
      if (session.online) void syncQueue();
    }
    if (capturing !== "MOBILE") {
      if (!frameUsable())
        throw new Error("设备画面不可用；等待实时画面恢复后再采样");
      const sample = await board(captureSet);
      lastInspection.value = sample.inspections[0] ?? null;
      lastResult.value += `${lastResult.value ? " · " : ""}板端采样已保存`;
    }
    try {
      uni.vibrateShort({ fail: () => {} });
    } catch {
      // 桌面浏览器没有震动。
    }
    uni.showToast({ title: "采样已保存", icon: "success" });
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <view class="capture-page">
    <view class="camera-stage">
      <view v-if="flash" class="flash-overlay" />
      <LiveFeed
        v-if="mode !== 'MOBILE'"
        minimal
        fit="aspectFit"
        expandable
        @expand="openLive"
      />
      <CameraSurface v-else-if="visible" ref="camera" />
      <view v-if="mode === 'SYNC' && visible" class="pip">
        <CameraSurface ref="camera" />
        <text class="pip-label">手机</text>
      </view>

      <view v-if="mode === 'MOBILE'" class="guide-frame">
        <view class="corner tl" /><view class="corner tr" />
        <view class="corner bl" /><view class="corner br" />
        <text>采样区域</text>
      </view>

      <view class="top-bar">
        <view class="top-left">
          <button class="close-btn" aria-label="返回首页" @click="goHome">
            ×
          </button>
          <view class="top-copy">
            <text class="top-title">现场采样</text>
            <text class="top-sub"
              >{{ modeLabel }} ·
              {{
                session.online && session.serverAvailable
                  ? "已连接"
                  : "离线模式"
              }}</text
            >
          </view>
        </view>
        <view class="top-actions">
          <button
            v-if="mode === 'MOBILE' && camera?.torchSupported"
            class="round-btn"
            :class="{ on: camera?.torchOn }"
            aria-label="闪光灯"
            @click="camera?.toggleTorch()"
          >
            ☀
          </button>
          <button class="task-btn" @click="showSettings = true">
            <text>{{ session.taskId ? "已关联任务" : "独立采样" }}</text>
          </button>
        </view>
      </view>

      <view class="source-chip">
        <view
          class="source-dot"
          :class="
            mode === 'MOBILE' ? 'live' : statusTone(device?.connectionState)
          "
        />
        <text class="source-name">{{ sourceName }}</text>
        <text
          v-if="mode !== 'MOBILE' && device?.connectionState === 'ONLINE'"
          class="source-meta mono"
          >{{ live.fps.toFixed(1) }}fps</text
        >
      </view>

      <view
        v-if="mode !== 'MOBILE' && verdict"
        class="verdict-overlay"
        :class="{ candidate: verdict.candidate }"
      >
        <text class="verdict-text">{{ verdict.text }}</text>
        <text class="verdict-detail">{{ verdict.detail }}</text>
      </view>

      <view v-if="mode !== 'BOARD'" class="posture-chip" :class="posture.tone">
        <view class="posture-dot" /><text>{{ posture.label }}</text>
      </view>

      <view
        v-if="error || lastInspection || lastResult"
        class="result-overlay"
        :class="{ error: !!error }"
        @click="
          lastInspection &&
          uni.navigateTo({
            url: `/pages/detail/index?id=${lastInspection.id}`,
          })
        "
      >
        <view v-if="error" class="result-copy">
          <text v-if="lastResult" class="result-kicker">{{ lastResult }}</text>
          <text class="result-text">{{ error }}</text>
        </view>
        <template v-else-if="lastInspection">
          <view class="result-copy">
            <text class="result-kicker">板端采样已保存</text>
            <text class="result-title"
              >检测结果 {{ chinese(lastInspection.result) }}</text
            >
          </view>
          <text class="result-link">查看 →</text>
        </template>
        <text v-else class="result-text">{{ lastResult }}</text>
      </view>
    </view>

    <view class="camera-controls">
      <view class="mode-switch">
        <text
          v-for="m in modes"
          :key="m.key"
          :class="{ active: mode === m.key }"
          @click="setMode(m.key)"
          >{{ m.label }}</text
        >
      </view>
      <view class="shutter-row">
        <button class="side-slot" @click="openSync">
          <image
            v-if="lastShot"
            :src="lastShot"
            class="last-shot"
            mode="aspectFill"
          />
          <template v-else>
            <text class="side-num mono">{{ pending }}</text>
            <text class="side-label">待同步</text>
          </template>
        </button>
        <button
          class="shutter"
          :disabled="busy || !!captureBlocked"
          :loading="busy"
          aria-label="采样快门"
          @click="capture"
        >
          <view />
        </button>
        <button
          class="side-slot"
          @click="
            mode === 'MOBILE' && camera?.active ? camera.flip() : openRecords()
          "
        >
          <text class="side-symbol">{{
            mode === "MOBILE" && camera?.active ? "⇄" : "记录"
          }}</text>
          <text class="side-label">{{
            mode === "MOBILE" && camera?.active ? "翻转" : "检测记录"
          }}</text>
        </button>
      </view>
      <text class="shutter-hint">{{ shutterHint }}</text>
    </view>

    <view
      v-if="showSettings"
      class="sheet-backdrop"
      @click="showSettings = false"
    />
    <view v-if="showSettings" class="settings-sheet">
      <view class="sheet-head">
        <text>任务与设备</text>
        <text class="sheet-done" @click="showSettings = false">完成</text>
      </view>
      <view class="sheet-row" @click="pickDevice">
        <text class="sheet-label">采样设备</text>
        <text class="sheet-value">{{
          mode === "MOBILE"
            ? "手机相机"
            : displayName(device?.name ?? "选择设备")
        }}</text>
      </view>
      <button class="sheet-action" @click="openTasks">
        {{ session.taskId ? "更换关联任务" : "选择采样任务" }} →
      </button>
      <text class="sheet-note">{{
        session.taskId
          ? "当前采样会归入已选任务"
          : "未关联任务，样本将作为独立采样保存"
      }}</text>
      <view class="sheet-links">
        <text @click="openSync">{{ pending }} 个待同步 →</text>
        <text @click="openRecords">检测记录 →</text>
        <text v-if="mode !== 'MOBILE'" @click="openLive">实时画面 →</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.capture-page {
  position: relative;
  height: 100vh;
  min-height: 100vh;
  overflow: hidden;
  background: #102b36;
  color: #f0f8fa;
}
.camera-stage {
  position: absolute;
  inset: 0;
  background: #102b36;
  overflow: hidden;
}
.flash-overlay {
  position: absolute;
  inset: 0;
  z-index: 30;
  background: #ffffff;
  pointer-events: none;
  animation: shutter-flash 140ms ease-out;
}
@keyframes shutter-flash {
  from {
    opacity: 0.95;
  }
  to {
    opacity: 0;
  }
}
.camera-stage :deep(.hud-top) {
  display: none;
}
.camera-stage :deep(.live-feed) {
  background: #102b36;
}
.pip {
  position: absolute;
  right: 14px;
  top: calc(122px + env(safe-area-inset-top));
  width: 116px;
  height: 116px;
  border: 1px solid #ffffff66;
  overflow: hidden;
  background: #102b36;
  z-index: 4;
}
.pip-label {
  position: absolute;
  left: 0;
  bottom: 0;
  background: #102b36cc;
  color: #d9e9ed;
  font-size: 11px;
  padding: 2px 5px;
}
.guide-frame {
  position: absolute;
  left: 8%;
  top: 16%;
  width: 84%;
  aspect-ratio: 1 / 1;
  border: 1px solid #e5ebd640;
  pointer-events: none;
  z-index: 2;
}
.guide-frame > text {
  position: absolute;
  left: 9px;
  top: 9px;
  font:
    9px Consolas,
    monospace;
  letter-spacing: 1px;
  color: #dfe7d2;
  background: #17343eb0;
  padding: 3px 5px;
}
.corner {
  position: absolute;
  width: 22px;
  height: 22px;
  border: 2px solid #f0f8facc;
}
.corner.tl {
  left: -1px;
  top: -1px;
  border-right: 0;
  border-bottom: 0;
}
.corner.tr {
  right: -1px;
  top: -1px;
  border-left: 0;
  border-bottom: 0;
}
.corner.bl {
  left: -1px;
  bottom: -1px;
  border-right: 0;
  border-top: 0;
}
.corner.br {
  right: -1px;
  bottom: -1px;
  border-left: 0;
  border-top: 0;
}
.top-bar {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  z-index: 6;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: calc(12px + env(safe-area-inset-top)) 16px 34px;
  background: linear-gradient(#000000b8 0%, #00000066 55%, transparent 100%);
  pointer-events: none;
}
.top-left,
.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  pointer-events: auto;
}
.top-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.top-title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.3px;
}
.top-sub {
  font-size: 11px;
  color: #b8c4ad;
}
.close-btn,
.round-btn {
  width: 38px;
  height: 38px;
  min-height: 38px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid #ffffff38;
  background: #102b3666;
  color: #f0f8fa;
  font-size: 22px;
  line-height: 36px;
  text-align: center;
}
.round-btn {
  font-size: 16px;
}
.round-btn.on {
  background: #f28b61;
  border-color: #f28b61;
  color: #17343e;
}
.task-btn {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 19px;
  border: 1px solid #ffffff38;
  background: #102b3666;
  color: #f0f8fa;
  font-size: 11px;
}
.source-chip {
  position: absolute;
  left: 16px;
  top: calc(76px + env(safe-area-inset-top));
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: calc(100% - 120px);
  padding: 5px 8px;
  background: #102b36b8;
  border: 1px solid #ffffff24;
  font-size: 11px;
  color: #c9dfe5;
}
.source-dot {
  width: 6px;
  height: 6px;
  background: #8d978a;
  flex: none;
}
.source-dot.live,
.source-dot.ok {
  background: #71ddc8;
}
.source-dot.warn {
  background: #e0b764;
}
.source-dot.crit {
  background: #d9765c;
}
.source-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-meta {
  color: #8db0bd;
  white-space: nowrap;
}
.verdict-overlay {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 226px;
  z-index: 4;
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 11px;
  background: #102b36c4;
  border-left: 3px solid #71ddc8;
  backdrop-filter: blur(6px);
}
.verdict-overlay.candidate {
  border-left-color: #e0b764;
  background: #3b3326d0;
}
.verdict-text {
  font-size: 14px;
  font-weight: 600;
}
.verdict-overlay.candidate .verdict-text {
  color: #e8c27c;
}
.verdict-detail {
  font-size: 11px;
  color: #aac6d0;
}
.posture-chip {
  position: absolute;
  right: 16px;
  top: calc(76px + env(safe-area-inset-top));
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  background: #102b36b8;
  border: 1px solid #ffffff24;
  font-size: 11px;
  color: #c9dfe5;
}
.posture-dot {
  width: 6px;
  height: 6px;
  background: #a7b596;
}
.posture-chip.stable .posture-dot {
  background: #71ddc8;
}
.posture-chip.motion .posture-dot,
.posture-chip.tilt .posture-dot {
  background: #efb761;
}
.result-overlay {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 286px;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: #eef2e8e8;
  color: #17343e;
  border-left: 3px solid #8fb47d;
  backdrop-filter: blur(6px);
}
.result-overlay.error {
  background: #f3e1dae8;
  border-left-color: #a5321a;
}
.result-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.result-kicker {
  font-size: 11px;
  color: #637d87;
}
.result-title {
  font-size: 12px;
}
.result-text {
  font-size: 11px;
  line-height: 1.6;
}
.result-link {
  font-size: 11px;
  color: #087f82;
  white-space: nowrap;
}
.camera-controls {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 7;
  padding: 48px 20px calc(16px + env(safe-area-inset-bottom));
  background: linear-gradient(
    transparent 0%,
    #0b2029b8 30%,
    #0b2029f2 65%,
    #0b2029 100%
  );
}
.mode-switch {
  display: flex;
  justify-content: center;
  gap: 2px;
  margin-bottom: 16px;
}
.mode-switch text {
  min-width: 58px;
  min-height: 30px;
  line-height: 30px;
  padding: 0 12px;
  text-align: center;
  font-size: 11px;
  color: #aac6d0;
  border: 1px solid #ffffff2e;
  background: #102b3666;
}
.mode-switch text.active {
  background: #f0f8fa;
  color: #17343e;
  border-color: #f0f8fa;
  font-weight: 600;
}
.shutter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.side-slot {
  width: 66px;
  height: 66px;
  min-height: 66px;
  padding: 0;
  border: 1px solid #ffffff38;
  border-radius: 12px;
  background: #102b3666;
  color: #d9e9ed;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  overflow: hidden;
}
.side-num {
  font-size: 19px;
  line-height: 1.1;
}
.side-label {
  font-size: 11px;
  color: #aac6d0;
}
.side-symbol {
  font-size: 16px;
  line-height: 1.2;
}
.last-shot {
  width: 100%;
  height: 100%;
  display: block;
}
.shutter {
  width: 84px;
  height: 84px;
  min-height: 84px;
  border-radius: 50%;
  border: 2px solid #f28b61;
  background: transparent;
  padding: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.shutter view {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #f28b61;
}
.shutter:active:not([disabled]) view {
  background: #076b6e;
  transform: scale(0.96);
}
.shutter[disabled] {
  opacity: 0.4;
}
.shutter-hint {
  display: block;
  margin-top: 12px;
  text-align: center;
  font-size: 11px;
  color: #aac6d0;
}
.sheet-backdrop {
  position: absolute;
  inset: 0;
  z-index: 20;
  background: #00000080;
}
.settings-sheet {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 21;
  padding: 18px 20px calc(20px + env(safe-area-inset-bottom));
  background: #ffffff;
  color: #17343e;
  border-radius: 14px 14px 0 0;
}
.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid #dce6e9;
  font-size: 15px;
  font-weight: 600;
}
.sheet-done {
  font-size: 11px;
  color: #087f82;
  font-weight: 400;
}
.sheet-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid #e6edef;
}
.sheet-label {
  font-size: 11px;
  color: #637d87;
}
.sheet-value {
  font-size: 12px;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sheet-action {
  width: 100%;
  margin-top: 14px;
  border: 1px solid #dce6e9;
  background: #f7fafb;
  color: #365661;
  font-size: 12px;
  min-height: 46px;
  text-align: left;
  padding: 0 13px;
}
.sheet-note {
  display: block;
  margin-top: 9px;
  font-size: 11px;
  color: #637d87;
  line-height: 1.6;
}
.sheet-links {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-top: 16px;
  font-size: 11px;
  color: #087f82;
}

.capture-page {
  height: 100vh;
  height: 100dvh;
  min-height: 0;
}
.task-btn {
  min-height: 44px;
  border-radius: 22px;
  font-size: 12px;
}
.close-btn,
.round-btn {
  min-height: 44px;
  min-width: 44px;
}
.source-chip,
.posture-chip {
  border-radius: 20px;
  padding: 7px 10px;
}
.source-chip {
  max-width: calc(100% - 148px);
}
.verdict-overlay {
  border-radius: 12px;
  bottom: calc(246px + env(safe-area-inset-bottom));
}
.result-overlay {
  border-radius: 12px;
  bottom: calc(306px + env(safe-area-inset-bottom));
}
.result-overlay.error {
  color: #ab443f;
}
.mode-switch {
  gap: 6px;
}
.mode-switch text {
  border-radius: 22px;
  min-height: 44px;
  line-height: 42px;
  min-width: 70px;
  font-size: 13px;
}
.side-slot {
  border-radius: 18px;
}
.shutter {
  box-shadow: 0 0 0 6px #f28b6110;
}
.shutter[disabled] {
  background: transparent;
}
.shutter-hint {
  font-size: 12px;
  min-height: 20px;
}
.settings-sheet {
  border-radius: 24px 24px 0 0;
  max-height: 82%;
  overflow-y: auto;
}
.sheet-head {
  padding-bottom: 16px;
}
.sheet-done {
  padding: 8px 0 8px 18px;
  font-size: 13px;
}
.sheet-row {
  padding: 18px 0;
}
.sheet-label,
.sheet-note {
  font-size: 12px;
}
.sheet-value,
.sheet-action {
  font-size: 14px;
}
.sheet-links {
  font-size: 13px;
  gap: 10px 20px;
}
.sheet-links > text {
  padding: 8px 0;
}
@media (max-height: 680px) {
  .guide-frame {
    top: 21%;
    width: 66%;
    left: 17%;
  }
  .camera-controls {
    padding-top: 30px;
  }
}
</style>
