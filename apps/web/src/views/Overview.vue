<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { chinese, terminalActivity } from "@vision/shared";
import type { InspectionBatch, Page } from "@vision/contracts";
import { api, errorText } from "../api";
import { useDeviceStore } from "../stores/devices";
import AsyncState from "../components/AsyncState.vue";
import { UiButton, UiCard, UiBadge, UiStat, UiSelect } from "../components/ui";

const devices = useDeviceStore();
const device = computed(() => devices.current);
const state = computed(() => device.value?.terminal?.state);
const online = computed(() => device.value?.connectionState === "ONLINE");
const activity = computed(() =>
  terminalActivity(state.value ?? null, online.value),
);
const counts = computed(() =>
  state.value?.productionRunId ? state.value.runCounts : state.value?.counts,
);
const total = computed(() =>
  counts.value
    ? Object.values(counts.value).reduce((sum, count) => sum + count, 0)
    : null,
);
const batches = ref<InspectionBatch[]>([]);
const loading = ref(false),
  error = ref("");
const batchLink = computed(() => ({
  name: "production",
  query: { run: state.value?.productionRunId || undefined },
}));
/** 批次名带的 ISO 时间戳对观众没有意义，时间已在副标题里。 */
const batchTitle = (name: string) =>
  name.replace(/\s*·\s*\d{4}-\d\d-\d\dT[\d:.]+Z$/, "");
async function load() {
  const id = device.value?.id;
  batches.value = [];
  if (!id) return;
  loading.value = true;
  error.value = "";
  try {
    const result = await api<Page<InspectionBatch>>(
      `/batches?deviceId=${encodeURIComponent(id)}&pageSize=5&sort=createdAt&order=desc`,
    );
    if (device.value?.id === id) batches.value = result.items.slice(0, 4);
  } catch (e) {
    error.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
async function refresh() {
  try {
    await devices.snapshot();
    await load();
  } catch (e) {
    error.value = errorText(e);
  }
}
watch(() => device.value?.id, load, { immediate: true });
watch(() => state.value?.productionRunId, load);
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>运行概览</h1>
      <p>当前设备、自动检测状态与批次结果。</p>
    </div>
    <div class="heading-actions">
      <UiSelect
        v-if="devices.devices.length > 1"
        v-model="devices.selected"
        aria-label="检测设备"
      >
        <option v-for="item in devices.devices" :key="item.id" :value="item.id">
          {{ item.name }}
        </option>
      </UiSelect>
      <UiButton
        variant="secondary"
        icon="refresh"
        :loading="loading"
        @click="refresh"
        >刷新</UiButton
      >
    </div>
  </div>
  <UiCard padding="none" class="current-device">
    <div class="device-status">
      <div class="device-copy">
        <div class="device-kicker">
          <span>边缘检测节点</span>
          <UiBadge :tone="online ? 'success' : 'warn'" dot :pulse="!online">{{
            online ? "设备在线" : "设备未连接"
          }}</UiBadge>
          <span class="mono device-code"
            >ID / {{ device?.id?.slice(-8) || "UNBOUND" }}</span
          >
        </div>
        <h2>{{ activity.label }}</h2>
        <p class="device-name">
          {{ device?.name || "尚未选择设备" }} ·
          {{
            state?.product?.product ||
            state?.product?.name ||
            "尚未配置产品"
          }}
        </p>
        <p class="device-hint">{{ activity.hint }}</p>
      </div>
      <div class="device-context">
        <div>
          <span>运行模型</span>
          <b class="mono">{{ state?.model?.version ?? "未下发" }}</b>
        </div>
        <div>
          <span>设备协议</span>
          <b class="mono">{{ device?.protocolVersion ?? "未上报" }}</b>
        </div>
        <div>
          <span>最近心跳</span>
          <b class="mono">{{
            state?.receivedAt
              ? new Date(state.receivedAt).toLocaleTimeString("zh-CN")
              : "未上报"
          }}</b>
        </div>
      </div>
      <div class="device-action-col">
        <dl class="device-kpis">
          <div>
            <dt>检测总数</dt>
            <dd>{{ total ?? "—" }}<small>件</small></dd>
          </div>
          <div>
            <dt>待上传</dt>
            <dd>{{ state?.pendingSync ?? 0 }}<small>条</small></dd>
          </div>
          <div>
            <dt>产品版本</dt>
            <dd class="is-text">V{{ state?.product?.version ?? "—" }}</dd>
          </div>
        </dl>
        <UiButton variant="primary" to="/workbench"
          >进入现场检测 <span aria-hidden="true">→</span></UiButton
        >
      </div>
    </div>
    <div class="signal-chain" aria-label="检测链路状态">
      <div class="chain-node" :class="{ 'is-on': online }">
        <span class="chain-index mono">01</span>
        <div class="chain-body">
          <b>图像采集</b><em>OV5640 · RGB565 416×416</em>
        </div>
        <span class="chain-state">{{ online ? "运行" : "待机" }}</span>
      </div>
      <span class="chain-link" aria-hidden="true"></span>
      <div class="chain-node" :class="{ 'is-on': online && !!state?.model }">
        <span class="chain-index mono">02</span>
        <div class="chain-body">
          <b>边缘推理</b><em>PL 加速器 · INT8</em>
        </div>
        <span class="chain-state">{{ state?.model?.version ?? "未下发" }}</span>
      </div>
      <span class="chain-link" aria-hidden="true"></span>
      <div class="chain-node" :class="{ 'is-on': online && !!state?.product }">
        <span class="chain-index mono">03</span>
        <div class="chain-body">
          <b>规则判定</b
          ><em>产品方案 V{{ state?.product?.version ?? "—" }}</em>
        </div>
        <span class="chain-state">{{
          state?.last ? chinese(state.last.result) : "等待结果"
        }}</span>
      </div>
      <span class="chain-link" aria-hidden="true"></span>
      <div class="chain-node" :class="{ 'is-on': online }">
        <span class="chain-index mono">04</span>
        <div class="chain-body">
          <b>记录追溯</b><em>平台批次与证据链</em>
        </div>
        <span class="chain-state">{{
          state?.pendingSync ? `${state.pendingSync} 条待上传` : "已同步"
        }}</span>
      </div>
    </div>
  </UiCard>

  <section class="section-space">
    <div class="section-heading">
      <div>
        <h2>{{ state?.productionRunId ? "本批自动检测" : "设备累计检测" }}</h2>
        <p class="muted">
          {{
            online ? "设备原始判定，包含待上传记录。" : "上次上报的设备数据。"
          }}
          批次页查看已上传记录及更正结果。
        </p>
      </div>
      <UiButton variant="ghost" :to="batchLink">查看批次</UiButton>
    </div>
    <div class="counts">
      <UiStat label="检测总件数" :value="total" unit="件" :to="batchLink" />
      <UiStat
        label="合格"
        :value="counts?.PASS ?? null"
        unit="件"
        tone="success"
        :to="batchLink"
      />
      <UiStat
        label="不合格"
        :value="counts?.FAIL ?? null"
        unit="件"
        tone="crit"
        :to="batchLink"
      />
      <UiStat
        label="判定不确定"
        :value="counts?.REVIEW ?? null"
        unit="件"
        hint="证据不足，未计入合格或不合格"
        :to="batchLink"
      />
      <UiStat
        label="检测错误"
        :value="counts?.ERROR ?? null"
        unit="件"
        hint="检测执行失败，查看错误原因"
        :to="batchLink"
      />
    </div>
    <p v-if="state?.pendingSync" class="muted">
      {{ state.pendingSync }} 条设备记录待上传。
    </p>
  </section>

  <section class="section-space">
    <div class="section-heading">
      <h2>最近批次</h2>
      <UiButton variant="ghost" to="/production">全部批次</UiButton>
    </div>
    <AsyncState :loading="loading" :error="error" @retry="load">
      <div v-if="batches.length" class="batch-list">
        <RouterLink
          v-for="batch in batches"
          :key="batch.id"
          class="batch-row"
          :to="{
            name: 'production',
            query: { run: batch.productionRunId || undefined },
          }"
        >
          <div>
            <b>{{ batchTitle(batch.name) }}</b
            ><small>{{
              new Date(batch.createdAt).toLocaleString("zh-CN")
            }}</small>
          </div>
          <span class="batch-metric">
            <em>已检</em>
            <b class="mono">{{ batch._count?.inspections ?? "—" }}</b>
            <small>件</small>
          </span>
          <span class="batch-state" :class="{ open: batch.status === 'OPEN' }">{{
            batch.status === "OPEN" ? "进行中" : "已结束"
          }}</span>
          <span class="batch-link">查看结果 <i aria-hidden="true">→</i></span>
        </RouterLink>
      </div>
      <p v-else class="muted">
        {{
          device
            ? "此设备暂无已上传批次。开始自动检测后会自动创建批次。"
            : "选择设备后查看生产批次。"
        }}
      </p>
    </AsyncState>
  </section>
</template>

<style scoped>
.current-device,
.section-heading,
.batch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}
.current-device h2 {
  margin: 16px 0 8px;
  font-size: 26px;
}
.current-device p {
  margin: 8px 0;
}
.section-space {
  margin-top: 28px;
}
.section-heading {
  margin-bottom: 16px;
}
.section-heading h2 {
  margin: 0;
  font-size: 18px;
}
.section-heading p {
  margin: 8px 0 0;
  font-size: 13px;
}
.counts {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}
.batch-list {
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface);
}
.batch-row {
  padding: 18px 20px;
  text-decoration: none;
  color: var(--ink);
}
.batch-row + .batch-row {
  border-top: 1px solid var(--line);
}
.batch-row:hover {
  background: var(--surface-2);
}
.batch-row div {
  flex: 1;
}
.batch-row small {
  display: block;
  margin-top: 6px;
  color: var(--muted);
}
@media (max-width: 1100px) {
  .counts {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .counts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .current-device {
    align-items: flex-start;
    flex-direction: column;
  }
  .batch-row {
    flex-wrap: wrap;
  }
}
</style>
