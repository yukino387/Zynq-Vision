<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type {
  BatchSummary,
  Inspection,
  InspectionBatch,
  Page,
} from "@vision/contracts";
import { api, errorText } from "../api";
import { useDeviceStore } from "../stores/devices";
import { useRoute } from "vue-router";
import { terminalActivity } from "@vision/shared";
import InspectionDetail from "../components/InspectionDetail.vue";
import Status from "../components/Status.vue";
import Drawer from "../components/Drawer.vue";
import Icon from "../components/Icon.vue";
import { UiButton, UiCard, UiSelect, UiBadge, UiStat } from "../components/ui";

const devices = useDeviceStore(),
  route = useRoute();
const batches = ref<InspectionBatch[]>([]),
  selected = ref(""),
  summary = ref<BatchSummary | null>(null),
  records = ref<Inspection[]>([]),
  detail = ref<Inspection | null>(null),
  loading = ref(false),
  error = ref("");
const batch = computed(() =>
  batches.value.find((b) => b.id === selected.value),
);
const terminalState = computed(() => devices.current?.terminal?.state ?? null);
const activity = computed(() =>
  terminalActivity(
    terminalState.value,
    devices.current?.connectionState === "ONLINE",
  ),
);
const localBatch = computed(
  () =>
    !!batch.value?.productionRunId &&
    batch.value.productionRunId === terminalState.value?.productionRunId,
);
async function saved() {
  if (detail.value)
    detail.value = await api<Inspection>(`/inspections/${detail.value.id}`);
  await refresh();
}
let timer: ReturnType<typeof setInterval> | undefined;

async function loadBatches() {
  const deviceId = devices.current?.id;
  try {
    const list = await api<Page<InspectionBatch>>(
      `/batches?pageSize=100${deviceId ? `&deviceId=${encodeURIComponent(deviceId)}` : ""}`,
    );
    batches.value = list.items;
    const requested = batches.value.find(
      (b) => b.productionRunId === route.query.run,
    );
    if (requested) selected.value = requested.id;
    if (!batches.value.some((b) => b.id === selected.value))
      selected.value =
        batches.value.find((b) => b.status === "OPEN")?.id ??
        batches.value[0]?.id ??
        "";
  } catch (e) {
    error.value = errorText(e);
  }
}
async function refresh() {
  const id = selected.value;
  if (!id) {
    summary.value = null;
    records.value = [];
    return;
  }
  loading.value = true;
  try {
    const [stats, list] = await Promise.all([
      api<BatchSummary>(`/batches/${id}/summary`),
      api<Page<Inspection>>(
        `/inspections?batchId=${encodeURIComponent(id)}&pageSize=20`,
      ),
    ]);
    if (selected.value === id) {
      summary.value = stats;
      records.value = list.items;
      error.value = "";
    }
  } catch (e) {
    if (selected.value === id) error.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
onMounted(async () => {
  await loadBatches();
  await refresh();
  timer = setInterval(() => {
    void loadBatches();
    void refresh();
  }, 5000);
});
onUnmounted(() => clearInterval(timer));
watch(selected, refresh);
watch(
  () => route.query.run,
  async () => {
    await loadBatches();
    await refresh();
  },
);
watch(
  () => devices.current?.id,
  async () => {
    selected.value = "";
    await loadBatches();
    await refresh();
  },
);
</script>

<template>
  <div class="page-heading instrument-heading">
    <div>
      <h1>生产批次</h1>
      <p>
        批次随现场工作台自动过件开始/停止自动创建与关闭，此页面供实时统计复核与历史追踪。
      </p>
    </div>
    <div class="heading-actions">
      <Status :value="devices.current?.connectionState" />
      <UiBadge
        tone="forest"
        chip
        dot
        :pulse="
          activity.label.includes('进行中') || activity.label.includes('自动')
        "
      >
        {{ activity.label }}
      </UiBadge>
    </div>
  </div>

  <!-- 顶部筛选工具栏 -->
  <section class="batch-toolbar">
    <div class="toolbar-group">
      <span class="toolbar-label">检测设备</span>
      <UiSelect v-model="devices.selected" aria-label="检测设备" size="md">
        <option v-if="!devices.devices.length" value="">暂无设备</option>
        <option v-for="d in devices.devices" :key="d.id" :value="d.id">
          {{ d.name }}
        </option>
      </UiSelect>
    </div>

    <div class="toolbar-group batch-select-group">
      <span class="toolbar-label">生产批次</span>
      <UiSelect v-model="selected" aria-label="生产批次" size="md">
        <option value="">请选择批次</option>
        <option v-for="b in batches" :key="b.id" :value="b.id">
          {{ b.name }} · {{ b.status === "OPEN" ? "进行中" : "已结束" }} ·
          {{ b._count?.inspections ?? 0 }} 件
        </option>
      </UiSelect>
    </div>

    <div class="toolbar-actions-end">
      <UiButton
        variant="outline"
        size="md"
        icon="camera"
        :to="{ name: 'workbench' }"
      >
        现场工作台
      </UiButton>
    </div>
  </section>

  <div v-if="error" class="error-banner" role="alert">
    <Icon name="alert" :size="16" />
    <span>{{ error }}</span>
  </div>

  <!-- 所选批次上下文卡片 -->
  <UiCard v-if="batch" variant="accent" padding="md" class="batch-info-card">
    <div class="batch-info-header">
      <div class="batch-title-row">
        <h3>当前批次：{{ batch.name }}</h3>

        <UiBadge
          :tone="batch.status === 'OPEN' ? 'success' : 'neutral'"
          chip
          size="sm"
        >
          {{ batch.status === "OPEN" ? "进行中" : "已归档" }}
        </UiBadge>
      </div>
      <div class="batch-tags">
        <span class="batch-tag-item"
          >产品：<b>{{ batch.snapshot.rules.product }}</b></span
        >
        <span class="batch-tag-item"
          >规则版本：<b>V{{ batch.snapshot.planVersion }}</b></span
        >
        <span class="batch-tag-item"
          >模型：<b>{{ batch.snapshot.modelVersion }}</b></span
        >
      </div>
    </div>
    <div v-if="localBatch" class="batch-sub-stats mono">
      <span
        >本机原判已检：<b>{{ terminalState?.runTotal }}</b> 件</span
      >
      <span class="divider">|</span>
      <span
        >全机待同步：<b>{{ terminalState?.pendingSync }}</b> 条</span
      >
    </div>
    <p class="batch-note">
      本页统计已经上传到平台的单件记录。设备在每件产品离开画面后保存并计数；全机待上传数量包含历史批次和补检，上传后按各自批次归入。
    </p>
  </UiCard>

  <!-- 批次统计与记录两栏布局 -->
  <div class="batch-content-grid">
    <!-- 左侧：指标总览 -->
    <div class="batch-stats-col">
      <UiCard
        title="批次指标汇总"
        subtitle="所选批次判定与合格率统计"
        padding="md"
      >
        <template v-if="summary">
          <div class="stat-cards-grid">
            <UiStat
              label="检测总件数"
              :value="summary.total"
              unit="件"
              icon="scan"
            />
            <UiStat
              label="综合合格率"
              :value="
                summary.passRate === null
                  ? '暂无已判定记录'
                  : (summary.passRate * 100).toFixed(1)
              "
              unit="%"
              icon="gauge"
              :tone="
                summary.passRate && summary.passRate >= 0.95
                  ? 'success'
                  : 'warn'
              "
            />
            <UiStat
              label="最终合格"
              :value="summary.final.PASS"
              unit="件"
              tone="success"
            />
            <UiStat
              label="最终不合格"
              :value="summary.final.FAIL"
              unit="件"
              tone="crit"
            />
          </div>

          <div class="summary-details">
            <h4 class="sub-header">机器原判与最终结论</h4>
            <div class="verdict-compare-table">
              <div class="compare-row compare-header">
                <span>判定类型</span>
                <span>平台机器原判</span>
                <span>最终处理结论</span>
              </div>
              <div class="compare-row">
                <span class="verdict-tag ok">合格</span>
                <span class="mono">{{ summary.machine.PASS }}</span>
                <span class="mono font-semibold">{{ summary.final.PASS }}</span>
              </div>
              <div class="compare-row">
                <span class="verdict-tag fail">不合格</span>
                <span class="mono">{{ summary.machine.FAIL }}</span>
                <span class="mono font-semibold">{{ summary.final.FAIL }}</span>
              </div>
              <div class="compare-row">
                <span class="verdict-tag review">待复核</span>
                <span class="mono">{{ summary.machine.REVIEW }}</span>
                <span class="mono font-semibold">{{ summary.pending }}</span>
              </div>
              <div class="compare-row">
                <span class="verdict-tag error">异常</span>
                <span class="mono">{{ summary.machine.ERROR }}</span>
                <span class="mono font-semibold">{{
                  summary.final.ERROR
                }}</span>
              </div>
            </div>
          </div>
        </template>
        <p v-else class="empty-hint">请在上方选择一个生产批次以查看指标。</p>
      </UiCard>
    </div>

    <!-- 右侧：最近过件流水 -->
    <div class="batch-records-col">
      <UiCard
        title="最近过件明细"
        subtitle="点击行打开单件检测详情与复核"
        padding="md"
      >
        <template #actions>
          <UiBadge v-if="loading" tone="info" size="sm">同步中…</UiBadge>
          <span v-else class="records-count mono"
            >{{ records.length }} 条记录</span
          >
        </template>

        <div class="records-list">
          <button
            v-for="record in records"
            :key="record.id"
            class="record-item"
            @click="detail = record"
          >
            <div class="record-left">
              <span v-if="record.frameId != null" class="record-id mono"
                >图像帧 {{ record.frameId }}</span
              >
              <time class="record-time mono">{{
                new Date(record.createdAt).toLocaleTimeString()
              }}</time>
            </div>
            <div class="record-middle">
              <span class="record-verdict">
                原判 <Status :value="record.result" />
              </span>
              <span class="record-sep">/</span>
              <span class="record-verdict">
                人工
                <Status
                  v-if="record.reviewResult"
                  :value="record.reviewResult"
                /><span v-else class="text-muted">未复核</span>
              </span>
            </div>
            <div class="record-right">
              <span class="record-arrow">查看</span>
            </div>
          </button>

          <p v-if="!records.length" class="empty-hint">
            当前批次暂无已同步检测记录。
          </p>
        </div>
      </UiCard>
    </div>
  </div>

  <!-- 详情抽屉 -->
  <Drawer v-if="detail" title="检测详情" @close="detail = null">
    <InspectionDetail :key="detail.id" :inspection="detail" @saved="saved" />
  </Drawer>
</template>

<style scoped>
.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  padding: 12px 18px;
  border-radius: var(--radius, 8px);
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-label {
  font-size: 13px;
  font-weight: 550;
  color: var(--muted);
  white-space: nowrap;
}

.batch-select-group {
  flex: 1;
  min-width: 260px;
}

.toolbar-actions-end {
  margin-left: auto;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--crit-bg, #f5e0da);
  border: 1px solid var(--crit-line, #d9a097);
  color: var(--red, #b6372a);
  padding: 10px 14px;
  border-radius: var(--radius, 6px);
  font-size: 13px;
  margin-bottom: 16px;
}

/* 批次上下文卡片 */
.batch-info-card {
  margin-bottom: 24px;
}

.batch-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.batch-title-row h3 {
  margin: 0;
  font-size: 17px;
  color: var(--ink);
}

.batch-tags {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.batch-tag-item {
  font-size: 13px;
  color: var(--muted);
}

.batch-tag-item b {
  color: var(--ink);
  font-weight: 550;
}

.batch-sub-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--ink-2);
}

.batch-sub-stats .divider {
  color: var(--line-strong);
}

.batch-note {
  font-size: 12px;
  color: var(--muted);
  margin: 10px 0 0;
  line-height: 1.5;
}

/* 两栏内容栅格 */
.batch-content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.stat-cards-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.sub-header {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 10px;
}

.verdict-compare-table {
  border: 1px solid var(--line);
  border-radius: var(--radius, 6px);
  overflow: hidden;
  font-size: 13px;
}

.compare-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
  align-items: center;
}

.compare-row:last-child {
  border-bottom: none;
}

.compare-header {
  background: var(--surface-2);
  font-weight: 600;
  font-size: 12px;
  color: var(--ink-2);
}

.verdict-tag {
  font-weight: 550;
}
.verdict-tag.ok {
  color: var(--green, #27734b);
}
.verdict-tag.fail {
  color: var(--red, #b6372a);
}
.verdict-tag.review {
  color: var(--amber, #98610b);
}
.verdict-tag.error {
  color: var(--muted);
}

.font-semibold {
  font-weight: 600;
}

/* 记录明细列表 */
.records-count {
  font-size: 12px;
  color: var(--muted);
}

.records-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 600px;
  overflow-y: auto;
}

.record-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius, 6px);
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
  min-height: 48px;
}

.record-item:hover {
  background: var(--surface-2);
  border-color: var(--line-strong);
  transform: translateX(2px);
}

.record-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 70px;
}

.record-id {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

.record-time {
  font-size: 11px;
  color: var(--muted);
}

.record-middle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.record-sep {
  color: var(--line-strong);
}

.record-verdict {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.text-muted {
  color: var(--muted);
}

.record-right {
  margin-left: auto;
}

.record-arrow {
  font-size: 12px;
  color: var(--forest);
  font-weight: 550;
}

.empty-hint {
  font-size: 13px;
  color: var(--muted);
  text-align: center;
  padding: 24px 0;
  margin: 0;
}

@media (max-width: 900px) {
  .batch-content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
