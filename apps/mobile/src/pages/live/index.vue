<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow, onHide } from "@dcloudio/uni-app";
import { chinese, displayName, statusTone } from "@vision/shared";
import {
  live,
  liveDevice,
  frameUsable,
  refreshDevices,
  setDevice,
  startLive,
  type LiveFrame,
} from "../../live";
import { request, session, notify, uid, captureIdentity } from "../../state";
import LiveFeed from "../../components/LiveFeed.vue";

const held = ref<LiveFrame | null>(null),
  busy = ref(false),
  immersive = ref(false),
  lastInspection = ref<{ id: string; result: string } | null>(null);
const shown = computed(() => held.value ?? live.frame);
const detections = computed(() => shown.value?.detections ?? null);
const device = computed(() => liveDevice.value);
const captureHint = computed(() => {
  if (!device.value) return "先选择一台设备";
  if (device.value.connectionState !== "ONLINE")
    return "设备离线，请工程师连接";
  if (!shown.value) return "等待设备画面";
  if (!held.value && !frameUsable()) return "画面已暂停，等待新帧";
  if (held.value) return "回看中；采样仍保存设备当前实时帧";
  return "";
});
const metric = (us: number | null | undefined) =>
  us == null ? "—" : (us / 1000).toFixed(1);
const streamFps = computed(() => (live.frame ? live.fps.toFixed(1) : "—"));

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
      if (next) {
        held.value = null;
        setDevice(next.id);
      }
    },
  });
}

async function capture() {
  if (!device.value || !frameUsable() || busy.value) return;
  busy.value = true;
  lastInspection.value = null;
  try {
    const identity = captureIdentity("mobile-live");
    const result = await request<{
      inspections: { id: string; result: string }[];
    }>("/samples/capture", "POST", {
      deviceId: device.value.id,
      taskId: session.taskId || undefined,
      clientId: identity.clientId,
      localSequence: identity.localSequence,
      idempotencyKey: uid(),
    });
    lastInspection.value = result.inspections[0] ?? null;
    try {
      uni.vibrateShort({ fail: () => {} });
    } catch {
      // 桌面浏览器没有震动，忽略。
    }
    uni.showToast({ title: "已采样当前帧", icon: "success" });
  } catch (error) {
    notify(error);
  } finally {
    busy.value = false;
  }
}

function back() {
  if (immersive.value) {
    immersive.value = false;
    return;
  }
  uni.navigateBack();
}

onShow(() => {
  startLive();
  void refreshDevices();
  try {
    uni.setKeepScreenOn({ keepScreenOn: true, fail: () => {} });
  } catch {
    // 浏览器不支持保持常亮。
  }
});
onHide(() => {
  try {
    uni.setKeepScreenOn({ keepScreenOn: false, fail: () => {} });
  } catch {
    // 同上。
  }
});
// 离开实时页不断开：采样页与首页共用同一条预览连接。
</script>

<template>
  <view class="live-page" :class="{ immersive }">
    <view v-if="!immersive" class="live-header">
      <button class="back" aria-label="返回" @click="back">‹</button>
      <view class="heading">
        <text class="kicker">设备监视 / LIVE</text>
        <text class="heading-title">实时画面<span>.</span></text>
      </view>
      <button class="device-switch" @click="pickDevice">
        <text class="device-state" :class="statusTone(device?.connectionState)"
          >● {{ chinese(device?.connectionState) }}</text
        >
        <text class="device-name">{{
          displayName(device?.name ?? "选择设备")
        }}</text>
      </button>
    </view>

    <view class="stage" :class="{ full: immersive }">
      <LiveFeed :override="held" :minimal="immersive" />
      <button
        class="immersive-toggle"
        :aria-label="immersive ? '退出全屏' : '全屏'"
        @click="immersive = !immersive"
      >
        {{ immersive ? "退出" : "全屏" }}
      </button>
      <view v-if="immersive" class="immersive-back">
        <button @click="back">‹ 返回</button>
      </view>
    </view>

    <template v-if="!immersive">
      <view class="filmstrip">
        <view class="strip-head">
          <text>最近帧</text>
          <text v-if="held" class="strip-live" @click="held = null"
            >回到实时 →</text
          >
          <text v-else class="strip-note">每帧到达即更新</text>
        </view>
        <scroll-view class="strip-track" scroll-x>
          <view
            v-for="frame in [...live.frames].reverse()"
            :key="frame.frameId"
            class="thumb"
            :class="{ selected: held?.frameId === frame.frameId }"
            @click="held = frame"
          >
            <image
              :src="`data:image/jpeg;base64,${frame.jpeg}`"
              mode="aspectFill"
            />
            <text class="mono">#{{ frame.frameId }}</text>
          </view>
          <view v-if="!live.frames.length" class="thumb empty">等待画面</view>
        </scroll-view>
      </view>

      <view class="readout">
        <view class="readout-head">
          <text>本帧判定</text>
          <text class="mono">{{
            shown ? `帧 #${shown.frameId}` : "等待画面"
          }}</text>
        </view>
        <view class="verdict" :class="{ candidate: detections?.length }">
          <text class="verdict-title">{{
            !shown
              ? "等待图像"
              : detections === null
                ? "仅图像"
                : detections.length
                  ? "待复核"
                  : "未检出缺陷"
          }}</text>
          <text class="verdict-note">{{
            !shown
              ? "设备画面到达后显示"
              : detections === null
                ? "本帧没有推理输出"
                : detections.length
                  ? `${detections.length} 处候选目标，需要人工确认`
                  : "本帧没有候选目标"
          }}</text>
        </view>
        <view v-if="detections?.length" class="detections">
          <view
            v-for="(box, index) in detections"
            :key="index"
            class="detection"
          >
            <text class="index mono">{{
              String(index + 1).padStart(2, "0")
            }}</text>
            <view class="det-copy">
              <text class="det-name">{{ displayName(box.label) }}</text>
              <text class="det-pos mono"
                >{{ Math.round(box.x1) }},{{ Math.round(box.y1) }} →
                {{ Math.round(box.x2) }},{{ Math.round(box.y2) }}</text
              >
            </view>
            <text class="det-score mono"
              >{{ (box.confidence * 100).toFixed(1) }}%</text
            >
          </view>
        </view>
      </view>

      <view class="metrics">
        <view class="metric">
          <text class="metric-label">画面流</text>
          <text class="metric-value mono"
            >{{ streamFps }}<text class="unit">FPS</text></text
          >
        </view>
        <view class="metric">
          <text class="metric-label">设备帧率</text>
          <text class="metric-value mono"
            >{{
              live.telemetry?.fps == null ? "—" : live.telemetry.fps.toFixed(1)
            }}<text class="unit">FPS</text></text
          >
        </view>
        <view class="metric">
          <text class="metric-label">推理</text>
          <text class="metric-value mono"
            >{{ metric(live.telemetry?.inferenceUs)
            }}<text class="unit">ms</text></text
          >
        </view>
        <view class="metric">
          <text class="metric-label">采集</text>
          <text class="metric-value mono"
            >{{ metric(live.telemetry?.captureUs)
            }}<text class="unit">ms</text></text
          >
        </view>
        <view class="metric">
          <text class="metric-label">传输</text>
          <text class="metric-value mono"
            >{{ metric(live.telemetry?.transferUs)
            }}<text class="unit">ms</text></text
          >
        </view>
        <view class="metric">
          <text class="metric-label">错误码</text>
          <text
            class="metric-value mono"
            :class="{ crit: live.telemetry?.errorCode }"
            >{{ live.telemetry?.errorCode ?? "—" }}</text
          >
        </view>
      </view>

      <view class="model-line">
        <text>运行模型</text>
        <text class="mono">{{
          device?.reportedState.modelVersion ?? "未上报"
        }}</text>
        <text class="mono">{{ device?.type ?? "" }}</text>
      </view>

      <view
        v-if="lastInspection"
        class="capture-result"
        @click="
          uni.navigateTo({ url: `/pages/detail/index?id=${lastInspection.id}` })
        "
      >
        <view>
          <text class="result-kicker">已采样当前帧</text>
          <text class="result-title"
            >检测结果 {{ chinese(lastInspection.result) }}</text
          >
        </view>
        <text class="result-link">查看记录 →</text>
      </view>

      <view class="actions">
        <button
          class="primary shutter-action"
          :loading="busy"
          :disabled="busy || !frameUsable()"
          @click="capture"
        >
          {{ busy ? "正在采样…" : "采样当前帧" }}
        </button>
      </view>
      <text class="action-hint">{{
        captureHint || "保存设备当前帧与检测记录"
      }}</text>
    </template>
  </view>
</template>

<style scoped>
.live-page {
  min-height: 100vh;
  background: #102b36;
  color: #f0f8fa;
  padding: 0 0 30px;
}
.live-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: calc(env(safe-area-inset-top) + 14px) 16px 14px;
}
.back {
  width: 36px;
  height: 36px;
  min-height: 36px;
  padding: 0;
  border: 1px solid #315460;
  background: transparent;
  color: #f0f8fa;
  font-size: 22px;
  line-height: 1;
  border-radius: 12px;
}
.heading {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
}
.kicker {
  font-size: 11px;
  letter-spacing: 2px;
  color: #8db0bd;
  font-family: Consolas, monospace;
}
.heading-title {
  font-size: 23px;
  font-weight: 550;
  letter-spacing: -0.5px;
}
.heading-title span {
  color: #f28b61;
}
.device-switch {
  max-width: 46%;
  min-height: 40px;
  padding: 6px 10px;
  border: 1px solid #315460;
  background: #1d231a;
  color: #f0f8fa;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  border-radius: 12px;
}
.device-state {
  font-size: 11px;
}
.device-name {
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.stage {
  position: relative;
  width: 100%;
  padding-top: 100%;
  background: #0d110b;
}
.stage > .live-feed {
  position: absolute;
  inset: 0;
}
.stage.full {
  position: fixed;
  inset: 0;
  z-index: 20;
  padding-top: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0d08;
}
.stage.full > .live-feed {
  position: relative;
  inset: auto;
  width: 100vw;
  height: 100vw;
  max-width: 100vh;
  max-height: 100vh;
}
.immersive-toggle {
  position: absolute;
  right: 12px;
  top: 44px;
  z-index: 2;
  min-height: 30px;
  padding: 4px 9px;
  border: 1px solid #ffffff40;
  background: #102b36cc;
  color: #d9e9ed;
  font-size: 11px;
  border-radius: 12px;
}
.immersive-back {
  position: absolute;
  left: 12px;
  top: 44px;
  z-index: 2;
}
.immersive-back button {
  min-height: 32px;
  padding: 5px 10px;
  border: 1px solid #ffffff40;
  background: #102b36cc;
  color: #d9e9ed;
  font-size: 11px;
  border-radius: 12px;
}
.filmstrip {
  padding: 12px 16px 4px;
}
.strip-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #aac6d0;
  margin-bottom: 7px;
}
.strip-live {
  color: #ee9a6e;
}
.strip-note {
  color: #8db0bd;
  font-size: 11px;
}
.strip-track {
  display: flex;
  white-space: nowrap;
  gap: 8px;
}
.thumb {
  display: inline-flex;
  flex-direction: column;
  width: 64px;
  border: 1px solid #315460;
  background: #102b36;
  position: relative;
}
.thumb image {
  width: 64px;
  height: 64px;
  display: block;
}
.thumb text {
  font-size: 11px;
  color: #aac6d0;
  padding: 3px 4px;
}
.thumb.selected {
  border-color: #f28b61;
}
.thumb.empty {
  width: 128px;
  height: 64px;
  align-items: center;
  justify-content: center;
  color: #8db0bd;
  font-size: 11px;
}
.readout {
  margin: 12px 16px 0;
  border-top: 1px solid #315460;
  padding-top: 12px;
}
.readout-head {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #aac6d0;
  margin-bottom: 9px;
}
.verdict {
  border: 1px solid #315460;
  background: #1a2017;
  padding: 11px 13px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.verdict.candidate {
  border-color: #a67c34;
  background: #241f13;
}
.verdict-title {
  font-size: 15px;
  font-weight: 550;
}
.verdict.candidate .verdict-title {
  color: #e8c27c;
}
.verdict-note {
  font-size: 11px;
  color: #aac6d0;
  line-height: 1.6;
}
.detections {
  margin-top: 9px;
  border: 1px solid #315460;
}
.detection {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 11px;
  border-bottom: 1px solid #2f3829;
}
.detection:last-child {
  border-bottom: 0;
}
.index {
  font-size: 11px;
  color: #8db0bd;
}
.det-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.det-name {
  font-size: 12px;
}
.det-pos {
  font-size: 11px;
  color: #8db0bd;
}
.det-score {
  font-size: 13px;
  color: #e8c27c;
}
.metrics {
  margin: 14px 16px 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid #315460;
  border-left: 1px solid #315460;
}
.metric {
  border-right: 1px solid #315460;
  border-bottom: 1px solid #315460;
  padding: 9px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.metric-label {
  font-size: 11px;
  color: #8b9782;
}
.metric-value {
  font-size: 15px;
  color: #f0f8fa;
}
.metric-value.crit {
  color: #ef9a80;
}
.unit {
  font-size: 11px;
  color: #8db0bd;
  margin-left: 3px;
}
.model-line {
  margin: 12px 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #aac6d0;
  border-top: 1px solid #315460;
  padding-top: 10px;
}
.model-line .mono {
  color: #d9e9ed;
  font-size: 11px;
}
.tag {
  margin-left: auto;
  border: 1px solid #7d6a3d;
  background: #2a2416;
  color: #d5b475;
  padding: 2px 5px;
  font-size: 11px;
}
.capture-result {
  margin: 14px 16px 0;
  border: 1px solid #5d6b4f;
  background: #1c2419;
  padding: 11px 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.result-kicker {
  display: block;
  font-size: 11px;
  color: #8b9782;
  margin-bottom: 3px;
}
.result-title {
  display: block;
  font-size: 13px;
}
.result-link {
  font-size: 11px;
  color: #ee9a6e;
  white-space: nowrap;
}
.actions {
  margin: 16px 16px 0;
}
.shutter-action {
  width: 100%;
  min-height: 48px;
  background: #087f82;
  color: #fff8eb;
  border-radius: 12px;
  font-size: 15px;
}
.shutter-action:active {
  background: #076b6e;
}
.action-hint {
  display: block;
  margin: 8px 16px 0;
  font-size: 11px;
  color: #8b9782;
  text-align: center;
  line-height: 1.7;
}

.back {
  width: 44px;
  min-height: 44px;
  height: 44px;
  border-radius: 14px;
}
.heading-title {
  font-weight: 650;
}
.stage {
  overflow: hidden;
  border-radius: 18px;
  margin: 0 16px;
  width: calc(100% - 32px);
  padding-top: calc(100% - 32px);
}
.stage.full {
  border-radius: 0;
  margin: 0;
}
.stage.full {
  width: 100%;
  padding-top: 0;
}
.device-switch {
  background: #193b48;
}
.live-header {
  min-width: 0;
}
.heading {
  min-width: 0;
}
.device-switch {
  max-width: 48%;
}
.device-switch {
  border-radius: 12px;
}
.readout,
.metrics {
  border-radius: 16px;
  overflow: hidden;
}
.actions button {
  border-radius: 14px;
}
.capture-result {
  border-radius: 14px;
}
</style>
