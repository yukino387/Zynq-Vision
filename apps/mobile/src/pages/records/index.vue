<script setup lang="ts">
import { chinese, displayName, statusTone } from "@vision/shared";
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import type { Page, Source } from "@vision/contracts";
import { request, requireLogin, notify } from "../../state";
import { queue } from "../../queue";
interface Inspection {
  id: string;
  result: string;
  source: Source;
  createdAt: string;
  modelVersion: string | null;
  sample: { name: string };
  detections: unknown[];
}
const records = ref<Inspection[]>([]),
  page = ref(1),
  total = ref(0),
  loading = ref(false),
  error = ref("");
async function load(append = false) {
  if (!requireLogin()) return;
  loading.value = true;
  error.value = "";
  try {
    if (!append) page.value = 1;
    const result = await request<Page<Inspection>>(
      `/inspections?page=${page.value}&pageSize=20`,
    );
    records.value = append ? [...records.value, ...result.items] : result.items;
    total.value = result.total;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    loading.value = false;
  }
}
onShow(() => load());
</script>
<template>
  <view class="page"
    ><text class="title">检测记录</text
    ><text class="subtitle"></text
    ><view class="card" @click="uni.navigateTo({ url: '/pages/sync/index' })"
      ><view class="row"
        ><text>本地手机采样</text
        ><text class="mono"
          >{{ queue.items.filter((i) => i.status !== "SYNCED").length }} 待同步
        </text></view
      ></view
    ><view v-if="error" class="error" @click="load()"
      >{{ error }} / 点击重试</view
    ><view v-if="!records.length && !loading" class="empty">
      <text>暂无检测记录</text>
      <text class="hint">到「采样」拍一张，或连接板端后同步一次。</text>
    </view
    ><view
      v-for="i in records"
      :key="i.id"
      class="card"
      @click="uni.navigateTo({ url: `/pages/detail/index?id=${i.id}` })"
      ><view class="row"
        ><text class="status" :class="statusTone(i.result)"
          >● {{ chinese(i.result) }}</text
        ><text class="mono" style="font-size: 10px">{{
          new Date(i.createdAt).toLocaleString()
        }}</text></view
      ><text class="list-title" style="margin-top: 18px">{{
        displayName(i.sample.name)
      }}</text
      ><text v-if="i.source === 'SIMULATION'" class="tag">模拟推理</text
      ><text class="list-caption" style="margin-top: 12px"
        >模型 {{ i.modelVersion ?? "未上报" }} /
        {{ i.detections.length }} 个检测目标</text
      ></view
    ><button
      v-if="records.length < total"
      :loading="loading"
      @click="
        page++;
        load(true);
      "
    >
      加载更多</button
    ><view v-if="loading" class="empty">正在读取…</view></view
  >
</template>
