<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { displayName } from "@vision/shared";
import { api } from "../api";
import { useNotificationStore } from "../stores/notifications";
import AsyncState from "./AsyncState.vue";
import DistributionBar from "./DistributionBar.vue";
import RankBars from "./RankBars.vue";
import Status from "./Status.vue";
import TrendChart from "./TrendChart.vue";
import { UiButton, UiStat, UiTable, UiTabs } from "./ui";

const props = withDefaults(defineProps<{ deviceId?: string }>(), {
  deviceId: "",
});

interface StatsPoint {
  at: string;
  total: number;
  pass: number;
  fail: number;
  review: number;
  error: number;
  passRate: number | null;
}
interface Stats {
  range: { from: string; to: string; bucket: "hour" | "day" };
  totals: {
    total: number;
    pass: number;
    fail: number;
    review: number;
    error: number;
    decided: number;
    passRate: number | null;
    avgLatencyMs: number | null;
    perHour: number;
  };
  series: StatsPoint[];
  classes: { label: string; count: number }[];
  devices: {
    id: string;
    name: string;
    type: string;
    connectionState: string;
    runtimeState: string;
    lastSeenAt: string | null;
    modelVersion: string | null;
    planVersion: string | null;
  }[];
  onlineDevices: number;
}

const notices = useNotificationStore();
const stats = ref<Stats | null>(null),
  error = ref(""),
  busy = ref(false),
  range = ref("7d");
const ranges = [
  { key: "24h", label: "近 24 小时" },
  { key: "7d", label: "近 7 天" },
];
let timer: ReturnType<typeof setInterval> | undefined;

async function load() {
  if (busy.value) return;
  busy.value = true;
  try {
    const now = new Date(),
      from = new Date(
        now.getTime() - (range.value === "7d" ? 7 : 1) * 24 * 3600_000,
      ),
      query = new URLSearchParams({
        from: from.toISOString(),
        to: now.toISOString(),
      });
    if (props.deviceId) query.set("deviceId", props.deviceId);
    stats.value = await api<Stats>(`/inspections/stats?${query}`);
    error.value = "";
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    if (!stats.value) error.value = message;
    else notices.error(e);
  } finally {
    busy.value = false;
  }
}

watch([range, () => props.deviceId], () => void load());
onMounted(() => {
  void load();
  timer = setInterval(() => void load(), 30000);
});
onBeforeUnmount(() => clearInterval(timer));

const devices = computed(() =>
  (stats.value?.devices ?? []).filter((d) => d.type !== "SIMULATOR"),
);
const onlineDevices = computed(
  () =>
    devices.value.filter((device) => device.connectionState === "ONLINE")
      .length,
);
const totals = computed(() => stats.value?.totals);
const passRate = computed(() =>
  totals.value?.passRate == null
    ? null
    : Number((totals.value.passRate * 100).toFixed(1)),
);
const pending = computed(
  () => (totals.value?.review ?? 0) + (totals.value?.error ?? 0),
);

function formatBucket(at: string) {
  const date = new Date(at);
  return stats.value?.range.bucket === "hour"
    ? date.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : date.toLocaleDateString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
      });
}
const volumeSeries = computed(() =>
  (stats.value?.series ?? []).map((point) => ({
    label: formatBucket(point.at),
    value: point.total,
  })),
);
const passRateSeries = computed(() =>
  (stats.value?.series ?? []).map((point) => ({
    label: formatBucket(point.at),
    value: point.passRate == null ? null : point.passRate * 100,
  })),
);
type Slice = {
  label: string;
  value: number;
  tone: "quiet" | "ok" | "info" | "warn" | "crit";
};
const distribution = computed<Slice[]>(() => [
  { label: "合格", value: totals.value?.pass ?? 0, tone: "ok" },
  { label: "不合格", value: totals.value?.fail ?? 0, tone: "crit" },
  { label: "待复核 / 异常", value: pending.value, tone: "warn" },
]);

function time(value: string | null) {
  return value
    ? new Date(value).toLocaleString("zh-CN", { hour12: false })
    : "—";
}
const rangeLabel = computed(() =>
  stats.value
    ? `${time(stats.value.range.from)} — ${time(stats.value.range.to)}`
    : "",
);
</script>

<template>
  <div class="analytics-toolbar">
    <UiTabs v-model="range" :items="ranges" variant="segment" size="sm" />
    <UiButton variant="secondary" icon="refresh" :loading="busy" @click="load">
      {{ busy ? "刷新中…" : "刷新" }}
    </UiButton>
    <span class="muted mono range-label">{{ rangeLabel }}</span>
  </div>

  <AsyncState
    :loading="busy && !stats"
    :error="error"
    :empty="!stats"
    hint="开始检测并完成一件产品后，统计会出现在这里。"
    @retry="load"
  >
    <template v-if="stats">
      <p v-if="stats.totals.total === 0" class="empty-note">
        当前时间范围没有检测记录，统计会随生产自动更新。
        <button
          v-if="range === '24h'"
          type="button"
          class="text-button"
          @click="range = '7d'"
        >
          查看近 7 天
        </button>
      </p>

      <div class="analytics-kpis">
        <UiStat
          label="检测总数"
          :value="totals?.total ?? 0"
          icon="scan"
          :hint="`约 ${(totals?.perHour ?? 0).toFixed(1)} 件 / 小时`"
        />
        <UiStat
          label="合格率"
          :value="passRate"
          unit="%"
          icon="check"
          tone="success"
          :hint="`已判定 ${totals?.decided ?? 0} 件`"
        />
        <UiStat
          label="不合格"
          :value="totals?.fail ?? 0"
          icon="alert"
          tone="crit"
          hint="人工复核后的最终结果"
        />
        <UiStat
          label="待复核 / 异常"
          :value="pending"
          icon="audit"
          tone="warn"
          hint="需要人工处理"
        />
        <UiStat
          label="平均耗时"
          :value="
            totals?.avgLatencyMs == null
              ? null
              : Math.round(totals.avgLatencyMs)
          "
          unit="ms"
          icon="clock"
          hint="从检测记录读取"
        />
        <UiStat
          label="在线设备"
          :value="`${onlineDevices} / ${devices.length}`"
          icon="device"
          to="/diagnostics/registry"
          hint="心跳在线"
        />
      </div>

      <div class="analytics-charts">
        <section class="panel chart-panel">
          <div class="panel-head chart-head">
            <h3>检测量趋势</h3>
            <span class="mono muted">{{ rangeLabel }}</span>
          </div>
          <div class="panel-body">
            <TrendChart
              label="检测量"
              unit=" 件"
              :points="volumeSeries"
              :height="210"
              :min="0"
            />
          </div>
        </section>
        <section class="panel chart-panel">
          <div class="panel-head chart-head">
            <h3>合格率趋势</h3>
            <span class="mono muted">最终结果</span>
          </div>
          <div class="panel-body">
            <TrendChart
              label="合格率"
              unit="%"
              color="var(--green)"
              :points="passRateSeries"
              :height="210"
              :min="0"
              :max="100"
              :decimals="1"
              empty-text="本时段还没有已判定的记录"
            />
          </div>
        </section>
        <section class="panel chart-panel">
          <div class="panel-head chart-head">
            <h3>结果构成</h3>
            <span class="mono muted">{{ totals?.total ?? 0 }} 件</span>
          </div>
          <div class="panel-body">
            <DistributionBar :slices="distribution" unit=" 件" />
          </div>
        </section>
        <section class="panel chart-panel">
          <div class="panel-head chart-head">
            <h3>识别类别 Top</h3>
            <span class="mono muted">检测框数量</span>
          </div>
          <div class="panel-body">
            <RankBars
              :items="stats.classes"
              unit=" 个"
              empty-text="本时段没有检测框数据"
            />
          </div>
        </section>
      </div>

      <div class="analytics-tables">
        <section class="panel table-panel">
          <div class="panel-head">
            <h3>设备状态</h3>
          </div>
          <UiTable>
            <thead>
              <tr>
                <th>设备</th>
                <th>连接</th>
                <th>运行</th>
                <th>模型</th>
                <th>产品方案</th>
                <th>最近心跳</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="device in devices" :key="device.id">
                <td>{{ displayName(device.name) }}</td>
                <td><Status :value="device.connectionState" /></td>
                <td><Status chip :value="device.runtimeState" /></td>
                <td class="mono">{{ device.modelVersion || "—" }}</td>
                <td class="mono">{{ device.planVersion || "—" }}</td>
                <td class="mono">{{ time(device.lastSeenAt) }}</td>
              </tr>
              <tr v-if="!devices.length">
                <td colspan="6" class="table-empty">还没有设备</td>
              </tr>
            </tbody>
          </UiTable>
        </section>
      </div>
    </template>
  </AsyncState>
</template>

<style scoped>
.analytics-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin: 0 0 16px;
}
.range-label {
  font-size: 11px;
}
.empty-note {
  margin: 0 0 14px;
  color: var(--muted);
  font-size: 13px;
}
.analytics-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.analytics-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.chart-panel {
  min-width: 0;
}
.chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.chart-head .muted {
  font-size: 11px;
  font-weight: 400;
}
.analytics-tables {
  display: grid;
  gap: 16px;
  margin-top: 16px;
}
.table-panel .panel-head {
  display: flex;
  align-items: center;
}
.table-empty {
  padding: 22px 14px;
  color: var(--muted);
  text-align: center;
}
@media (max-width: 700px) {
  .analytics-charts {
    grid-template-columns: 1fr;
  }
}
</style>
