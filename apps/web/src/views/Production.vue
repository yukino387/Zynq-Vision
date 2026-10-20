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
      <p>批次由自动过件开始/停止自动创建和关闭，这里只查看运行与记录。</p>
    </div>
    <div class="heading-actions">
      <Status :value="devices.current?.connectionState" />
      <span>{{ activity.label }}</span>
    </div>
  </div>

  <section class="toolbar">
    <label class="toolbar-field">
      <span>设备</span>
      <select v-model="devices.selected" aria-label="检测设备">
        <option v-if="!devices.devices.length" value="">暂无设备</option>
        <option v-for="d in devices.devices" :key="d.id" :value="d.id">
          {{ d.name }}
        </option>
      </select>
    </label>
    <label class="toolbar-field">
      <span>批次</span>
      <select v-model="selected" aria-label="生产批次">
        <option value="">选择批次</option>
        <option v-for="b in batches" :key="b.id" :value="b.id">
          {{ b.name }} · {{ b.status === "OPEN" ? "进行中" : "已结束" }} ·
          {{ b._count?.inspections ?? 0 }} 件
        </option>
      </select>
    </label>
    <RouterLink :to="{ name: 'workbench' }" class="text-button">
      去现场工作台开始/停止检测
    </RouterLink>
  </section>

  <p v-if="error" class="error-box" role="alert">{{ error }}</p>

  <section v-if="batch" class="panel runtime-summary">
    <h3>所选批次 · {{ batch.productionRunId?.slice(0, 8) }}</h3>
    <p>
      产品：{{ batch.snapshot.rules.product }} · 方案：{{
        batch.snapshot.planName
      }}
      / V{{ batch.snapshot.planVersion }} · 模型：{{
        batch.snapshot.modelVersion
      }}
    </p>
    <p v-if="localBatch">
      本机原判已检 {{ terminalState?.runTotal }} 件 · 全机待同步
      {{ terminalState?.pendingSync }} 条
    </p>
    <p class="note">
      以下为所选批次已同步记录。人工结论保留机器原判；尚未同步的本机记录不包含在内。
    </p>
  </section>

  <section class="workbench-grid">
    <div class="panel">
      <section class="side-card">
        <div class="side-card-title">
          <span>已同步批次汇总</span>
          <span v-if="batch" class="mono">{{
            batch.productionRunId?.slice(0, 8)
          }}</span>
        </div>
        <template v-if="summary">
          <p class="mono">
            人工处理后：总数 {{ summary.total }} · 合格
            {{ summary.final.PASS }} · 不合格 {{ summary.final.FAIL }} · 待复核
            {{ summary.pending }}
          </p>
          <p class="mono">
            平台原判（核验后）：合格 {{ summary.machine.PASS }} · 不合格
            {{ summary.machine.FAIL }} · 待复核 {{ summary.machine.REVIEW }} ·
            错误 {{ summary.machine.ERROR }}
          </p>
          <p class="mono">
            已判定件合格率：{{
              summary.passRate === null
                ? "—"
                : (summary.passRate * 100).toFixed(1) + "%"
            }}
          </p>
        </template>
        <p v-else class="note">选择批次查看汇总。</p>
        <p v-if="batch" class="mono">
          产品：{{ batch.snapshot.planName }} / 模型：{{
            batch.snapshot.modelVersion
          }}
        </p>
      </section>
      <section class="side-card">
        <div class="side-card-title">
          <span>最近记录</span>
          <small v-if="loading">加载中…</small>
        </div>
        <button
          v-for="record in records"
          :key="record.id"
          class="record-row"
          @click="detail = record"
        >
          <span
            >平台核验 <Status :value="record.result" /> · 人工
            <Status
              v-if="record.reviewResult"
              :value="record.reviewResult"
            /><span v-else>未复核</span></span
          >
          <span class="mono">#{{ record.frameId ?? "—" }}</span>
          <time class="mono">{{
            new Date(record.createdAt).toLocaleTimeString()
          }}</time>
        </button>
        <p v-if="!records.length" class="note">当前批次还没有记录。</p>
      </section>
    </div>
  </section>

  <Drawer v-if="detail" title="检测详情" @close="detail = null">
    <InspectionDetail :key="detail.id" :inspection="detail" @saved="saved" />
  </Drawer>
</template>
