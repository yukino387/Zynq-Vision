<script setup lang="ts">
import { computed } from "vue";
import { displayName } from "@vision/shared";
import type { DetectionBox } from "@vision/contracts";
import { live, liveDevice, frameAge, type LiveFrame } from "../live";

const props = defineProps<{
  /** 回看时传入历史帧；不传就跟随实时流。 */
  override?: LiveFrame | null;
  expandable?: boolean;
  deviceId?: string;
  /** 页面自己提供设备与判定信息时，只保留画面上的最小标记。 */
  minimal?: boolean;
}>();
const emit = defineEmits<{ expand: [] }>();

const device = computed(() =>
  props.deviceId
    ? (live.devices.find((d) => d.id === props.deviceId) ?? null)
    : liveDevice.value,
);
const frame = computed(() => props.override ?? live.frame);
const held = computed(() => Boolean(props.override));
const imageSrc = computed(() =>
  frame.value ? `data:image/jpeg;base64,${frame.value.jpeg}` : "",
);
const age = computed(() => {
  if (!frame.value) return null;
  if (held.value) return null;
  return frameAge.value;
});
const fresh = computed(
  () => age.value !== null && age.value < 4000 && !held.value,
);
const detections = computed(() => frame.value?.detections ?? null);
const runtimeLabel = computed(() => {
  if (!device.value) return "未连接";
  if (device.value.connectionState !== "ONLINE") return "等待连接";
  return device.value.runtimeState === "RUNNING"
    ? "检测运行中"
    : "设备就绪";
});

const state = computed(() => {
  if (!device.value)
    return {
      key: "empty",
      label: "未选择设备",
      detail: "在下方选择一台已连接的设备",
    };
  if (device.value.connectionState !== "ONLINE")
    return {
      key: "offline",
      label: "设备离线",
      detail: "请工程师在 Web 端连接设备后回到这里",
    };
  if (live.error)
    return { key: "error", label: "实时连接异常", detail: live.error };
  if (!live.ready)
    return {
      key: "connecting",
      label: "正在连接实时画面",
      detail: live.connecting ? "等待服务器响应…" : "连接已断开，正在重试…",
    };
  if (!frame.value)
    return {
      key: "waiting",
      label: "等待第一帧",
      detail: "设备已连接，画面到达后会立即显示",
    };
  if (!fresh.value)
    return {
      key: "stale",
      label: held.value ? "帧回看" : "画面已暂停",
      detail: held.value
        ? "正在查看历史帧"
        : `最后一帧 ${new Date(live.lastFrameAt).toLocaleTimeString()}`,
    };
  return { key: "live", label: "实时", detail: "" };
});

function boxStyle(box: DetectionBox, source: LiveFrame) {
  const width = source.width || 416;
  const height = source.height || 416;
  return {
    left: `${(box.x1 / width) * 100}%`,
    top: `${(box.y1 / height) * 100}%`,
    width: `${((box.x2 - box.x1) / width) * 100}%`,
    height: `${((box.y2 - box.y1) / height) * 100}%`,
  };
}
function ageText() {
  if (held.value) return "历史帧";
  if (age.value === null) return "";
  if (age.value < 1200) return "刚刚";
  return `${(age.value / 1000).toFixed(1)} 秒前`;
}
function expand() {
  if (props.expandable) emit("expand");
}
</script>

<template>
  <view
    class="live-feed"
    :class="{ interactable: expandable, dark: !frame }"
    @click="expand"
  >
    <image
      v-if="frame"
      class="feed-image"
      :src="imageSrc"
      mode="aspectFill"
      alt="设备实时画面"
    />
    <view v-if="frame && detections?.length" class="box-layer">
      <view
        v-for="(box, index) in detections"
        :key="index"
        class="det-box"
        :style="boxStyle(box, frame)"
      >
        <text class="det-label"
          >{{ displayName(box.label) }}
          {{ (box.confidence * 100).toFixed(0) }}%</text
        >
      </view>
    </view>

    <view class="hud-top">
      <view class="live-chip" :class="state.key"
        ><view class="dot" /><text>{{ state.label }}</text></view
      >
      <text v-if="frame" class="hud-mono"
        >{{ frame.width }} × {{ frame.height }} ·
        {{ held ? "回看" : `${live.fps.toFixed(1)} FPS` }}</text
      >
    </view>

    <view v-if="state.key !== 'live'" class="state-panel">
      <view v-if="state.key === 'connecting'" class="spinner" />
      <text class="state-title">{{ state.label }}</text>
      <text class="state-detail">{{ state.detail }}</text>
    </view>

    <view v-if="!minimal" class="hud-bottom">
      <view class="hud-device">
        <text class="hud-name">{{
          displayName(device?.name ?? "未选择设备")
        }}</text>
        <text class="hud-sub"
          >{{ runtimeLabel }} ·
          {{ device?.reportedState.modelVersion ?? "模型未上报" }}</text
        >
      </view>
      <view class="hud-right">
        <text v-if="frame" class="hud-mono">#{{ frame.frameId }}</text>
        <text v-if="ageText()" class="hud-mono muted">{{ ageText() }}</text>
      </view>
    </view>

    <view
      v-if="!minimal && frame && detections !== null"
      class="verdict-chip"
    >
      <text v-if="detections.length" class="warn"
        >{{ detections.length }} 处候选 · 待复核</text
      >
      <text v-else class="clear">本帧未检出</text>
    </view>
    <view v-if="!minimal && frame && detections === null" class="verdict-chip">
      <text class="muted-chip">仅图像</text>
    </view>

    <view v-if="expandable && !minimal" class="expand-hint"
      ><text>点击全屏</text></view
    >
  </view>
</template>

<style scoped>
.live-feed {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #10140f;
  color: #eef1e6;
}
.live-feed.interactable {
  cursor: pointer;
}
.feed-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}
.box-layer {
  position: absolute;
  inset: 0;
}
.det-box {
  position: absolute;
  border: 2px solid #ee743d;
  box-sizing: border-box;
}
.det-label {
  position: absolute;
  left: -2px;
  top: -19px;
  max-width: 220px;
  padding: 2px 5px;
  background: #ee743d;
  color: #1b1e1c;
  font-size: 10px;
  line-height: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hud-top {
  position: absolute;
  left: 12px;
  right: 12px;
  top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  pointer-events: none;
}
.live-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: #10140fcc;
  border: 1px solid #ffffff26;
  font-size: 10px;
  letter-spacing: 1px;
  color: #c9d2c0;
}
.live-chip .dot {
  width: 6px;
  height: 6px;
  background: #8d978a;
}
.live-chip.live {
  color: #d7ecc9;
  border-color: #9bc78966;
}
.live-chip.live .dot {
  background: #9bc789;
  box-shadow: 0 0 0 4px #9bc78922;
}
.live-chip.stale,
.live-chip.waiting,
.live-chip.connecting {
  color: #e8d4a8;
}
.live-chip.stale .dot,
.live-chip.waiting .dot,
.live-chip.connecting .dot {
  background: #e0b764;
}
.live-chip.offline,
.live-chip.error {
  color: #efb9a8;
}
.live-chip.offline .dot,
.live-chip.error .dot {
  background: #d9765c;
}
.hud-mono {
  font-family: Consolas, monospace;
  font-variant-numeric: tabular-nums;
  font-size: 10px;
  color: #c9d2c0;
  text-shadow: 0 1px 2px #00000080;
}
.hud-bottom {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  pointer-events: none;
}
.hud-device {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.hud-name {
  font-size: 12px;
  color: #eef1e6;
  text-shadow: 0 1px 3px #000000b0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hud-sub {
  font-size: 9px;
  color: #b9c4ae;
  text-shadow: 0 1px 3px #000000b0;
}
.hud-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
}
.hud-right .muted {
  color: #b9c4ae;
}
.state-panel {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 78%;
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  text-align: center;
  background: #10140fd9;
  border: 1px solid #ffffff1f;
}
.state-title {
  font-size: 14px;
  font-weight: 550;
}
.state-detail {
  font-size: 10px;
  line-height: 1.7;
  color: #aebaa3;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #ffffff26;
  border-top-color: #ee743d;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.verdict-chip {
  position: absolute;
  left: 12px;
  top: 42px;
  padding: 3px 7px;
  font-size: 9px;
  background: #10140fcc;
  border: 1px solid #ffffff26;
}
.verdict-chip .warn {
  color: #e0b764;
}
.verdict-chip .clear {
  color: #b9c4ae;
}
.verdict-chip .muted-chip {
  color: #93a08a;
}
.expand-hint {
  position: absolute;
  right: 12px;
  bottom: 38px;
  padding: 3px 6px;
  border: 1px solid #ffffff33;
  color: #d8e0cf;
  font-size: 9px;
  background: #10140f99;
}
</style>
