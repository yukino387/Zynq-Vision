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
  <view class="page"
    ><text class="title">采样任务</text
    ><view v-if="loading" class="empty">读取任务…</view
    ><view v-else-if="error" class="error" @click="load"
      >{{ error }} / 重试</view
    ><view v-else-if="!list.length" class="empty">
      <text>暂无任务</text>
      <text class="hint">任务由管理员在 Web 端创建后下发到这里。</text>
    </view
    ><view v-for="t in list" :key="t.id" class="card"
      ><view class="row"
        ><text class="list-title">{{ displayName(t.name) }}</text
        ><text class="status">{{ chinese(t.status) }}</text></view
      ><view class="stat-row"
        ><view
          ><text class="value mono">{{ t._count.samples }}</text
          ><text class="caption">已采样</text></view
        ><view
          ><text class="value mono">{{ t.target }}</text
          ><text class="caption">目标样本</text></view
        ></view
      ><button
        :class="session.taskId === t.id ? 'primary' : ''"
        @click="select(t)"
      >
        {{ session.taskId === t.id ? "继续采样" : "选择任务" }}
      </button></view
    ><button
      @click="
        selectTask('');
        uni.switchTab({ url: '/pages/capture/index' });
      "
    >
      独立采样
    </button></view
  >
</template>
