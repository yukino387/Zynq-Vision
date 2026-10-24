<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { onShow, onHide } from "@dcloudio/uni-app";
import { motionSummary, displayName } from "@vision/shared";
import {
  session,
  request,
  notify,
  uid,
  captureIdentity,
  selectTask,
} from "../../state";
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
    : "MOBILE",
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
  lastSample = ref(""),
  visible = ref(false),
  showSettings = ref(false),
  lastShot = ref(""),
  flash = ref(false);

const modes = [
  { key: "BOARD", label: "板端" },
  { key: "MOBILE", label: "手机" },
  { key: "SYNC", label: "双机" },
] as const;
const device = computed(() => liveDevice.value);
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
const captureBlocked = computed(() => {
  if (busy.value) return "保存中…";
  if (mode.value !== "BOARD" && !camera.value?.active)
    return camera.value?.error || "等待相机就绪";
  if (mode.value === "MOBILE") return "";
  if (!device.value) return "请选择设备";
  if (!device.value.capabilities.capture) return "设备不支持采样";
  if (device.value.connectionState !== "ONLINE") return "设备离线";
  if (!frameUsable()) return "等待实时画面";
  return "";
});
const shutterHint = computed(
  () =>
    captureBlocked.value || (mode.value === "SYNC" ? "双机留样" : "轻点拍摄"),
);
function releaseShot() {
  // #ifdef H5
  if (lastShot.value.startsWith("blob:")) URL.revokeObjectURL(lastShot.value);
  // #endif
  lastShot.value = "";
}

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
function openLastSample() {
  if (lastSample.value)
    uni.navigateTo({ url: `/pages/sample/index?id=${lastSample.value}` });
  else openSync();
}
function openLive() {
  uni.navigateTo({ url: "/pages/live/index" });
}

watch(mode, (value) => {
  uni.setStorageSync("vision.captureMode", value);
  lastSample.value = "";
  lastResult.value = "";
  error.value = "";
  if (value !== "MOBILE") void refreshDevices();
});

onShow(async () => {
  visible.value = !!session.token;
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
  releaseShot();
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
      (d) =>
        `${displayName(d.name)} · ${d.connectionState === "ONLINE" ? "在线" : "离线"}`,
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
  return request<{ id: string }>("/samples/capture", "POST", {
    deviceId: device.value.id,
    clientId: identity.clientId,
    idempotencyKey: uid(),
    localSequence: identity.localSequence,
    taskId: session.taskId || undefined,
    captureSetClientId,
    planId: session.taskId
      ? undefined
      : device.value.terminal?.state?.product?.id,
  });
}
async function capture() {
  if (busy.value || captureBlocked.value) return;
  busy.value = true;
  error.value = "";
  lastResult.value = "";
  lastSample.value = "";
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
      releaseShot();
      lastShot.value = path;
      const system = uni.getSystemInfoSync();
      await enqueue(
        path,
        {
          orientation: system.deviceOrientation ?? "UNKNOWN",
          deviceModel: system.model,
          appVersion: "0.2.1",
          planId: session.taskId
            ? undefined
            : device.value?.terminal?.state?.product?.id,
          imu: imuAvailable.value ? motion.value : null,
          imuAvailable: imuAvailable.value,
          cameraMetadata: {
            method: "live camera snapshot",
            timestamp: new Date().toISOString(),
          },
          note: "",
          captureSetClientId: captureSet,
        },
        captureSet,
      );
      lastResult.value = "手机样本已保存";
      if (session.online) void syncQueue();
    }
    if (capturing !== "MOBILE") {
      if (!frameUsable())
        throw new Error("设备画面不可用；等待实时画面恢复后再采样");
      const sample = await board(captureSet);
      lastSample.value = sample.id;
      lastResult.value += `${lastResult.value ? " · " : ""}板端采样已保存`;
    }
    try {
      uni.vibrateShort({ fail: () => {} });
    } catch {
      // 桌面浏览器没有震动。
    }
    uni.showToast({ title: "已保存", icon: "success" });
    setTimeout(() => {
      lastResult.value = "";
    }, 2500);
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
    <view class="top-bar">
      <button class="round" aria-label="返回首页" @click="goHome">×</button>
      <view class="heading"
        ><text>采样</text><text class="muted-copy">{{ sourceName }}</text></view
      >
      <button class="task-btn" :disabled="busy" @click="showSettings = true">
        {{ session.taskId ? "当前任务" : "任务 / 设备" }}
      </button>
    </view>
    <view class="source-row">
      <text class="source-label"
        >{{ modeLabel }} ·
        {{
          mode === "MOBILE"
            ? camera?.active
              ? "实时取景"
              : "准备中"
            : frameUsable()
              ? "实时"
              : "等待画面"
        }}</text
      >
      <button
        v-if="mode !== 'BOARD' && camera?.torchSupported"
        class="light-btn"
        @click="camera?.toggleTorch()"
      >
        {{ camera?.torchOn ? "关灯" : "补光" }}
      </button>
      <text v-else-if="mode !== 'BOARD' && imuAvailable" class="source-label">{{
        posture.label
      }}</text>
    </view>
    <view class="viewfinder">
      <LiveFeed v-if="visible && mode !== 'MOBILE'" minimal fit="aspectFit" />
      <CameraSurface
        v-if="visible && !showSettings && mode === 'MOBILE'"
        ref="camera"
      />
      <view v-if="flash" class="flash" />
    </view>
    <view v-if="mode === 'SYNC'" class="pip">
      <CameraSurface v-if="visible && !showSettings" ref="camera" />
    </view>
    <view class="camera-controls">
      <view
        class="feedback"
        :class="{ error: !!error }"
        @click="openLastSample"
      >
        <text>{{ error || lastResult }}</text
        ><text v-if="lastSample && lastResult">查看 ›</text>
      </view>
      <view class="mode-switch">
        <button
          v-for="m in modes"
          :key="m.key"
          :class="{ active: mode === m.key }"
          :disabled="busy"
          @click="setMode(m.key)"
        >
          {{ m.label }}
        </button>
      </view>
      <view class="shutter-row">
        <button class="side" aria-label="最近采样" @click="openLastSample">
          <image v-if="lastShot" :src="lastShot" mode="aspectFill" />
          <text v-else>{{ pending ? `${pending} 待上传` : "样本" }}</text>
        </button>
        <button
          class="shutter"
          :disabled="!!captureBlocked"
          :loading="busy"
          aria-label="拍摄样本"
          @click="capture"
        >
          <view />
        </button>
        <button
          class="side"
          :disabled="busy"
          :aria-label="mode === 'BOARD' ? '检测记录' : '翻转相机'"
          @click="mode === 'BOARD' ? openRecords() : camera?.flip()"
        >
          <text>{{ mode === "BOARD" ? "记录" : "⇄" }}</text>
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
      <view class="sheet-head"
        ><text>任务与设备</text
        ><button @click="showSettings = false">完成</button></view
      >
      <button class="sheet-row" @click="pickDevice">
        <text>板端设备</text
        ><text>{{ displayName(device?.name ?? "选择设备") }} ›</text>
      </button>
      <button class="sheet-row" @click="openTasks">
        <text>采样任务</text
        ><text>{{ session.taskId ? "更换任务" : "独立采样" }} ›</text>
      </button>
      <button v-if="session.taskId" class="sheet-row" @click="selectTask('')">
        取消关联任务
      </button>
      <button class="sheet-row" @click="openSync">
        <text>本地队列</text><text>{{ pending }} 待上传 ›</text>
      </button>
      <button v-if="mode !== 'MOBILE'" class="sheet-row" @click="openLive">
        设备工作台 ›
      </button>
    </view>
  </view>
</template>

<style scoped>
.capture-page {
  height: 100vh;
  height: 100dvh;
  position: relative;
  overflow: hidden;
  background: #102b36;
  color: #f0f8fa;
}
.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: calc(12px + env(safe-area-inset-top)) 16px 8px;
}
.round {
  width: 44px;
  height: 44px;
  min-height: 44px;
  padding: 0;
  border-radius: 50%;
  background: #ffffff12;
  color: white;
  font-size: 28px;
}
.heading {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  font-size: 17px;
  font-weight: 600;
}
.muted-copy {
  font-size: 11px;
  font-weight: 400;
  color: #aac6d0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.task-btn {
  padding: 10px 12px;
  background: #ffffff12;
  color: white;
  min-height: 44px;
  font-size: 12px;
}
.source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  min-height: 38px;
}
.source-label {
  color: #aac6d0;
  font-size: 12px;
}
.light-btn {
  background: transparent;
  color: #71ddc8;
  min-height: 32px;
  padding: 4px 10px;
  font-size: 12px;
}
.viewfinder {
  position: absolute;
  top: calc(126px + env(safe-area-inset-top));
  bottom: calc(252px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
}
.flash {
  position: absolute;
  inset: 0;
  background: #ffffff99;
  pointer-events: none;
}
.pip {
  position: absolute;
  top: calc(130px + env(safe-area-inset-top));
  right: 16px;
  width: 100px;
  height: 130px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #ffffff44;
}
.camera-controls {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0 24px calc(18px + env(safe-area-inset-bottom));
  background: #102b36;
}
.feedback {
  min-height: 38px;
  display: flex;
  justify-content: center;
  gap: 12px;
  align-items: center;
  color: #71ddc8;
  font-size: 12px;
}
.feedback.error {
  color: #ffb5a5;
}
.mode-switch {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin: 8px 0 20px;
}
.mode-switch button {
  padding: 8px 18px;
  min-height: 38px;
  border-radius: 20px;
  background: transparent;
  color: #aac6d0;
  font-size: 13px;
}
.mode-switch button.active {
  background: #ffffff1c;
  color: #71ddc8;
  font-weight: 600;
}
.shutter-row {
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: 18px;
}
.side {
  width: 60px;
  height: 60px;
  min-height: 60px;
  padding: 0;
  background: #ffffff0d;
  color: white;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  overflow: hidden;
}
.side image {
  width: 60px;
  height: 60px;
}
.shutter {
  width: 80px;
  height: 80px;
  min-height: 80px;
  border-radius: 50%;
  border: 3px solid white;
  padding: 5px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
}
.shutter view {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: white;
}
.shutter:active:not([disabled]) view {
  transform: scale(0.9);
  background: #71ddc8;
}
.shutter-hint {
  display: block;
  text-align: center;
  color: #aac6d0;
  margin-top: 16px;
  font-size: 12px;
}
.sheet-backdrop {
  position: absolute;
  inset: 0;
  z-index: 20;
  background: #00000080;
}
.settings-sheet {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 21;
  padding: 12px 20px calc(24px + env(safe-area-inset-bottom));
  border-radius: 24px 24px 0 0;
  background: white;
  color: #17343e;
}
.sheet-head,
.sheet-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.sheet-head {
  font-size: 17px;
  font-weight: 650;
  padding-bottom: 10px;
}
.sheet-head button {
  background: transparent;
  color: #087f82;
}
.sheet-row {
  width: 100%;
  padding: 16px 0;
  background: white;
  border-top: 1px solid #edf1f3;
  border-radius: 0;
  font-size: 14px;
  text-align: left;
}
@media (max-height: 640px) {
  .viewfinder {
    top: calc(110px + env(safe-area-inset-top));
    bottom: calc(220px + env(safe-area-inset-bottom));
  }
  .mode-switch {
    margin: 0 0 10px;
  }
  .shutter {
    width: 68px;
    height: 68px;
    min-height: 68px;
  }
  .feedback {
    min-height: 30px;
  }
}
</style>
