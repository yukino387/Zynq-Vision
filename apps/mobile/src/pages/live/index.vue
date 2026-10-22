<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow, onHide, onUnload } from "@dcloudio/uni-app";
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
import {
  request,
  session,
  notify,
  uid,
  captureIdentity,
  requireLogin,
} from "../../state";
import DeviceRun from "../../components/DeviceRun.vue";
import LiveFeed from "../../components/LiveFeed.vue";

const held = ref<LiveFrame | null>(null),
  busy = ref(false),
  immersive = ref(false),
  lastSample = ref(""),
  visible = ref(false),
  showDetails = ref(false);
const shown = computed(() => held.value ?? live.frame);
const detections = computed(() => shown.value?.detections ?? null);
const device = computed(() => liveDevice.value);
const captureHint = computed(() => {
  if (!device.value) return "先选择一台设备";
  if (device.value.connectionState !== "ONLINE")
    return "设备离线，请工程师连接";
  if (!shown.value) return "等待设备画面";
  if (!held.value && !frameUsable()) return "画面已暂停，等待新帧";
  if (held.value) return "回看中";
  return "";
});
const metric = (us: number | null | undefined) =>
  us == null ? "未上报" : (us / 1000).toFixed(1) + " 毫秒";
const streamFps = computed(() =>
  live.frame ? live.fps.toFixed(1) + " 帧/秒" : "等待画面",
);

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
  if (!device.value || !frameUsable() || busy.value || held.value) return;
  busy.value = true;
  lastSample.value = "";
  try {
    const identity = captureIdentity("mobile-live");
    const result = await request<{
      id: string;
    }>("/samples/capture", "POST", {
      deviceId: device.value.id,
      taskId: session.taskId || undefined,
      planId: session.taskId
        ? undefined
        : device.value.terminal?.state?.product?.id,
      clientId: identity.clientId,
      localSequence: identity.localSequence,
      idempotencyKey: uid(),
    });
    lastSample.value = result.id;
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
  if (!requireLogin()) return;
  visible.value = true;
  held.value = null;
  live.retainFrames = true;
  startLive();
  void refreshDevices();
  try {
    uni.setKeepScreenOn({ keepScreenOn: true, fail: () => {} });
  } catch {
    // 浏览器不支持保持常亮。
  }
});
function leave() {
  visible.value = false;
  live.retainFrames = false;
  live.frames = [];
  held.value = null;
  try {
    uni.setKeepScreenOn({ keepScreenOn: false, fail: () => {} });
  } catch {
    // 同上。
  }
}
onHide(leave);
onUnload(leave);
// 离开实时页不断开：采样页与首页共用同一条预览连接。
</script>

<template>
  <view class="live-page" :class="{ immersive }">
    <view v-if="!immersive" class="live-header">
      <button class="back" aria-label="返回" @click="back">‹</button>
      <button class="device-switch" @click="pickDevice">
        <text>{{ displayName(device?.name ?? "选择设备") }}</text
        ><text class="device-state" :class="statusTone(device?.connectionState)"
          >{{ chinese(device?.connectionState) }} ▾</text
        >
      </button>
    </view>
    <view class="stage" :class="{ full: immersive }">
      <LiveFeed
        v-if="visible"
        :key="immersive ? 'full' : 'inline'"
        :override="held"
        minimal
        fit="aspectFit"
      />
      <button class="immersive-toggle" @click="immersive = !immersive">
        {{ immersive ? "退出全屏" : "全屏" }}
      </button>
    </view>
    <template v-if="!immersive">
      <view class="content">
        <button v-if="held" class="return-live" @click="held = null">
          回到实时
        </button>
        <DeviceRun />
        <view class="sample-actions">
          <button
            class="primary"
            :loading="busy"
            :disabled="busy || !frameUsable() || !!held"
            @click="capture"
          >
            保存训练样本
          </button>
          <button @click="uni.switchTab({ url: '/pages/records/index' })">
            检测记录
          </button>
        </view>
        <text v-if="captureHint" class="hint">{{ captureHint }}</text>
        <button
          v-if="lastSample"
          class="sample-result"
          @click="
            uni.navigateTo({ url: `/pages/sample/index?id=${lastSample}` })
          "
        >
          样本已保存 · 查看 ›
        </button>
        <button class="details-toggle" @click="showDetails = !showDetails">
          {{ showDetails ? "收起详情 −" : "画面详情与回看 +" }}
        </button>
        <view v-if="showDetails" class="details">
          <view class="detail-row"
            ><text>当前画面</text
            ><text>{{
              detections === null ? "仅图像" : `${detections.length} 个目标`
            }}</text></view
          >
          <view
            v-for="(box, index) in detections || []"
            :key="index"
            class="detail-row"
            ><text>{{ displayName(box.label) }}</text
            ><text>{{ (box.confidence * 100).toFixed(0) }}%</text></view
          >
          <view class="detail-row"
            ><text>预览帧率</text><text>{{ streamFps }}</text></view
          >
          <view class="detail-row"
            ><text>推理</text
            ><text>{{ metric(live.telemetry?.inferenceUs) }}</text></view
          >
          <view class="detail-row"
            ><text>模型</text
            ><text>{{
              device?.terminal?.state?.model?.version ??
              device?.reportedState.modelVersion ??
              "未部署"
            }}</text></view
          >
          <scroll-view class="strip-track" scroll-x>
            <view
              v-for="frame in [...live.frames].reverse()"
              :key="frame.frameId"
              class="thumb"
              :class="{ selected: held?.frameId === frame.frameId }"
              @click="held = frame"
              ><image
                :src="`data:image/jpeg;base64,${frame.jpeg}`"
                mode="aspectFill"
              /><text>{{
                new Date(frame.receivedAt).toLocaleTimeString()
              }}</text></view
            >
          </scroll-view>
        </view>
      </view>
    </template>
  </view>
</template>

<style scoped>
.live-page {
  min-height: 100vh;
  background: #f3f6f7;
  color: #17343e;
}
.live-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: calc(10px + env(safe-area-inset-top)) 16px 12px;
  background: #102b36;
  color: white;
}
.back {
  width: 44px;
  min-height: 44px;
  padding: 0;
  font-size: 32px;
  background: #ffffff10;
  color: white;
}
.device-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex: 1;
  min-width: 0;
  padding: 10px 0;
  color: white;
  background: transparent;
  text-align: left;
}
.device-switch > text:first-child {
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}
.device-state {
  font-size: 11px;
  color: #aac6d0;
  white-space: nowrap;
}
.device-state.ok {
  color: #71ddc8;
}
.stage {
  width: 100%;
  height: 44vh;
  position: relative;
  background: #102b36;
}
.immersive-toggle {
  position: absolute;
  bottom: 12px;
  right: 14px;
  padding: 8px 14px;
  min-height: 38px;
  border-radius: 20px;
  background: #102b36b0;
  color: white;
  font-size: 12px;
}
.immersive {
  background: #102b36;
}
.stage.full {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  z-index: 30;
}
.full .immersive-toggle {
  bottom: calc(20px + env(safe-area-inset-bottom));
}
.content {
  padding: 0 16px calc(24px + env(safe-area-inset-bottom));
}
.sample-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.sample-actions button {
  flex: 1;
  padding: 13px 8px;
}
.hint {
  display: block;
  margin-top: 10px;
  font-size: 12px;
  color: #637d87;
}
.sample-result,
.return-live {
  background: #e0f3ed;
  color: #087f82;
  width: 100%;
  margin-top: 12px;
}
.details-toggle {
  width: 100%;
  background: transparent;
  color: #637d87;
  font-size: 13px;
  margin-top: 12px;
}
.details {
  background: white;
  padding: 12px 16px;
  border-radius: 16px;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding: 8px 0;
  font-size: 12px;
}
.detail-row > text:last-child {
  text-align: right;
  overflow-wrap: anywhere;
}
.strip-track {
  white-space: nowrap;
  width: 100%;
  margin-top: 12px;
}
.thumb {
  display: inline-flex;
  flex-direction: column;
  width: 78px;
  margin-right: 8px;
  border: 2px solid transparent;
  border-radius: 10px;
  overflow: hidden;
  background: #f3f6f7;
}
.thumb.selected {
  border-color: #087f82;
}
.thumb image {
  width: 74px;
  height: 74px;
}
.thumb text {
  font-size: 9px;
  padding: 5px 3px;
  text-align: center;
}
</style>
