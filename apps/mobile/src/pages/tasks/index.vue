<script setup lang="ts">
import { chinese, displayName } from "@vision/shared";
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import {
  session,
  tasks,
  selectTask,
  requireLogin,
  notify,
  type Task,
} from "../../state";
const list = ref<Task[]>([]),
  loading = ref(false),
  error = ref("");
async function load() {
  if (!requireLogin()) return;
  loading.value = true;
  error.value = "";
  try {
    list.value = (await tasks()).items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    loading.value = false;
  }
}
onShow(load);
function select(t: Task) {
  selectTask(t.id);
  uni.switchTab({ url: "/pages/capture/index" });
}
</script>

<template>
  <view class="page">
    <view class="head-row">
      <view>
        <text class="eyebrow">采样计划</text>
        <text class="title">采样任务</text>
      </view>
      <text class="muted refresh" @click="load">刷新</text>
    </view>
    <text class="subtitle"
      >选中任务后，所有板端与手机采样都会归入该任务。</text
    >
    <view v-if="loading" class="empty">读取任务…</view>
    <view v-else-if="error" class="error" @click="load"
      >{{ error }} / 重试</view
    >
    <view v-else-if="!list.length" class="empty">
      <text>暂无任务</text>
      <text class="hint">任务由管理员在 Web 端创建后下发到这里。</text>
    </view>
    <view
      v-for="t in list"
      :key="t.id"
      class="card task"
      :class="{ selected: session.taskId === t.id }"
      @click="select(t)"
    >
      <view class="row">
        <text class="list-title">{{ displayName(t.name) }}</text>
        <text class="status">{{ chinese(t.status) }}</text>
      </view>
      <view class="stat-row">
        <view>
          <text class="value mono">{{ t._count.samples }}</text>
          <text class="caption">已采样</text>
        </view>
        <view>
          <text class="value mono">{{ t.target }}</text>
          <text class="caption">目标样本</text>
        </view>
        <view>
          <text class="value mono"
            >{{
              t.target
                ? Math.min(100, Math.round((t._count.samples / t.target) * 100))
                : 0
            }}%</text
          >
          <text class="caption">完成度</text>
        </view>
      </view>
      <view class="progress"
        ><view
          :style="{
            width: `${t.target ? Math.min(100, (t._count.samples / t.target) * 100) : 0}%`,
          }"
        /></view
      >
      <text v-if="session.taskId === t.id" class="selected-note"
        >当前任务 · 点按继续采样 →</text
      >
    </view>

    <view
      class="card independent"
      :class="{ selected: !session.taskId }"
      @click="
        selectTask('');
        uni.switchTab({ url: '/pages/capture/index' });
      "
    >
      <view class="row">
        <text class="list-title">独立采样</text>
        <text class="status">不关联任务</text>
      </view>
      <text class="note">用于临时抽检；样本仍会保存并进入记录。</text>
      <text v-if="!session.taskId" class="selected-note">当前模式</text>
    </view>
  </view>
</template>

<style scoped>
.head-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}
.head-row .title {
  margin-bottom: 0;
}
.refresh {
  font-size: 11px;
  padding-bottom: 6px;
}
.task {
  border-left: 3px solid transparent;
  transition: background 0.15s;
}
.task.selected,
.independent.selected {
  border-left-color: #dd5b2a;
  background: #fbf8ef;
}
.stat-row {
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 14px 0 10px;
  border-top: 1px solid #b7bda9;
  border-bottom: 1px solid #b7bda9;
  padding: 10px 0;
}
.stat-row > view {
  border: 0;
  padding: 0;
}
.stat-row .value {
  font-size: 21px;
}
.stat-row .caption {
  font-size: 10px;
}
.progress {
  margin-top: 4px;
}
.selected-note {
  display: block;
  margin-top: 10px;
  font-size: 10px;
  color: #b4491f;
}
.independent {
  border-left: 3px solid transparent;
}
.independent .note {
  margin: 6px 0 0;
}
</style>
