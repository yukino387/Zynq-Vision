<script setup lang="ts">
import { chinese, displayName, statusTone } from "@vision/shared";
import { ref, computed, watch } from "vue";
import { onShow } from "@dcloudio/uni-app";
import type { Page, Source } from "@vision/contracts";
import { request, requireLogin, notify } from "../../state";
import { live } from "../../live";
import { queue } from "../../queue";
import RemoteImage from "../../components/RemoteImage.vue";

interface Inspection {
  id: string;
  result: string;
  source: Source;
  createdAt: string;
  modelVersion: string | null;
  sample: { name: string; assets?: { id: string; kind: string }[] };
  detections: unknown[];
}
const records = ref<Inspection[]>([]),
  page = ref(1),
  total = ref(0),
  loading = ref(false),
  error = ref(""),
  filter = ref<"ALL" | "REVIEW" | "REAL">("ALL");
const pending = computed(
  () => queue.items.filter((i) => i.status !== "SYNCED").length,
);
async function load(append = false) {
  if (!requireLogin()) return;
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const nextPage = append ? page.value + 1 : 1;
    const result = await request<Page<Inspection>>(
      `/inspections?page=${nextPage}&pageSize=20${
        filter.value === "REVIEW"
          ? "&reviewed=false"
          : filter.value === "REAL"
            ? "&realOnly=true"
            : ""
      }`,
    );
    records.value = append ? [...records.value, ...result.items] : result.items;
    total.value = result.total;
    page.value = nextPage;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    loading.value = false;
  }
}
function switchFilter(value: "ALL" | "REVIEW" | "REAL") {
  if (loading.value || filter.value === value) return;
  filter.value = value;
  void load();
}
function preview(item: Inspection) {
  return item.sample.assets?.find((a) => a.kind === "PREVIEW")?.id;
}
onShow(() => load());
// 另一台设备完成检测时，列表自动回到第一页显示最新记录。
let refreshTimer: ReturnType<typeof setTimeout> | null = null;
watch(
  () => live.completedAt,
  () => {
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => void load(), 500);
  },
);
</script>

<template>
  <view class="page">
    <view class="head-row">
      <view>
        <text class="eyebrow">证据与复核</text>
        <text class="title">检测记录</text>
      </view>
      <text class="mono total">{{ total }} 条</text>
    </view>

    <view class="filter-row">
      <text
        class="filter"
        :class="{ active: filter === 'ALL' }"
        @click="switchFilter('ALL')"
        >全部</text
      >
      <text
        class="filter"
        :class="{ active: filter === 'REVIEW' }"
        @click="switchFilter('REVIEW')"
        >待复核</text
      >
      <text
        class="filter"
        :class="{ active: filter === 'REAL' }"
        @click="switchFilter('REAL')"
        >真实</text
      >
      <text
        class="filter-action"
        @click="uni.navigateTo({ url: '/pages/sync/index' })"
        >{{ pending }} 待同步 →</text
      >
    </view>

    <view v-if="error" class="error" @click="load()"
      >{{ error }} / 点击重试</view
    >
    <view v-if="loading && !records.length" class="empty"
      >正在读取检测记录…</view
    >
    <view v-if="!records.length && !loading && !error" class="empty">
      <text>{{
        filter === "REVIEW"
          ? "没有待复核记录"
          : filter === "REAL"
            ? "没有真实设备记录"
            : "暂无检测记录"
      }}</text>
      <text class="hint">到「采样」拍一张，或连接板端后同步一次。</text>
    </view>

    <view
      v-for="i in records"
      :key="i.id"
      class="record"
      @click="uni.navigateTo({ url: `/pages/detail/index?id=${i.id}` })"
    >
      <view class="thumb">
        <RemoteImage :asset-id="preview(i)" label="无预览" />
        <text v-if="i.source === 'SIMULATION'" class="thumb-tag">模拟</text>
      </view>
      <view class="record-main">
        <view class="record-top">
          <text class="status" :class="statusTone(i.result)"
            >● {{ chinese(i.result) }}</text
          >
          <text class="mono time">{{
            new Date(i.createdAt).toLocaleString()
          }}</text>
        </view>
        <text class="record-name">{{ displayName(i.sample.name) }}</text>
        <view class="record-foot">
          <text class="mono">{{ i.detections.length }} 个目标</text>
          <text class="mono model">{{ i.modelVersion ?? "模型未上报" }}</text>
        </view>
      </view>
      <text class="chevron">›</text>
    </view>

    <button
      v-if="records.length < total"
      :loading="loading"
      :disabled="loading"
      @click="load(true)"
    >
      加载更多
    </button>
    <view v-if="loading && records.length" class="empty">正在读取…</view>
  </view>
</template>

<style scoped>
.head-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
}
.head-row .title {
  margin-bottom: 0;
}
.total {
  font-size: 11px;
  color: #637d87;
  padding-bottom: 6px;
}
.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 0 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid #dce6e9;
}
.filter {
  font-size: 11px;
  padding: 5px 10px;
  border: 1px solid #dce6e9;
  color: #486571;
  min-height: 30px;
}
.filter.active {
  background: #087f82;
  border-color: #087f82;
  color: #ffffff;
}
.filter-action {
  margin-left: auto;
  font-size: 11px;
  color: #087f82;
}
.record {
  display: flex;
  align-items: stretch;
  gap: 12px;
  background: #ffffff;
  border-top: 1px solid #dce6e9;
  border-bottom: 1px solid #dce6e9;
  padding: 12px;
  margin-bottom: -1px;
}
.record:active {
  background: #ecebdf;
}
.thumb {
  width: 76px;
  height: 76px;
  flex-shrink: 0;
  position: relative;
  border: 1px solid #e6edef;
  overflow: hidden;
}
.thumb-tag {
  position: absolute;
  left: 0;
  bottom: 0;
  background: #f5e7c4;
  color: #7a5a1c;
  font-size: 11px;
  padding: 1px 4px;
  border-top: 1px solid #c2ab76;
  border-right: 1px solid #c2ab76;
}
.record-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
}
.record-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.record-top .status {
  font-size: 11px;
  white-space: nowrap;
}
.time {
  font-size: 11px;
  color: #637d87;
  white-space: nowrap;
}
.record-name {
  font-size: 12px;
  color: #17343e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.record-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #637d87;
}
.record-foot .model {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.chevron {
  align-self: center;
  color: #8ca4ad;
  font-size: 18px;
}

.filter-row {
  flex-wrap: wrap;
  border: 0;
  gap: 8px;
  padding-bottom: 0;
  margin-bottom: 20px;
}
.filter {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 14px;
  min-height: 42px;
  font-size: 13px;
  border-radius: 12px;
  background: white;
}
.filter-action {
  font-size: 12px;
  padding: 10px 0;
}
.record {
  gap: 11px;
  border: 1px solid #e4ecef;
  border-radius: 16px;
  padding: 12px;
  margin-bottom: 12px;
}
.thumb {
  width: 64px;
  height: 76px;
  border: 0;
  border-radius: 10px;
}
.record-top {
  flex-wrap: wrap;
  gap: 2px;
}
.record-top .status {
  font-size: 12px;
}
.time {
  font-size: 10px;
}
.record-name {
  font-size: 13px;
  font-weight: 600;
}
.record-foot {
  font-size: 11px;
}
.total {
  font-size: 12px;
}
</style>
