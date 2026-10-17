<script setup lang="ts">
import { chinese, displayName, statusTone } from "@vision/shared";
import { ref, computed } from "vue";
import { onShow } from "@dcloudio/uni-app";
import type { DeviceSnapshot } from "@vision/contracts";
import {
  session,
  tasks,
  devices,
  requireLogin,
  notify,
  logout,
  type Task,
} from "../../state";
import { queue } from "../../queue";
const taskList = ref<Task[]>([]),
  deviceList = ref<DeviceSnapshot[]>([]),
  loading = ref(false),
  error = ref("");
const pending = computed(
  () => queue.items.filter((i) => i.status !== "SYNCED").length,
);
async function load() {
  if (!requireLogin()) return;
  loading.value = true;
  error.value = "";
  try {
    const [t, d] = await Promise.all([tasks(), devices()]);
    taskList.value = t.items;
    deviceList.value = d;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    loading.value = false;
  }
}
onShow(load);
</script>
<template>
  <view
    v-if="!session.online || !session.serverAvailable || pending"
    class="offline-banner"
    @click="uni.navigateTo({ url: '/pages/sync/index' })"
    >{{ session.online ? "同步队列" : "离线模式" }} ·
    {{ pending }} 个样本待同步</view
  ><view class="page"
    ><view class="row">
      ><text class="status"
        >●
        {{
          session.online && session.serverAvailable ? "已连接" : "离线模式"
        }}</text
      ></view
    ><text class="eyebrow">现场任务</text
    ><text class="title">{{
      displayName(session.user?.name ?? "欢迎回来")
    }}</text
    ><view
      class="large-action"
      @click="uni.switchTab({ url: '/pages/capture/index' })"
      ><view
        ><text class="title">开始采样</text
        ><text class="note">板端 · 手机 · 同步采样</text></view
      ><text>进入采样</text></view
    ><view class="section-head"
      ><text>当前任务</text
      ><text class="muted" @click="uni.switchTab({ url: '/pages/tasks/index' })"
        >全部</text
      ></view
    ><view v-if="loading" class="empty">正在读取任务…</view
    ><view v-else-if="error" class="error" @click="load"
      >{{ error }} / 点击重试</view
    ><view v-else-if="!taskList.length" class="empty"
      >暂无任务，仍可进行独立采样。</view
    ><view v-for="t in taskList.slice(0, 3)" :key="t.id" class="card"
      ><view class="row"
        ><text>{{ displayName(t.name) }}</text
        ><text class="mono">{{ t._count.samples }} / {{ t.target }}</text></view
      ><view class="progress"
        ><view
          :style="{
            width: `${Math.min(100, (t._count.samples / t.target) * 100)}%`,
          }" /></view
      ><text class="note"
        >{{ chinese(t.status) }} ·
        {{ session.taskId === t.id ? "当前选中" : "未选择" }}</text
      ></view
    ><view class="section-head"
      ><text>设备状态</text><text class="muted" @click="load">刷新</text></view
    ><view class="card"
      ><view v-for="d in deviceList" :key="d.id" class="list-item"
        ><view class="row"
          ><text class="list-title">{{ displayName(d.name) }}</text
          ><text class="status" :class="statusTone(d.connectionState)"
            >● {{ chinese(d.connectionState) }}</text
          ></view
        ><text v-if="d.source === 'SIMULATION'" class="tag">模拟设备</text
        ><text class="list-caption"
          >运行状态 {{ chinese(d.runtimeState) }} · 模型
          {{ d.reportedState.modelVersion ?? "未上报" }}</text
        ></view
      ></view
    ><view class="row"
      ><text class="muted" @click="uni.navigateTo({ url: '/pages/pair/index' })"
        >配对服务器 / 工位</text
      ><text
        class="muted"
        @click="
          logout();
          uni.navigateTo({ url: '/pages/login/index' });
        "
        >退出</text
      ></view
    ></view
  >
</template>
