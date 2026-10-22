<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow, onHide, onPullDownRefresh } from "@dcloudio/uni-app";
import { chinese, displayName, statusTone } from "@vision/shared";
import {
  session,
  tasks,
  selectTask,
  requireLogin,
  notify,
  logout,
  type Task,
} from "../../state";
import { queue } from "../../queue";
import {
  live,
  liveDevice,
  refreshDevices,
  setDevice,
  startLive,
} from "../../live";
import DeviceRun from "../../components/DeviceRun.vue";
import LiveFeed from "../../components/LiveFeed.vue";

const taskList = ref<Task[]>([]),
  loading = ref(false),
  error = ref(""),
  visible = ref(false);
const pending = computed(
  () => queue.items.filter((i) => i.status !== "SYNCED").length,
);
const greeting = computed(() => displayName(session.user?.name ?? "操作员"));
const liveLabel = computed(() => {
  if (!liveDevice.value) return "未选择设备";
  if (liveDevice.value.connectionState !== "ONLINE") return "设备离线";
  if (!live.ready) return "正在连接";
  if (!live.frame) return "等待画面";
  return live.now - live.lastFrameAt > 4000 ? "画面暂停" : "实时";
});
const liveTone = computed(() => {
  if (!liveDevice.value || liveDevice.value.connectionState !== "ONLINE")
    return "crit";
  if (!live.ready || !live.frame) return "warn";
  return live.now - live.lastFrameAt > 4000 ? "warn" : "live";
});
const detections = computed(() => live.frame?.detections ?? null);

async function load() {
  if (!requireLogin()) return;
  loading.value = true;
  error.value = "";
  startLive();
  try {
    const [t] = await Promise.all([tasks(), refreshDevices()]);
    taskList.value = t.items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    loading.value = false;
  }
}
onShow(() => {
  visible.value = true;
  void load();
});
onHide(() => {
  visible.value = false;
});
onPullDownRefresh(async () => {
  try {
    await load();
  } finally {
    uni.stopPullDownRefresh();
  }
});

function openLive() {
  uni.navigateTo({ url: "/pages/live/index" });
}
function capture() {
  uni.switchTab({ url: "/pages/capture/index" });
}
function chooseTask(t: Task) {
  selectTask(t.id);
  capture();
}
function chooseDevice(id: string) {
  setDevice(id);
  uni.showToast({ title: "已切换实时设备", icon: "none" });
}
</script>

<template>
  <view
    v-if="!session.online || !session.serverAvailable || pending"
    class="offline-banner"
    @click="uni.navigateTo({ url: '/pages/sync/index' })"
    >{{ session.online ? "同步队列" : "离线模式" }} ·
    {{ pending }} 个样本待同步</view
  >
  <view class="page">
    <view class="welcome">
      <view class="welcome-row">
        <text class="eyebrow">现场工作台</text>
        <text
          class="connection"
          :class="{ online: session.online && session.serverAvailable }"
        >
          {{
            session.online && session.serverAvailable ? "已连接" : "离线模式"
          }}</text
        >
      </view>
      <text class="title">你好，{{ greeting }}</text>
    </view>

    <view class="live-card" @click="openLive">
      <view class="live-stage">
        <LiveFeed v-if="visible" minimal fit="aspectFit" />
      </view>
      <view class="live-foot">
        <view class="live-foot-copy">
          <text class="live-foot-title"
            >{{ displayName(liveDevice?.name ?? "未选择设备") }}
            <text class="live-dot" :class="liveTone">{{
              liveLabel
            }}</text></text
          >
          <text class="live-foot-note"
            >{{
              detections === null
                ? "等待推理"
                : detections.length
                  ? `${detections.length} 个画面目标`
                  : "当前画面无目标"
            }}
            ·
            {{ live.fps.toFixed(1) }} FPS</text
          >
        </view>
        <text class="live-foot-action">全屏查看</text>
      </view>
    </view>

    <DeviceRun />

    <view class="quick-grid">
      <view class="quick" @click="capture">
        <image class="quick-icon" src="/static/action-camera.png" />
        <text class="quick-title">开始采样</text>
        <text class="quick-note">实时相机</text>
      </view>
      <view
        class="quick"
        @click="uni.switchTab({ url: '/pages/records/index' })"
      >
        <image class="quick-icon" src="/static/action-records.png" />
        <text class="quick-title">检测记录</text>
        <text class="quick-note">查看与复核</text>
      </view>
      <view class="quick" @click="uni.navigateTo({ url: '/pages/sync/index' })">
        <image class="quick-icon" src="/static/action-sync.png" />
        <text class="quick-title">同步队列</text>
        <text class="quick-note">{{ pending }} 个待同步</text>
      </view>
    </view>

    <view class="section-head">
      <text>当前任务</text>
      <text class="muted" @click="uni.switchTab({ url: '/pages/tasks/index' })"
        >全部</text
      >
    </view>
    <view v-if="loading" class="empty">正在读取任务…</view>
    <view v-else-if="error" class="error" @click="load"
      >{{ error }} / 点击重试</view
    >
    <view v-else-if="!taskList.length" class="empty">暂无采样任务</view>
    <view
      v-for="t in taskList.slice(0, 3)"
      :key="t.id"
      class="card task-card"
      :class="{ selected: session.taskId === t.id }"
      @click="chooseTask(t)"
    >
      <view class="row">
        <text class="list-title">{{ displayName(t.name) }}</text>
        <text class="mono progress-count"
          >{{ t._count.samples }} / {{ t.target }}</text
        >
      </view>
      <view class="progress"
        ><view
          :style="{
            width: `${t.target ? Math.min(100, (t._count.samples / t.target) * 100) : 0}%`,
          }"
      /></view>
      <view class="row task-meta">
        <text class="note"
          >{{ chinese(t.status) }} ·
          {{ session.taskId === t.id ? "当前选中" : "选择任务" }}</text
        >
        <text class="task-select">{{
          session.taskId === t.id ? "继续采样" : "选择"
        }}</text>
      </view>
    </view>

    <view class="section-head">
      <text>设备状态</text>
      <text class="muted" @click="refreshDevices()">刷新</text>
    </view>
    <view class="card device-card">
      <view
        v-for="d in live.devices"
        :key="d.id"
        class="list-item device-row"
        :class="{ selected: d.id === live.deviceId }"
        @click="chooseDevice(d.id)"
      >
        <view class="device-main">
          <view class="row">
            <text class="list-title"
              >{{ displayName(d.name) }}
              <text v-if="d.id === live.deviceId" class="selected-mark"
                >实时源</text
              ></text
            >
            <text class="status" :class="statusTone(d.connectionState)">{{
              chinese(d.connectionState)
            }}</text>
          </view>
          <text class="list-caption"
            >{{ chinese(d.runtimeState) }} · 模型
            {{ d.reportedState.modelVersion ?? "未上报" }}</text
          >
        </view>
      </view>
      <view v-if="!live.devices.length" class="empty">暂无设备</view>
    </view>

    <view class="footer-links">
      <text class="muted" @click="uni.navigateTo({ url: '/pages/pair/index' })"
        >连接设置</text
      >
      <text
        class="muted"
        @click="
          logout();
          uni.navigateTo({ url: '/pages/login/index' });
        "
        >退出登录</text
      >
    </view>
  </view>
</template>

<style scoped>
.welcome {
  margin-bottom: 18px;
}
.welcome-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.connection {
  font-size: 11px;
  color: #8a6a24;
}
.connection.online {
  color: #087f82;
}
.live-card {
  border: 1px solid #dce6e9;
  background: #102b36;
  margin-bottom: 18px;
}
.live-stage {
  width: 100%;
  aspect-ratio: 1 / 1;
  position: relative;
  overflow: hidden;
}
.live-stage > .live-feed {
  position: absolute;
  inset: 0;
}
.live-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: #193b48;
  border-top: 1px solid #315460;
}
.live-foot-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.live-foot-title {
  font-size: 11px;
  color: #f0f8fa;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.live-dot {
  font-size: 11px;
  color: #aac6d0;
  margin-left: 4px;
  white-space: nowrap;
}
.live-dot.live {
  color: #71ddc8;
}
.live-dot.warn {
  color: #e4b676;
}
.live-dot.crit {
  color: #efb9a8;
}
.live-foot-note {
  font-size: 11px;
  color: #8db0bd;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.live-foot-action {
  font-size: 11px;
  color: #ee9a6e;
  white-space: nowrap;
}
.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: #dce6e9;
  border: 1px solid #dce6e9;
  margin-bottom: 4px;
}
.quick {
  background: #ffffff;
  padding: 13px 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-height: 82px;
}
.quick:active {
  background: #e8e7dc;
}
.quick-num {
  font:
    9px Consolas,
    monospace;
  color: #8ca4ad;
}
.quick-title {
  font-size: 13px;
  font-weight: 600;
}
.quick-note {
  font-size: 11px;
  color: #637d87;
  line-height: 1.5;
}
.task-card.selected {
  border-left: 3px solid #087f82;
  padding-left: 15px;
}
.progress-count {
  font-size: 13px;
  color: #486571;
}
.task-meta {
  margin-top: 8px;
}
.task-meta .note {
  margin: 0;
}
.task-select {
  font-size: 11px;
  color: #087f82;
  white-space: nowrap;
}
.device-card {
  padding-top: 2px;
  padding-bottom: 2px;
}
.device-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.device-row.selected {
  border-left: 3px solid #087f82;
  padding-left: 15px;
  margin-left: -18px;
  padding-right: 0;
}
.device-main {
  flex: 1;
  min-width: 0;
}
.selected-mark {
  font-size: 11px;
  color: #087f82;
  border: 1px solid #a8d8d3;
  padding: 1px 4px;
  margin-left: 5px;
  font-weight: 400;
  white-space: nowrap;
}
.footer-links {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
  font-size: 11px;
}

.welcome-row {
  margin-bottom: 10px;
}
.connection {
  background: #e5f3ef;
  border-radius: 20px;
  padding: 6px 10px;
  font-size: 11px;
}
.welcome .subtitle {
  margin-bottom: 20px;
}
.live-card {
  border: 0;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 10px 24px #102b3612;
}
.live-stage {
  aspect-ratio: 1.55 / 1;
}
.live-foot {
  padding: 13px 14px;
  border: 0;
}
.live-foot-title {
  font-size: 13px;
}
.live-dot {
  font-size: 11px;
}
.live-foot-note {
  font-size: 11px;
  margin-top: 3px;
}
.quick-grid {
  background: transparent;
  border: 0;
  gap: 10px;
  margin-top: 20px;
}
.quick {
  padding: 16px 10px;
  border: 1px solid #e4ecef;
  border-radius: 16px;
  gap: 5px;
}
.quick-icon {
  width: 26px;
  height: 26px;
  margin-bottom: 6px;
}
.quick-title {
  font-size: 14px;
}
.quick-note {
  font-size: 11px;
}
.task-card.selected {
  border-left: 3px solid #087f82;
  padding-left: 16px;
}
.task-meta {
  margin-top: 12px;
}
.task-select {
  font-size: 12px;
}
.selected-mark {
  font-size: 10px;
  border-radius: 5px;
  padding: 2px 5px;
}
.device-row.selected {
  border: 0;
  margin-left: 0;
  padding-left: 0;
}
.device-row.selected .list-title {
  color: #087f82;
}
.footer-links {
  padding: 18px 0 4px;
  margin-top: 10px;
  border-top: 1px solid #dce6e9;
  font-size: 12px;
}
</style>
