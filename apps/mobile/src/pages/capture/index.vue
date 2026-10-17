<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { onShow, onHide } from "@dcloudio/uni-app";
import { motionSummary, chinese, displayName, statusTone } from "@vision/shared";
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
  sheetExpanded = ref(false);

const device = computed(() => liveDevice.value),
  detections = computed(() => live.frame?.detections ?? null);
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
  if (!device.value) return "请先在下方选择设备";
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
  if (value === "BOARD" || value === "MOBILE" || value === "SYNC")
    mode.value = value;
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
  try {
    uni.stopAccelerometer({ fail: () => {} });
    uni.stopGyroscope({ fail: () => {} });
    uni.offAccelerometerChange(accelerometer);
    uni.offGyroscopeChange?.();
  } catch {
    // H5 没有传感器时停止接口也可能失败。
  }
});

function openLive() {
  uni.navigateTo({ url: "/pages/live/index" });
}
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
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  lastResult.value = "";
  lastInspection.value = null;
  const capturing = mode.value;
  const captureSet = capturing === "SYNC" ? uid() : undefined;
  try {
    if (capturing !== "BOARD") {
      if (!camera.value) throw new Error("相机尚未准备就绪，请稍后重试");
      const path = await camera.value.capture();
      const system = uni.getSystemInfoSync();
      await enqueue(
        path,
        {
          orientation: system.deviceOrientation ?? "UNKNOWN",
          deviceModel: system.model,
          appVersion: "0.1.0",
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
      lastResult.value += `${lastResult.value ? " · " : ""}${
        device.value?.source === "SIMULATION" ? "模拟设备 " : ""
      }板端采样已保存`;
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
    <view class="capture-header">
      <view class="heading">
        <text class="field-kicker">视觉采样仪 / FIELD</text>
        <text class="field-title">现场采样<span>.</span></text>
      </view>
      <view
        class="field-link"
        @click="uni.navigateTo({ url: '/pages/sync/index' })"
      >
        <text
          class="link-state"
          :class="{ online: session.online && session.serverAvailable }"
          >{{ session.online && session.serverAvailable ? "已连接" : "离线模式" }}</text
        >
        <text class="mono">{{ pending }} 待同步</text>
      </view>
    </view>

    <view class="modes">
      <text
        v-for="m in [
          { key: 'BOARD', label: '板端' },
          { key: 'MOBILE', label: '手机' },
          { key: 'SYNC', label: '同步' },
        ]"
        :key="m.key"
        :class="{ active: mode === m.key }"
        @click="setMode(m.key)"
        >{{ m.label }}采样</text
      >
    </view>

    <view class="viewer">
      <LiveFeed
        v-if="mode !== 'MOBILE'"
        minimal
        expandable
        @expand="openLive"
      />
      <CameraSurface v-else-if="visible" ref="camera" />
      <view v-if="mode === 'SYNC' && visible" class="pip">
        <CameraSurface ref="camera" />
        <text class="pip-label">手机</text>
      </view>
      <view v-if="mode === 'MOBILE'" class="guide-frame"
        ><text>采样区域</text></view
      >
    </view>

    <view class="source-bar">
      <view class="source-main" @click="pickDevice">
        <text class="source-name">{{
          mode === "MOBILE"
            ? "手机相机"
            : displayName(device?.name ?? "选择设备")
        }}</text>
        <text
          class="source-state"
          :class="mode === 'MOBILE' ? 'live' : statusTone(device?.connectionState)"
          >●
          {{
            mode === "MOBILE"
              ? "原图采样"
              : chinese(device?.connectionState)
          }}</text
        >
      </view>
      <view class="source-meta">
        <text
          v-if="mode !== 'MOBILE' && device?.connectionState === 'ONLINE'"
          class="mono"
          >{{ live.fps.toFixed(1) }} FPS · 推理
          {{
            live.telemetry?.inferenceUs == null
              ? "—"
              : (live.telemetry.inferenceUs / 1000).toFixed(1)
          }}ms</text
        >
        <text v-else-if="mode !== 'MOBILE'" class="mono">无实时数据</text>
        <text v-else class="mono">手机原图 · 离线优先</text>
        <view v-if="mode !== 'MOBILE'" class="source-actions">
          <text @click="pickDevice">切换设备</text>
          <text @click="openLive">全屏 ↗</text>
        </view>
      </view>
    </view>

    <view
      v-if="mode !== 'MOBILE' && verdict"
      class="verdict-strip"
      :class="{ candidate: verdict.candidate }"
    >
      <text class="verdict-text">{{ verdict.text }}</text>
      <text class="verdict-detail">{{ verdict.detail }}</text>
      <text v-if="mode === 'SYNC'" class="sync-badge">同步组</text>
    </view>

    <view v-if="mode !== 'BOARD'" class="posture-strip" :class="posture.tone">
      <view class="posture-label"
        ><view class="posture-dot" /><text>{{ posture.label }}</text></view
      >
      <view v-if="motion && imuAvailable" class="posture-values">
        <text class="mono">俯仰 {{ motion.pitch?.toFixed(1) }}°</text>
        <text class="mono">横滚 {{ motion.roll?.toFixed(1) }}°</text>
      </view>
      <text v-else class="posture-values">姿态辅助未启用</text>
    </view>

    <view class="capture-sheet">
      <button
        class="sheet-toggle"
        :aria-expanded="sheetExpanded"
        @click="sheetExpanded = !sheetExpanded"
      >
        <view class="sheet-grip" />
        <view class="sheet-toggle-copy">
          <text>任务与设备</text>
          <text
            >{{ session.taskId ? "已关联任务" : "独立采样" }} ·
            {{ sheetExpanded ? "收起" : "展开" }}</text
          >
        </view>
      </button>

      <view v-if="sheetExpanded" class="sheet-settings">
        <view
          v-if="mode !== 'MOBILE'"
          class="device-picker"
          @click="pickDevice"
        >
          <text>采样设备</text>
          <text
            >{{ displayName(device?.name ?? "选择设备") }} ·
            {{ chinese(device?.connectionState) }}</text
          >
        </view>
        <button
          class="task-picker"
          @click="uni.switchTab({ url: '/pages/tasks/index' })"
        >
          {{ session.taskId ? "更换关联任务" : "选择采样任务" }} →
        </button>
        <text v-if="mode === 'SYNC'" class="capture-note"
          >手机与设备分别采样，关联到同一采样组</text
        >
      </view>

      <text v-if="error" class="capture-error" role="alert">{{ error }}</text>
      <view
        v-if="lastInspection"
        class="result-card"
        @click="
          uni.navigateTo({
            url: `/pages/detail/index?id=${lastInspection.id}`,
          })
        "
      >
        <view>
          <text class="result-kicker">板端采样已保存</text>
          <text class="result-title"
            >检测结果 {{ chinese(lastInspection.result) }}</text
          >
        </view>
        <text class="result-link">查看 →</text>
      </view>
      <text v-else-if="lastResult" class="capture-success">{{
        lastResult
      }}</text>

      <view class="shutter-row">
        <button
          class="shutter-side"
          @click="uni.navigateTo({ url: '/pages/sync/index' })"
        >
          <text class="mono">{{ pending }}</text>
          <text>待同步</text>
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
          class="shutter-side"
          @click="uni.switchTab({ url: '/pages/records/index' })"
        >
          <text class="record-symbol">记录</text>
          <text>检测记录</text>
        </button>
      </view>
      <text class="capture-note">{{ shutterHint }}</text>
    </view>
  </view>
</template>

<style scoped>
.capture-page {
  min-height: 100vh;
  background: #161a12;
  color: #eef1e6;
  padding: env(safe-area-inset-top) 0 16px;
}
.capture-header {
  padding: 18px 20px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.field-kicker {
  display: block;
  color: #93a08a;
  font: 9px Consolas, monospace;
  letter-spacing: 2px;
  margin-bottom: 6px;
}
.field-title {
  font-size: 26px;
  line-height: 1.2;
  font-weight: 550;
  letter-spacing: -1px;
}
.field-title span {
  color: #ee743d;
}
.field-link {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: right;
  font-size: 10px;
  min-height: 44px;
  justify-content: center;
  color: #93a08a;
}
.link-state {
  color: #e4b676;
}
.link-state.online {
  color: #a0cb87;
}
.modes {
  margin: 0 20px 12px;
  display: flex;
  border: 1px solid #4a5541;
  background: #22281c;
}
.modes text {
  flex: 1;
  text-align: center;
  padding: 12px 0;
  font-size: 12px;
  color: #b5c0a6;
  min-height: 44px;
  border-right: 1px solid #4a5541;
}
.modes text:last-child {
  border-right: 0;
}
.modes text.active {
  background: #ebece1;
  color: #272f20;
  font-weight: 600;
}
.viewer {
  width: min(100%, 44vh);
  aspect-ratio: 1 / 1;
  margin: 0 auto;
  position: relative;
  overflow: hidden;
  background: #0d110b;
}
.pip {
  position: absolute;
  right: 12px;
  bottom: 46px;
  width: 30%;
  height: 30%;
  min-width: 104px;
  min-height: 104px;
  border: 1px solid #eef1e666;
  overflow: hidden;
  background: #10140f;
  z-index: 2;
}
.pip-label {
  position: absolute;
  left: 0;
  bottom: 0;
  background: #10140fcc;
  color: #dfe7d5;
  font-size: 8px;
  padding: 2px 5px;
}
.guide-frame {
  position: absolute;
  left: 11%;
  top: 17%;
  width: 78%;
  height: 66%;
  border: 1px solid #e5ebd65c;
  pointer-events: none;
  z-index: 2;
}
.guide-frame text {
  position: absolute;
  left: 9px;
  top: 9px;
  font: 9px Consolas, monospace;
  letter-spacing: 1px;
  color: #dfe7d2;
  background: #20271bb0;
  padding: 3px 5px;
}
.source-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 11px 20px;
  background: #2a3123;
  border-top: 1px solid #515f41;
}
.source-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.source-name {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-state {
  font-size: 9px;
  color: #93a08a;
}
.source-state.live {
  color: #a0cb87;
}
.source-state.ok {
  color: #a0cb87;
}
.source-state.warn {
  color: #e4b676;
}
.source-state.crit {
  color: #efb9a8;
}
.source-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
}
.source-meta .mono {
  font-size: 9px;
  color: #aab6a0;
}
.source-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 9px;
  color: #d8b181;
}
.verdict-strip {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 20px;
  background: #20261b;
  border-bottom: 1px solid #3d4736;
}
.verdict-strip.candidate {
  background: #262013;
  border-bottom-color: #6a5528;
}
.verdict-text {
  font-size: 12px;
  font-weight: 600;
}
.verdict-strip.candidate .verdict-text {
  color: #e8c27c;
}
.verdict-detail {
  font-size: 9px;
  color: #93a08a;
}
.sync-badge {
  margin-left: auto;
  font-size: 8px;
  color: #dfe7d5;
  border: 1px solid #4a5541;
  padding: 2px 5px;
}
.posture-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11px 20px;
  background: #2c3524;
  border-top: 1px solid #515f41;
  gap: 12px;
}
.posture-label {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  font-weight: 550;
}
.posture-dot {
  width: 6px;
  height: 6px;
  background: #a7b596;
}
.stable .posture-dot {
  background: #a4d588;
}
.stable .posture-label {
  color: #c1e0ab;
}
.motion .posture-dot,
.tilt .posture-dot {
  background: #efb761;
}
.motion .posture-label,
.tilt .posture-label {
  color: #efc48a;
}
.posture-values {
  display: flex;
  gap: 14px;
  font-size: 9px;
  color: #b6c3a5;
}
.capture-sheet {
  background: #f1f0e8;
  color: #2c3326;
  border-radius: 14px 14px 0 0;
  padding: 0 20px 16px;
  position: relative;
  margin-top: 2px;
}
.sheet-toggle {
  border: 0;
  background: transparent;
  color: #39452d;
  padding: 8px 0 10px;
  width: 100%;
  min-height: 44px;
  border-radius: 0;
}
.sheet-grip {
  height: 3px;
  width: 30px;
  background: #b3b9a8;
  margin: 0 auto 10px;
  border-radius: 2px;
}
.sheet-toggle-copy {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  font-size: 11px;
}
.sheet-toggle-copy text:last-child {
  font-size: 9px;
  color: #707c63;
}
.sheet-settings {
  border-top: 1px solid #c9cebf;
  padding-top: 10px;
}
.device-picker {
  border: 1px solid #b7bfaa;
  padding: 11px 12px;
  background: #faf9f3;
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-height: 52px;
}
.device-picker text:first-child {
  font-size: 9px;
  color: #728063;
}
.device-picker text:last-child {
  font-size: 12px;
}
.task-picker {
  border: 0;
  background: transparent;
  text-align: left;
  font-size: 11px;
  min-height: 44px;
  padding: 10px 0;
  color: #4d5b3f;
}
.capture-note {
  display: block;
  font-size: 10px;
  color: #707c63;
  line-height: 1.7;
  text-align: center;
  margin-top: 6px;
}
.capture-error {
  display: block;
  color: #a5321a;
  background: #f3e1da;
  border: 1px solid #d4a294;
  padding: 10px 12px;
  font-size: 11px;
  line-height: 1.7;
  margin-top: 10px;
}
.capture-success {
  display: block;
  color: #3d6b4b;
  background: #e4ecdf;
  border: 1px solid #b9c9ae;
  padding: 9px 12px;
  font-size: 11px;
  line-height: 1.7;
  margin-top: 10px;
}
.result-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid #b9c9ae;
  background: #eef2e8;
}
.result-kicker {
  display: block;
  font-size: 9px;
  color: #707c63;
  margin-bottom: 2px;
}
.result-title {
  display: block;
  font-size: 12px;
  color: #2c3326;
}
.result-link {
  font-size: 10px;
  color: #b4491f;
  white-space: nowrap;
}
.shutter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 8px;
}
.shutter-side {
  width: 84px;
  border: 1px solid #b7bfaa;
  background: transparent;
  color: #4d5b3f;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 0;
  font-size: 9px;
  min-height: 60px;
  border-radius: 2px;
}
.shutter-side .mono {
  font-size: 18px;
  line-height: 1.1;
}
.record-symbol {
  font-size: 16px;
  line-height: 1.2;
}
.shutter {
  width: 86px;
  height: 86px;
  min-height: 86px;
  border-radius: 50%;
  border: 2px solid #dd5b2a;
  background: transparent;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.shutter view {
  width: 67px;
  height: 67px;
  border-radius: 50%;
  background: #dd5b2a;
}
.shutter:active:not([disabled]) view {
  background: #c64b1e;
  transform: scale(0.97);
}
.shutter[disabled] {
  opacity: 0.38;
}
</style>
