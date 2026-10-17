<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { onShow } from "@dcloudio/uni-app";
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
import LiveFeed from "../../components/LiveFeed.vue";

const taskList = ref<Task[]>([]),
  loading = ref(false),
  error = ref("");
const pending = computed(
  () => queue.items.filter((i) => i.status !== "SYNCED").length,
);
const greeting = computed(() => displayName(session.user?.name ?? "操作员"));
const liveLabel = computed(() => {
  if (!liveDevice.value) return "未选择设备";
  if (liveDevice.value.connectionState !== "ONLINE") return "设备离线";
  if (!live.ready) return "正在连接";
  if (!live.frame) return "等待画面";
  return Date.now() - live.lastFrameAt > 4000 ? "画面暂停" : "实时";
});
const liveTone = computed(() => {
  if (!liveDevice.value || liveDevice.value.connectionState !== "ONLINE")
    return "crit";
  if (!live.ready || !live.frame) return "warn";
  return Date.now() - live.lastFrameAt > 4000 ? "warn" : "live";
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
onShow(load);
let refreshTimer: ReturnType<typeof setTimeout> | null = null;
watch(
  () => live.completedAt,
  () => {
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => void load(), 500);
  },
);

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
        <text class="eyebrow">现场任务 / FIELD</text>
        <text
          class="connection"
          :class="{ online: session.online && session.serverAvailable }"
          >●
          {{
            session.online && session.serverAvailable ? "已连接" : "离线模式"
          }}</text
        >
      </view>
      <text class="title">你好，{{ greeting }}</text>
      <text class="subtitle"
        >先看设备画面，再按下快门。板端、手机与同步采样都在同一个入口。</text
      >
    </view>

    <view class="live-card" @click="openLive">
      <view class="live-stage">
        <LiveFeed minimal />
      </view>
      <view class="live-foot">
        <view class="live-foot-copy">
          <text class="live-foot-title"
            >{{ displayName(liveDevice?.name ?? "未选择设备") }}
            <text class="live-dot" :class="liveTone">● {{ liveLabel }}</text></text
          >
          <text class="live-foot-note"
            >{{
              detections === null
                ? "等待本帧推理输出"
                : detections.length
                  ? `${detections.length} 处候选目标 · 待复核`
                  : "本帧未检出缺陷"
            }}
            ·
            {{ live.fps.toFixed(1) }} FPS</text
          >
        </view>
        <text class="live-foot-action">全屏 ↗</text>
      </view>
    </view>

    <view class="quick-grid">
      <view class="quick" @click="capture">
        <text class="quick-num">01</text>
        <text class="quick-title">开始采样</text>
        <text class="quick-note">板端 / 手机 / 同步</text>
      </view>
      <view class="quick" @click="uni.switchTab({ url: '/pages/records/index' })">
        <text class="quick-num">02</text>
        <text class="quick-title">检测记录</text>
        <text class="quick-note">复核与证据</text>
      </view>
      <view class="quick" @click="uni.navigateTo({ url: '/pages/sync/index' })">
        <text class="quick-num">03</text>
        <text class="quick-title">同步队列</text>
        <text class="quick-note">{{ pending }} 个待同步</text>
      </view>
    </view>

    <view class="section-head">
      <text>当前任务</text>
      <text class="muted" @click="uni.switchTab({ url: '/pages/tasks/index' })"
        >全部 →</text
      >
    </view>
    <view v-if="loading" class="empty">正在读取任务…</view>
    <view v-else-if="error" class="error" @click="load"
      >{{ error }} / 点击重试</view
    >
    <view v-else-if="!taskList.length" class="empty"
      >暂无任务，仍可进行独立采样。</view
    >
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
        /></view
      >
      <view class="row task-meta">
        <text class="note"
          >{{ chinese(t.status) }} ·
          {{ session.taskId === t.id ? "当前选中" : "点按选择" }}</text
        >
        <text class="task-select">{{
          session.taskId === t.id ? "继续采样 →" : "选择 →"
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
            <text class="status" :class="statusTone(d.connectionState)"
              >● {{ chinese(d.connectionState) }}</text
            >
          </view>
          <text v-if="d.source === 'SIMULATION'" class="tag">模拟设备</text>
          <text class="list-caption"
            >{{ chinese(d.runtimeState) }} · 模型
            {{ d.reportedState.modelVersion ?? "未上报" }}</text
          >
        </view>
      </view>
      <view v-if="!live.devices.length" class="empty"
        >尚未注册设备。请工程师在 Web 端添加并连接。</view
      >
    </view>

    <view class="footer-links">
      <text class="muted" @click="uni.navigateTo({ url: '/pages/pair/index' })"
        >配对服务器 / 工位</text
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
  font-size: 9px;
  color: #8a6a24;
}
.connection.online {
  color: #4d7a4b;
}
.live-card {
  border: 1px solid #b7bda9;
  background: #10140f;
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
  background: #22281c;
  border-top: 1px solid #3d4736;
}
.live-foot-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.live-foot-title {
  font-size: 11px;
  color: #eef1e6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.live-dot {
  font-size: 8px;
  color: #b9c4ae;
  margin-left: 4px;
  white-space: nowrap;
}
.live-dot.live {
  color: #a0cb87;
}
.live-dot.warn {
  color: #e4b676;
}
.live-dot.crit {
  color: #efb9a8;
}
.live-foot-note {
  font-size: 9px;
  color: #93a08a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.live-foot-action {
  font-size: 10px;
  color: #ee9a6e;
  white-space: nowrap;
}
.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: #b7bda9;
  border: 1px solid #b7bda9;
  margin-bottom: 4px;
}
.quick {
  background: #f7f6ee;
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
  font: 9px Consolas, monospace;
  color: #a4ad98;
}
.quick-title {
  font-size: 13px;
  font-weight: 600;
}
.quick-note {
  font-size: 9px;
  color: #6b775e;
  line-height: 1.5;
}
.task-card.selected {
  border-left: 3px solid #dd5b2a;
  padding-left: 15px;
}
.progress-count {
  font-size: 13px;
  color: #4d5b3f;
}
.task-meta {
  margin-top: 8px;
}
.task-meta .note {
  margin: 0;
}
.task-select {
  font-size: 10px;
  color: #b4491f;
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
  border-left: 3px solid #dd5b2a;
  padding-left: 15px;
  margin-left: -18px;
  padding-right: 0;
}
.device-main {
  flex: 1;
  min-width: 0;
}
.selected-mark {
  font-size: 8px;
  color: #b4491f;
  border: 1px solid #d9a388;
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
</style>
