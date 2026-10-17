<script setup lang="ts">
import { ref, computed } from "vue";
import { onShow, onHide } from "@dcloudio/uni-app";
import type { DeviceSnapshot } from "@vision/contracts";
import { motionSummary, chinese, displayName } from "@vision/shared";
import {
  session,
  devices,
  requireLogin,
  request,
  notify,
  uid,
} from "../../state";
import { enqueue, syncQueue, queue } from "../../queue";
import CameraSurface from "../../components/CameraSurface.vue";
const mode = ref<"BOARD" | "MOBILE" | "SYNC">("MOBILE"),
  deviceList = ref<DeviceSnapshot[]>([]),
  deviceIndex = ref(0),
  camera = ref<InstanceType<typeof CameraSurface> | null>(null),
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
  visible = ref(false);
const sheetExpanded = ref(false);
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
  ),
  device = computed(() => deviceList.value[deviceIndex.value]);
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
onShow(async () => {
  visible.value = true;
  if (!requireLogin()) return;
  try {
    deviceList.value = await devices();
    const paired = deviceList.value.findIndex((d) => d.id === session.deviceId);
    if (paired >= 0) deviceIndex.value = paired;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
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
});
onHide(() => {
  visible.value = false;
  camera.value?.stop();
  uni.stopAccelerometer();
  uni.stopGyroscope();
  uni.offAccelerometerChange(accelerometer);
  uni.offGyroscopeChange?.();
});
async function board(captureSetClientId?: string) {
  if (!device.value?.capabilities.capture)
    throw new Error("设备不支持采样或尚未选择设备");
  return request<{ id: string; inspections: { id: string; result: string }[] }>(
    "/samples/capture",
    "POST",
    {
      deviceId: device.value.id,
      clientId: `mobile-board-${uid()}`,
      idempotencyKey: uid(),
      localSequence: 0,
      taskId: session.taskId || undefined,
      captureSetClientId,
    },
  );
}
async function capture() {
  busy.value = true;
  error.value = "";
  lastResult.value = "";
  const captureSet = mode.value === "SYNC" ? uid() : undefined;
  try {
    if (mode.value !== "BOARD") {
      const path = await camera.value!.capture();
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
      lastResult.value = "原始图像已保存到本地队列";
      if (session.online) void syncQueue();
    }
    if (mode.value !== "MOBILE") {
      try {
        const sample = await board(captureSet);
        lastResult.value += `${lastResult.value ? " · " : ""}${device.value?.source === "SIMULATION" ? "模拟设备 " : ""}板端采样已保存`;
        if (mode.value === "BOARD" && sample.inspections[0])
          uni.navigateTo({
            url: `/pages/detail/index?id=${sample.inspections[0].id}`,
          });
      } catch (e) {
        if (captureSet)
          throw new Error(
            `手机样本已保存，板端采样未完成。采样组 ${captureSet}：${String(e)}`,
          );
        throw e;
      }
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
    <view class="capture-header"
      ><view
        ><text class="field-kicker">视觉采样仪</text
        ><text class="field-title">现场采样<span>.</span></text></view
      ><view
        class="field-link"
        @click="uni.navigateTo({ url: '/pages/sync/index' })"
        ><text
          class="link-state"
          :class="{ online: session.online && session.serverAvailable }"
          >{{
            session.online && session.serverAvailable ? "已连接" : "离线模式"
          }}</text
        ><text class="mono">{{ pending }} 待同步</text></view
      ></view
    >
    <view class="modes"
      ><text
        v-for="m in [
          { key: 'BOARD', label: '板端' },
          { key: 'MOBILE', label: '手机' },
          { key: 'SYNC', label: '同步' },
        ]"
        :key="m.key"
        :class="{ active: mode === m.key }"
        @click="mode = m.key as typeof mode"
        >{{ m.label }}采样</text
      ></view
    >
    <view class="field-camera-label"
      ><text>{{ mode === "BOARD" ? "设备图像源" : "相机取景" }}</text
      ><text class="mono">{{
        mode === "BOARD" ? (device?.type ?? "未选择") : "原图采样"
      }}</text></view
    >
    <view class="camera-window">
      <CameraSurface v-if="mode !== 'BOARD' && visible" ref="camera" />
      <view v-else class="board-guide"
        ><text>板端采样</text
        ><text>{{ displayName(device?.name ?? "请选择设备") }}</text
        ><text v-if="device?.source === 'SIMULATION'" class="tag">模拟设备</text
        ><text class="board-source-state">{{
          chinese(device?.connectionState)
        }}</text></view
      >
      <view v-if="mode !== 'BOARD'" class="guide-frame"
        ><text>采样区域</text></view
      >
    </view>
    <view v-if="mode !== 'BOARD'" class="posture-strip" :class="posture.tone"
      ><view class="posture-label"
        ><view class="posture-dot" /><text>{{ posture.label }}</text></view
      ><view v-if="motion && imuAvailable" class="posture-values"
        ><text class="mono">俯仰 {{ motion.pitch?.toFixed(1) }}°</text
        ><text class="mono">横滚 {{ motion.roll?.toFixed(1) }}°</text></view
      ><text v-else class="posture-values">姿态辅助未启用</text></view
    >
    <view class="capture-sheet">
      <button
        class="sheet-toggle"
        :aria-expanded="sheetExpanded"
        @click="sheetExpanded = !sheetExpanded"
      >
        <view class="sheet-grip" /><view
          ><text>任务与设备</text
          ><text
            >{{ session.taskId ? "已关联任务" : "独立采样" }} ·
            {{ sheetExpanded ? "收起" : "展开" }}</text
          ></view
        >
      </button>
      <view v-if="sheetExpanded" class="sheet-settings"
        ><picker
          v-if="mode !== 'MOBILE'"
          :range="deviceList"
          range-key="name"
          :value="deviceIndex"
          @change="deviceIndex = Number($event.detail.value)"
          ><view class="device-picker"
            ><text>采样设备</text
            ><text
              >{{ displayName(device?.name ?? "选择设备") }} ·
              {{ chinese(device?.connectionState) }}</text
            ></view
          ></picker
        ><button
          class="task-picker"
          @click="uni.switchTab({ url: '/pages/tasks/index' })"
        >
          {{ session.taskId ? "更换关联任务" : "选择采样任务" }} →</button
        ><text v-if="mode === 'SYNC'" class="capture-note"
          >手机与设备分别采样，关联到同一采样组</text
        ></view
      >
      <text
        v-if="mode !== 'MOBILE' && !sheetExpanded"
        class="selected-device"
        @click="sheetExpanded = true"
        >{{ displayName(device?.name ?? "点击选择设备") }} /
        {{ chinese(device?.connectionState) }}</text
      >
      <text v-if="error" class="capture-error" role="alert">{{ error }}</text
      ><text v-if="lastResult" class="capture-success">{{ lastResult }}</text>
      <view class="shutter-row"
        ><button
          class="shutter-side"
          @click="uni.navigateTo({ url: '/pages/sync/index' })"
        >
          <text class="mono">{{ pending }}</text
          ><text>待同步</text></button
        ><button
          class="shutter"
          :disabled="busy"
          :loading="busy"
          @click="capture"
          aria-label="采样快门"
        >
          <view /></button
        ><button
          class="shutter-side"
          @click="uni.switchTab({ url: '/pages/records/index' })"
        >
          <text class="record-symbol">记录</text><text>检测记录</text>
        </button></view
      >
      <text class="capture-note">{{
        busy
          ? "正在保存采样…"
          : mode === "BOARD"
            ? "采样设备最近的完整帧"
            : imuAvailable && motion && posture.tone !== "stable"
              ? "调整姿态可改善采样，仍可直接拍摄"
              : "按下快门，保存原始图像"
      }}</text>
    </view>
  </view>
</template>
<style scoped>
.capture-page {
  min-height: 100vh;
  background: #1d211b;
  color: #eef1e6;
  padding: env(safe-area-inset-top) 0 16px;
}
.capture-header {
  padding: 22px 22px 17px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.field-kicker {
  display: block;
  color: #a4b096;
  font: 10px monospace;
  letter-spacing: 2px;
  margin-bottom: 7px;
}
.field-title {
  font-size: 27px;
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
  gap: 8px;
  text-align: right;
  font-size: 10px;
  min-height: 44px;
  justify-content: center;
  color: #a4b096;
}
.link-state {
  color: #e4b676;
}
.link-state.online {
  color: #a0cb87;
}
.modes {
  margin: 0 20px 15px;
  display: flex;
  border: 1px solid #525e45;
  background: #292f23;
}
.modes text {
  flex: 1;
  text-align: center;
  padding: 13px 0;
  font-size: 12px;
  color: #b5c0a6;
  min-height: 44px;
  border-right: 1px solid #525e45;
}
.modes text:last-child {
  border-right: 0;
}
.modes text.active {
  background: #ebece1;
  color: #272f20;
  font-weight: 600;
}
.field-camera-label {
  padding: 10px 20px;
  background: #30392a;
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: #b9c6a9;
  letter-spacing: 1px;
  border-top: 1px solid #4c5940;
}
.camera-window {
  height: 44vh;
  min-height: 275px;
  max-height: 560px;
  position: relative;
  overflow: hidden;
  background: #141910;
}
.guide-frame {
  position: absolute;
  left: 11%;
  top: 17%;
  width: 78%;
  height: 66%;
  border: 1px solid #e5ebd65c;
  pointer-events: none;
}
.guide-frame text {
  position: absolute;
  left: 9px;
  top: 9px;
  font: 9px monospace;
  letter-spacing: 1px;
  color: #dfe7d2;
  background: #20271bb0;
  padding: 3px 5px;
}
.board-guide {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 13px;
  color: #d2dcc4;
  font-size: 14px;
}
.board-source-state {
  font-size: 10px;
  color: #a4b38e;
}
.posture-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 20px;
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
  border-radius: 16px 16px 0 0;
  padding: 0 20px 18px;
  position: relative;
}
.sheet-toggle {
  border: 0;
  background: transparent;
  color: #39452d;
  padding: 10px 0 12px;
  width: 100%;
  min-height: 48px;
  border-radius: 0;
}
.sheet-grip {
  height: 3px;
  width: 30px;
  background: #b3b9a8;
  margin: 0 auto 13px;
  border-radius: 2px;
}
.sheet-toggle > view:last-child {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  font-size: 11px;
}
.sheet-toggle > view:last-child text:last-child {
  font-size: 9px;
  color: #707c63;
}
.sheet-settings {
  border-top: 1px solid #c9cebf;
  padding-top: 12px;
}
.device-picker {
  border: 1px solid #b7bfaa;
  padding: 12px;
  background: #faf9f3;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 55px;
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
  padding: 12px 0;
  color: #4d5b3f;
}
.selected-device {
  display: block;
  text-align: center;
  font: 10px monospace;
  padding: 10px 0 2px;
  min-height: 32px;
  color: #667456;
}
.shutter-row {
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin: 10px 0 5px;
  gap: 20px;
}
.shutter-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 70px;
  min-height: 70px;
  background: transparent;
  border: 0;
  padding: 8px;
  color: #536146;
  border-radius: 2px;
  font-size: 10px;
}
.shutter-side .mono {
  font-size: 24px;
  line-height: 1.2;
}
.record-symbol {
  font-size: 24px;
  line-height: 1.2;
  color: #536146;
}
.shutter {
  width: 78px;
  height: 78px;
  border: 2px solid #dc5a2a;
  border-radius: 50%;
  background: transparent;
  padding: 5px;
  flex-shrink: 0;
}
.shutter view {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #df602f;
}
.shutter:active {
  background: #f3dbc9;
}
.capture-note {
  display: block;
  color: #69775d;
  font-size: 10px;
  text-align: center;
  line-height: 1.8;
  margin-top: 8px;
}
.capture-error,
.capture-success {
  display: block;
  font-size: 11px;
  line-height: 1.7;
  padding: 10px;
  margin-top: 10px;
  border-left: 3px solid;
}
.capture-error {
  color: #a93b25;
  background: #f6e0d5;
}
.capture-success {
  color: #3b6c30;
  background: #e4ecd9;
}
@media (min-width: 700px) {
  .capture-page {
    max-width: 680px;
    margin: auto;
  }
  .camera-window {
    height: 50vh;
  }
  .capture-sheet {
    padding-left: 35px;
    padding-right: 35px;
  }
}
</style>
