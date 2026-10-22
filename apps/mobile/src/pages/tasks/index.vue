<script setup lang="ts">
import { chinese, displayName } from "@vision/shared";
import { ref } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
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
onPullDownRefresh(async () => {
  try {
    await load();
  } finally {
    uni.stopPullDownRefresh();
  }
});
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

    <view v-if="loading" class="empty">读取任务…</view>
    <view v-else-if="error" class="error" @click="load"
      >{{ error }} / 重试</view
    >
    <view v-else-if="!list.length" class="empty">
      <text>暂无任务</text>
      <text class="hint">下拉刷新</text>
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
      /></view>
      <text v-if="session.taskId === t.id" class="selected-note"
        >继续采样 ›</text
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
  border-left-color: #087f82;
  background: #eef8f6;
}
.stat-row {
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 14px 0 10px;
  border-top: 1px solid #dce6e9;
  border-bottom: 1px solid #dce6e9;
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
  font-size: 11px;
}
.progress {
  margin-top: 4px;
}
.selected-note {
  display: block;
  margin-top: 10px;
  font-size: 11px;
  color: #087f82;
}
.independent {
  border-left: 3px solid transparent;
}
.independent .note {
  margin: 6px 0 0;
}

.task,
.independent {
  border: 1px solid #e4ecef;
  border-left: 3px solid #e4ecef;
}
.task.selected,
.independent.selected {
  border-color: #b4ded8;
  border-left-color: #087f82;
}
.stat-row {
  border: 0;
  background: #f5f9fa;
  padding: 14px 10px;
  border-radius: 12px;
}
.stat-row .value {
  font-size: 24px;
}
.stat-row .caption,
.selected-note {
  font-size: 12px;
}
.refresh {
  padding: 10px;
  font-size: 13px;
}
.independent .list-title {
  margin-bottom: 0;
}
</style>
