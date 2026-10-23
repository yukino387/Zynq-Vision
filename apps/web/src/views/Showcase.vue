<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { chinese, displayName, terminalActivity } from "@vision/shared";
import type { Inspection } from "@vision/contracts";
import { api, post, errorText } from "../api";
import { useDeviceStore } from "../stores/devices";
import Icon from "../components/Icon.vue";

const devices = useDeviceStore();
const root = ref<HTMLElement | null>(null);
const now = ref(Date.now()),
  busy = ref(false),
  message = ref("");
const full = ref(false),
  boxesVisible = ref(true),
  records = ref<Inspection[]>([]);
const device = computed(() => devices.current);
const state = computed(() => device.value?.terminal?.state);
const online = computed(() => device.value?.connectionState === "ONLINE");
const active = computed(() => online.value && state.value?.production);
const preview = computed(() => {
  const p = device.value && devices.previews[device.value.id];
  return online.value && p && now.value - Date.parse(p.receivedAt) < 4000
    ? p
    : null;
});
const activity = computed(() =>
  terminalActivity(state.value ?? null, online.value),
);
const counts = computed(() =>
  state.value?.productionRunId ? state.value.runCounts : state.value?.counts,
);
const total = computed(() =>
  counts.value ? Object.values(counts.value).reduce((a, b) => a + b, 0) : null,
);
const passRate = computed(() => {
  const c = counts.value;
  return c && c.PASS + c.FAIL ? (c.PASS / (c.PASS + c.FAIL)) * 100 : null;
});
const fps = computed(() =>
  online.value && state.value?.fresh
    ? (state.value.fps ?? device.value?.telemetry?.fps ?? null)
    : null,
);
const latency = computed(() =>
  online.value && device.value?.telemetry?.inferenceUs != null
    ? device.value.telemetry.inferenceUs / 1000
    : null,
);
const result = computed(() => state.value?.last);
const lastLabel = computed(() =>
  result.value ? chinese(result.value.result) : "等待第一件",
);
const resultClass = computed(() =>
  result.value?.result === "PASS"
    ? "pass"
    : result.value?.result === "FAIL"
      ? "fail"
      : "neutral",
);
const product = computed(
  () =>
    state.value?.product?.product ||
    state.value?.product?.name ||
    "尚未配置产品",
);
const level = computed(() => preview.value?.level);
const timing = computed(() =>
  online.value && state.value?.fresh ? state.value.timing : null,
);
const stages = computed(() => [
  { label: "输入搬运", value: timing.value?.prepareMs },
  { label: "PL 卷积", value: timing.value?.convMs },
  { label: "张量提取", value: timing.value?.extractMs },
]);
const timingMax = computed(() =>
  Math.max(1, ...stages.value.map((s) => s.value ?? 0)),
);
const detections = computed(() => preview.value?.detections ?? []);
const confidence = computed(() =>
  detections.value.length
    ? Math.max(...detections.value.map((d) => d.confidence)) * 100
    : null,
);
const rules = computed(() => state.value?.product?.checks ?? []);
const memory = computed(() =>
  state.value?.memoryTotal
    ? (state.value.memoryUsed / state.value.memoryTotal) * 100
    : null,
);
const uptime = computed(() => {
  const seconds = state.value?.uptime;
  if (seconds == null) return "—";
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
});
const time = computed(() =>
  new Date(now.value).toLocaleTimeString("zh-CN", { hour12: false }),
);
const date = computed(() =>
  new Date(now.value)
    .toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    })
    .replaceAll("/", "."),
);
const clock = setInterval(() => {
  now.value = Date.now();
}, 1000);
async function loadRecords() {
  const id = device.value?.id;
  if (!id) {
    records.value = [];
    return;
  }
  try {
    const data = await api<{ items: Inspection[] }>(
      `/inspections?deviceId=${encodeURIComponent(id)}&realOnly=true&pageSize=5&sort=createdAt&order=desc`,
    );
    if (device.value?.id === id) records.value = data.items;
  } catch (e) {
    message.value = errorText(e);
  }
}
watch(
  () => device.value?.id,
  (id, old) => {
    if (old) devices.unwatchPreview(old);
    records.value = [];
    message.value = "";
    if (id) devices.watchPreview(id);
    void loadRecords();
  },
  { immediate: true },
);
watch(() => state.value?.last?.sequence, loadRecords);
async function control() {
  if (!device.value || busy.value) return;
  busy.value = true;
  message.value = "";
  try {
    await post(`/devices/${device.value.id}/commands`, {
      type: active.value ? "STOP_INSPECTION" : "START_INSPECTION",
    });
    await devices.snapshot();
  } catch (e) {
    message.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function fullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await root.value?.requestFullscreen();
  } catch {
    message.value = "浏览器未允许全屏，请使用 F11。";
  }
}
function onFull() {
  full.value = !!document.fullscreenElement;
}
document.addEventListener("fullscreenchange", onFull);
onBeforeUnmount(() => {
  clearInterval(clock);
  document.removeEventListener("fullscreenchange", onFull);
  if (device.value) devices.unwatchPreview(device.value.id);
});
const trend = computed(() => {
  const values = devices.history
    .slice(-40)
    .map((h) => h.fps)
    .filter((v): v is number => v != null && Number.isFinite(v));
  if (values.length < 2) return "";
  const max = Math.max(...values, 1),
    min = Math.min(...values, 0);
  return values
    .map(
      (v, i) =>
        `${(i / (values.length - 1)) * 240},${44 - ((v - min) / (max - min)) * 32}`,
    )
    .join(" ");
});
</script>

<template>
  <div ref="root" class="showcase">
    <header class="show-header">
      <RouterLink to="/overview" class="identity" aria-label="返回运行概览"
        ><span class="brand-emblem"><Icon name="scan" :size="27" /></span
        ><span class="wordmark"
          >VISION<span>.</span><small>EDGE INTELLIGENCE</small></span
        ></RouterLink
      >
      <nav class="show-tabs" aria-label="演示导航">
        <span class="selected"><i></i>实时检测</span
        ><RouterLink to="/production"
          >生产记录<Icon name="chart" :size="14"
        /></RouterLink>
      </nav>
      <div class="header-end">
        <span class="show-clock"
          >{{ time }}<small>{{ date }}</small></span
        ><button
          class="round-button"
          :aria-label="full ? '退出全屏' : '进入全屏'"
          @click="fullscreen"
        >
          <svg
            width="19"
            height="19"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
          >
            <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" />
          </svg></button
        ><RouterLink
          class="round-button"
          to="/workbench"
          aria-label="返回现场工作台"
          ><Icon name="device" :size="19"
        /></RouterLink>
      </div>
    </header>

    <div class="show-content">
      <div class="intro">
        <div>
          <p class="eyebrow"><i></i>FPGA POWERED VISION SYSTEM</p>
          <h1>看见细节<span>，</span>判断品质<span>。</span></h1>
          <p class="intro-copy">感知、计算、判断。在边缘，实时发生。</p>
        </div>
        <div class="connection">
          <Icon name="wifi" :size="21" />
          <div>
            <b>{{ online ? "边缘终端已连接" : "等待边缘终端" }}</b
            ><small>{{ device?.name || "连接设备后显示实时检测" }}</small>
          </div>
          <i :class="{ connected: online }"></i>
        </div>
      </div>
      <div class="show-grid">
        <section class="soft-card vision-card" aria-label="实时检测视频">
          <div class="card-heading">
            <div>
              <span class="section-number">01</span>
              <h2>实时视野</h2>
              <span class="english-label">LIVE VISION</span>
            </div>
            <button
              class="text-control"
              :aria-pressed="boxesVisible"
              @click="boxesVisible = !boxesVisible"
            >
              <Icon name="scan" :size="15" />{{
                boxesVisible ? "隐藏标记" : "显示标记"
              }}
            </button>
          </div>
          <div class="video-well">
            <div class="video-top">
              <span class="live-tag" :class="{ streaming: !!preview }"
                ><i></i>{{ preview ? "LIVE" : "STANDBY" }}</span
              ><span>{{
                preview ? `${preview.width} × ${preview.height}` : "CAMERA / 01"
              }}</span>
            </div>
            <div
              v-if="preview"
              class="feed"
              :style="{ aspectRatio: `${preview.width}/${preview.height}` }"
            >
              <img
                :src="`data:image/jpeg;base64,${preview.jpeg}`"
                alt="设备实时检测画面"
                draggable="false"
              />
              <svg
                v-if="boxesVisible"
                class="detection-overlay"
                :viewBox="`0 0 ${preview.width} ${preview.height}`"
              >
                <g v-for="(box, i) in preview.detections ?? []" :key="i">
                  <rect
                    :x="box.x1"
                    :y="box.y1"
                    :width="box.x2 - box.x1"
                    :height="box.y2 - box.y1"
                    rx="3"
                  />
                  <rect
                    class="caption-bg"
                    :x="box.x1"
                    :y="Math.max(0, box.y1 - 21)"
                    :width="Math.min(160, preview.width - box.x1)"
                    height="20"
                    rx="3"
                  />
                  <text :x="box.x1 + 6" :y="Math.max(14, box.y1 - 7)">
                    {{ displayName(box.label) }} ·
                    {{ (box.confidence * 100).toFixed(0) }}%
                  </text>
                </g>
              </svg>
            </div>
            <div v-else class="video-placeholder">
              <div class="lens-orbit">
                <div><Icon name="camera" :size="38" /></div>
                <i></i>
              </div>
              <b>{{ online ? "正在建立实时视野" : "等待视频信号" }}</b>
              <p>
                {{
                  online
                    ? "保持设备在线，画面将在接收后自动显示"
                    : "连接边缘终端，开启视觉检测"
                }}
              </p>
            </div>
            <div class="frame-corners"></div>
            <div class="video-bottom">
              <span><i :class="{ lit: active }"></i>{{ activity.label }}</span
              ><span>{{
                preview
                  ? `FRAME ${String(preview.frameId).padStart(6, "0")}`
                  : "NO SIGNAL"
              }}</span>
            </div>
          </div>
          <div class="camera-footer">
            <span class="camera-icon"><Icon name="camera" :size="18" /></span>
            <div>
              <b>{{ product }}</b
              ><small>{{ state?.model?.version || "模型信息待上报" }}</small>
            </div>
            <div class="camera-source">
              <small>实时采集</small><b>OV5640 ↗</b>
            </div>
          </div>
        </section>
        <aside class="insight-column">
          <section class="soft-card verdict-card" :class="resultClass">
            <div class="card-heading">
              <div>
                <span class="section-number">02</span>
                <h2>单件结论</h2>
              </div>
              <span class="mini-label">最近完成</span>
            </div>
            <div class="verdict-main">
              <div class="verdict-symbol">
                <Icon
                  :name="
                    result?.result === 'PASS'
                      ? 'check'
                      : result?.result === 'FAIL'
                        ? 'close'
                        : 'scan'
                  "
                  :size="43"
                />
              </div>
              <div>
                <span class="verdict-kicker">{{
                  result ? "INSPECTION RESULT" : "READY TO INSPECT"
                }}</span
                ><Transition name="result" mode="out-in"
                  ><h3 :key="lastLabel">{{ lastLabel }}</h3></Transition
                >
              </div>
            </div>
            <p class="verdict-reason">
              {{ result?.reason || "产品经过视野后，自动完成判定与计件。" }}
            </p>
            <div v-if="level" class="level-reading">
              <span>当前画面 · 液位测量</span
              ><b
                >{{ level.row == null ? "未测到液面" : level.row.toFixed(1)
                }}<small v-if="level.row != null"> row</small></b
              >
              <div class="level-track">
                <span
                  :style="{
                    left: `${(level.band[0] / 223) * 100}%`,
                    width: `${((level.band[1] - level.band[0]) / 223) * 100}%`,
                  }"
                ></span
                ><i
                  v-if="level.row != null"
                  :style="{ left: `${(level.row / 223) * 100}%` }"
                ></i>
              </div>
              <small
                >{{ level.status }} · 合格带 {{ level.band[0] }}–{{
                  level.band[1]
                }}</small
              >
            </div>
            <div v-else class="verdict-foot">
              <i></i>多帧判定 · 自动留存检测结果
            </div>
          </section>
          <section class="soft-card compute-card">
            <div class="card-heading">
              <div>
                <span class="section-number">03</span>
                <h2>边缘计算</h2>
              </div>
              <span class="chip-label">ZYNQ-7020</span>
            </div>
            <div class="compute-body">
              <span class="processor-icon"
                ><Icon name="device" :size="37"
              /></span>
              <div class="fps-value">
                {{ fps == null ? "—" : fps.toFixed(1) }}<span>FPS</span
                ><small>实测推理帧率</small>
              </div>
              <svg
                class="spark"
                viewBox="0 0 240 55"
                aria-label="近期推理帧率趋势"
              >
                <path d="M0 48H240" />
                <polyline v-if="trend" :points="trend" />
              </svg>
            </div>
            <div class="compute-foot">
              <span>端侧推理延迟</span
              ><b
                >{{ latency == null ? "—" : latency.toFixed(1)
                }}<small> ms</small></b
              ><span class="accelerated">● PL 加速</span>
            </div>
          </section>
          <div class="control-deck">
            <select
              v-if="devices.devices.length > 1"
              v-model="devices.selected"
              aria-label="选择演示设备"
            >
              <option v-for="d in devices.devices" :key="d.id" :value="d.id">
                {{ d.name }}
              </option></select
            ><button
              class="start-button"
              :disabled="
                busy || !online || (!active && !!activity.startBlocked)
              "
              :title="activity.startBlocked"
              @click="control"
            >
              <span><Icon :name="active ? 'pause' : 'play'" :size="17" /></span
              >{{ busy ? "正在切换…" : active ? "停止检测" : "开始自动检测"
              }}<span class="button-arrow">{{ active ? "Ⅱ" : "↗" }}</span>
            </button>
            <p v-if="message" class="control-message" role="alert">
              {{ message }}
            </p>
            <RouterLink
              v-else-if="!state?.model || !state?.product"
              to="/workbench?setup=1"
              class="setup-link"
              >前往工作台配置产品与模型 →</RouterLink
            >
          </div>
        </aside>
      </div>
      <section class="metrics-row" aria-label="检测统计">
        <div class="metric">
          <span class="metric-icon"><Icon name="scan" :size="22" /></span>
          <div>
            <small>{{ state?.productionRunId ? "本批检测" : "设备累计" }}</small
            ><b
              >{{ total == null ? "—" : total.toLocaleString() }}<em>件</em></b
            >
          </div>
          <span class="metric-index">01</span>
        </div>
        <div class="metric">
          <span class="metric-icon green"
            ><Icon name="check" :size="22"
          /></span>
          <div>
            <small>合格产品</small
            ><b>{{ counts?.PASS?.toLocaleString() ?? "—" }}<em>件</em></b>
          </div>
          <span class="metric-index">02</span>
        </div>
        <div class="metric">
          <span class="metric-icon coral"
            ><Icon name="close" :size="22"
          /></span>
          <div>
            <small>不合格产品</small
            ><b>{{ counts?.FAIL?.toLocaleString() ?? "—" }}<em>件</em></b>
          </div>
          <span class="metric-index">03</span>
        </div>
        <div class="metric">
          <div class="rate-ring" :style="{ '--rate': `${passRate ?? 0}%` }">
            <Icon name="chart" :size="20" />
          </div>
          <div>
            <small>已判定合格率</small
            ><b>{{ passRate == null ? "—" : passRate.toFixed(1) }}<em>%</em></b>
          </div>
          <span class="metric-index">04</span>
        </div>
      </section>
      <div class="statistics-note">
        <span>{{
          online ? "设备原判 · 含待上传记录" : "上次上报的设备数据"
        }}</span
        ><span
          >判定不确定 {{ counts?.REVIEW ?? "—" }} · 检测错误
          {{ counts?.ERROR ?? "—" }} · 合格率仅统计已明确判定件</span
        >
      </div>
      <section class="technical-grid" aria-label="检测链路与技术指标">
        <article class="soft-card technical-card">
          <div class="card-heading">
            <div>
              <span class="section-number">04</span>
              <h2>推理流水线</h2>
            </div>
            <span class="mini-label">PS + PL 协同</span>
          </div>
          <div class="pipeline-nodes">
            <span><Icon name="camera" :size="16" />图像采集</span><i>→</i
            ><b><Icon name="device" :size="16" />FPGA 卷积</b><i>→</i
            ><span><Icon name="check" :size="16" />自动判定</span>
          </div>
          <div v-for="stage in stages" :key="stage.label" class="timing-row">
            <span>{{ stage.label }}</span>
            <div>
              <i
                :style="{
                  width:
                    stage.value == null
                      ? '0%'
                      : `${(stage.value / timingMax) * 100}%`,
                }"
              ></i>
            </div>
            <b
              >{{ stage.value == null ? "—" : stage.value.toFixed(2)
              }}<small> ms</small></b
            >
          </div>
          <p class="technical-note">
            采集推理 {{ timing?.captureMs?.toFixed(1) ?? "—" }} ms ·
            预处理与卷积并行，阶段耗时不可相加
          </p>
        </article>
        <article class="soft-card technical-card">
          <div class="card-heading">
            <div>
              <span class="section-number">05</span>
              <h2>识别与判定</h2>
            </div>
            <span class="mini-label">当前画面</span>
          </div>
          <div class="observation-values">
            <div>
              <b>{{ preview ? detections.length : "—" }}<em>个</em></b
              ><small>检测目标 · 不等于件数</small>
            </div>
            <div>
              <b
                >{{ confidence == null ? "—" : confidence.toFixed(1)
                }}<em>%</em></b
              ><small>最高置信度</small>
            </div>
            <div>
              <b
                >{{
                  state?.product
                    ? (state.product.acceptance.confidence * 100).toFixed(0)
                    : "—"
                }}<em>%</em></b
              ><small>判定阈值</small>
            </div>
          </div>
          <div class="rule-chips">
            <span v-for="rule in rules" :key="rule.classId"
              ><i :class="{ forbidden: rule.max === 0 }"></i
              >{{ displayName(rule.label)
              }}<b>{{
                rule.max === 0
                  ? "禁止出现"
                  : rule.min === rule.max
                    ? `${rule.min} 个`
                    : `${rule.min}–${rule.max} 个`
              }}</b></span
            ><span v-if="!rules.length">等待产品规则</span>
          </div>
          <p class="technical-note">
            {{
              level
                ? `液位合格带 ${level.band[0]}–${level.band[1]} row`
                : "按数量、区域与多帧证据自动判定"
            }}
            ·
            {{
              !state?.product
                ? "等待质量规则"
                : state.product.acceptance.qualityGate
                  ? "图像质量门控已开启"
                  : "图像质量门控未开启"
            }}
          </p>
        </article>
        <article class="soft-card technical-card">
          <div class="card-heading">
            <div>
              <span class="section-number">06</span>
              <h2>端侧运行状态</h2>
            </div>
            <span class="mini-label">{{ online ? "ONLINE" : "OFFLINE" }}</span>
          </div>
          <div class="runtime-values">
            <div>
              <span>CPU 使用率</span
              ><b>{{ state?.cpuPercent?.toFixed(0) ?? "—" }}<small>%</small></b>
              <div class="resource-track">
                <i
                  :style="{
                    width: `${Math.min(100, state?.cpuPercent ?? 0)}%`,
                  }"
                ></i>
              </div>
            </div>
            <div>
              <span>内存使用率</span
              ><b>{{ memory?.toFixed(0) ?? "—" }}<small>%</small></b>
              <div class="resource-track">
                <i :style="{ width: `${memory ?? 0}%` }"></i>
              </div>
            </div>
          </div>
          <div class="runtime-details">
            <span
              >当前模型<b :title="state?.model?.version">{{
                state?.model?.version || "未上报"
              }}</b></span
            ><span
              >运行时长<b>{{ uptime }}</b></span
            ><span
              >记录上传<b>{{
                state
                  ? state.pendingSync
                    ? `${state.pendingSync} 条待上传`
                    : "已同步"
                  : "—"
              }}</b></span
            >
          </div>
        </article>
      </section>
      <section class="bottom-row">
        <div class="recent-results">
          <span class="recent-title"
            >最近检测<small>RECENT RESULTS</small></span
          >
          <div class="result-pills">
            <RouterLink
              v-for="item in records"
              :key="item.id"
              class="result-pill"
              :class="item.result.toLowerCase()"
              :to="{ name: 'inspection', params: { id: item.id } }"
              ><Icon
                :name="
                  item.result === 'PASS'
                    ? 'check'
                    : item.result === 'FAIL'
                      ? 'close'
                      : 'scan'
                "
                :size="13"
              /><span>{{ chinese(item.result) }}</span
              ><small>{{
                new Date(item.createdAt).toLocaleTimeString("zh-CN", {
                  hour12: false,
                })
              }}</small></RouterLink
            ><span v-if="!records.length" class="empty-records"
              >检测记录将在完成后呈现</span
            >
          </div>
        </div>
        <div class="flow-signature">
          <span>感知</span><i></i><b>FPGA</b><i></i><span>判定</span><i></i
          ><span>记录</span>
        </div>
      </section>
      <footer class="show-footer">
        <span>VISION AT THE EDGE. <b>QUALITY IN EVERY DETAIL.</b></span
        ><span>嵌入式视觉检测系统 · LIVE DEMONSTRATION</span>
      </footer>
    </div>
  </div>
</template>

<style scoped>
@media (min-width: 1101px) and (min-height: 980px) {
  .showcase {
    height: 100dvh;
    display: flex;
    flex-direction: column;
  }
  .showcase .show-header {
    height: 85px;
    flex-shrink: 0;
    width: 100%;
  }
  .showcase .show-content {
    display: grid;
    grid-template-rows: auto minmax(min-content, 1fr) auto auto auto auto auto;
    flex: 1;
    min-height: 0;
    width: 100%;
  }
  .showcase .intro {
    padding: 24px 0;
  }
  .showcase .intro h1 {
    font-size: 36px;
  }
  .showcase .show-grid {
    min-height: 0;
  }
  .showcase .vision-card {
    display: flex;
    flex-direction: column;
  }
  .showcase .video-well {
    flex: 1;
    height: 0;
    min-height: 200px;
  }
  .showcase .camera-footer {
    flex-shrink: 0;
    padding-top: 16px;
    padding-bottom: 16px;
  }
  .showcase .verdict-card,
  .showcase .compute-card {
    padding: 20px 24px;
  }
  .showcase .verdict-main {
    margin: 20px 0 16px;
  }
  .showcase .verdict-symbol {
    width: 70px;
    height: 70px;
  }
  .showcase .verdict-reason {
    min-height: 0;
  }
  .showcase .verdict-foot {
    margin-top: 14px;
    padding-top: 12px;
  }
  .showcase .compute-body {
    margin: 20px 0;
  }
  .showcase .metrics-row {
    margin-top: 24px;
  }
  .showcase .metric {
    padding: 20px 24px;
  }
  .showcase .bottom-row {
    padding: 18px 0;
  }
}
.showcase {
  --paper: #e9eeed;
  --text: #293d3a;
  --sub: #7f918c;
  --mint: #3d927f;
  min-height: 100dvh;
  background:
    radial-gradient(ellipse at 90% 0, #f3f7ed70, transparent 45%), var(--paper);
  color: var(--text);
  font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
  padding: 0 4.2vw 20px;
  overflow: hidden;
  font-size: 14px;
  letter-spacing: 0.01em;
  color-scheme: light;
}
.showcase * {
  box-sizing: border-box;
}
.showcase h1,
.showcase h2,
.showcase h3,
.showcase p {
  margin: 0;
}
.showcase button,
.showcase select {
  font: inherit;
  cursor: pointer;
}
.showcase button {
  border: 0;
}
.showcase a {
  color: inherit;
  text-decoration: none;
}
.showcase button:focus-visible,
.showcase a:focus-visible,
.showcase select:focus-visible {
  outline: 2px solid var(--mint);
  outline-offset: 5px;
}
.show-header {
  height: 106px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #d7dfdc;
  box-shadow: 0 1px 0 #ffffffa0;
  gap: 20px;
}
.identity {
  display: flex;
  align-items: center;
  gap: 15px;
}
.brand-emblem,
.round-button {
  display: grid;
  place-items: center;
  background: var(--paper);
  box-shadow:
    5px 5px 12px #cbd5d2,
    -5px -5px 12px #fff;
  border: 1px solid #f8fffc90;
}
.brand-emblem {
  width: 56px;
  height: 56px;
  border-radius: 19px;
  color: var(--mint);
}
.wordmark {
  font-size: 26px;
  line-height: 1;
  font-weight: 750;
  letter-spacing: 0.12em;
}
.wordmark > span {
  color: var(--mint);
}
.wordmark small {
  display: block;
  font-size: 8px;
  letter-spacing: 0.3em;
  margin-top: 9px;
  font-weight: 500;
  color: var(--sub);
}
.show-tabs {
  display: flex;
  gap: 6px;
  padding: 7px;
  border-radius: 100px;
  box-shadow:
    inset 4px 4px 9px #cdd7d3,
    inset -4px -4px 9px #fbffff;
}
.show-tabs > span,
.show-tabs > a {
  padding: 11px 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--sub);
  font-size: 12px;
}
.show-tabs .selected {
  border-radius: 99px;
  background: var(--paper);
  box-shadow:
    3px 3px 8px #cad4d0,
    -3px -3px 8px #fff;
  color: var(--text);
  font-weight: 600;
}
.selected i,
.eyebrow i {
  width: 6px;
  height: 6px;
  background: var(--mint);
  border-radius: 50%;
}
.header-end {
  display: flex;
  gap: 16px;
  align-items: center;
}
.show-clock {
  font-size: 18px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.06em;
  text-align: right;
  margin-right: 6px;
}
.show-clock small {
  display: block;
  font-size: 10px;
  color: var(--sub);
  margin-top: 5px;
  letter-spacing: 0.12em;
}
.round-button {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  color: #72867e;
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}
.round-button:hover {
  transform: translateY(-2px);
}
.round-button:active {
  box-shadow:
    inset 3px 3px 7px #cbd5d2,
    inset -3px -3px 7px #fff;
}
.show-content,
.show-header {
  max-width: 1760px;
  margin: auto;
}
.intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 35px 0 29px;
  gap: 24px;
}
.eyebrow {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 9px;
  letter-spacing: 0.24em;
  color: var(--mint);
  font-weight: 600;
}
.intro h1 {
  font-size: clamp(27px, 2.4vw, 43px);
  font-weight: 600;
  letter-spacing: 0.035em;
  margin: 12px 0 11px;
  line-height: 1.3;
}
.intro h1 > span {
  font-weight: 400;
  color: #839c91;
}
.intro-copy {
  font-size: 12px;
  color: var(--sub);
  letter-spacing: 0.08em;
}
.connection {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 14px 18px;
  border: 1px solid #f8fffc7a;
  border-radius: 18px;
  box-shadow:
    inset 3px 3px 8px #d6dfdc,
    inset -3px -3px 8px #f8fffc;
  color: #78978a;
}
.connection b {
  font-size: 12px;
  font-weight: 500;
}
.connection small {
  font-size: 10px;
  display: block;
  color: var(--sub);
  margin-top: 5px;
}
.connection > i {
  width: 7px;
  height: 7px;
  background: #aeb9b4;
  border-radius: 50%;
  margin-left: 12px;
}
.connection > i.connected {
  background: #65aa8d;
  box-shadow: 0 0 0 4px #75ad8d14;
}
.show-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.95fr) minmax(310px, 1fr);
  gap: 28px;
}
.soft-card {
  background: var(--paper);
  border: 1px solid #f5fffc99;
  border-radius: 27px;
  box-shadow:
    12px 12px 27px #cad4d0,
    -12px -12px 27px #fafffd;
}
.vision-card {
  padding: 21px 22px 0;
  min-width: 0;
}
.card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.card-heading > div {
  display: flex;
  align-items: center;
  gap: 12px;
}
.section-number {
  font-size: 10px;
  color: #9aada4;
  letter-spacing: 0.1em;
}
.card-heading h2 {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.05em;
}
.english-label {
  font-size: 8px;
  letter-spacing: 0.17em;
  color: #9aa9a2;
}
.text-control {
  background: transparent;
  color: #7f968b;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px !important;
  padding: 5px !important;
}
.video-well {
  height: clamp(310px, 31vw, 490px);
  margin-top: 18px;
  position: relative;
  background:
    radial-gradient(ellipse at center, #30493d55, transparent 75%),
    linear-gradient(#ffffff03 1px, transparent 1px),
    linear-gradient(90deg, #ffffff03 1px, transparent 1px), #172b29;
  background-size:
    auto,
    38px 38px,
    38px 38px,
    auto;
  border-radius: 17px;
  overflow: hidden;
  box-shadow:
    inset 5px 5px 15px #0b1b1b,
    inset -2px -2px 8px #455d55,
    0 1px 0 #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #d7e8df;
}
.feed {
  height: 100%;
  max-width: 100%;
  position: relative;
}
.feed img {
  height: 100%;
  width: 100%;
  object-fit: contain;
  display: block;
}
.detection-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
.detection-overlay rect {
  fill: #72e1bd0a;
  stroke: #8ee8c6;
  stroke-width: 1.3;
}
.detection-overlay .caption-bg {
  fill: #6acbaa;
  stroke: none;
}
.detection-overlay text {
  font:
    9px "Microsoft YaHei",
    sans-serif;
  fill: #163b30;
  stroke: none;
}
.video-top,
.video-bottom {
  position: absolute;
  left: 22px;
  right: 22px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 2;
  pointer-events: none;
  font-size: 9px;
  letter-spacing: 0.08em;
  color: #a3b9ac;
}
.video-top {
  top: 19px;
}
.video-bottom {
  bottom: 18px;
}
.video-bottom > span:first-child {
  max-width: 75%;
  display: flex;
  gap: 7px;
  align-items: center;
  line-height: 1.5;
  letter-spacing: 0;
}
.video-bottom i {
  width: 5px;
  height: 5px;
  flex-shrink: 0;
  background: #7e8f86;
  border-radius: 50%;
}
.video-bottom i.lit {
  background: #99d9b5;
}
.live-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #243b35dd;
  border: 1px solid #b1d5c025;
  border-radius: 6px;
  padding: 6px 9px;
  font-size: 8px;
  letter-spacing: 0.14em;
}
.live-tag i {
  width: 4px;
  height: 4px;
  background: #8b9e92;
  border-radius: 50%;
}
.live-tag.streaming i {
  background: #92dcad;
  box-shadow: 0 0 8px #a8ffc977;
}
.frame-corners {
  position: absolute;
  inset: 59px 20px 49px;
  border: 1px solid #a6c1af1c;
  border-radius: 4px;
  pointer-events: none;
}
.video-placeholder {
  text-align: center;
  color: #b5c7bd;
}
.video-placeholder b {
  display: block;
  margin-top: 23px;
  font-size: 15px;
  letter-spacing: 0.12em;
  font-weight: 400;
}
.video-placeholder p {
  font-size: 10px;
  color: #7f9b8e;
  margin-top: 10px;
}
.lens-orbit {
  width: 126px;
  height: 126px;
  border: 1px solid #93b4a11b;
  border-radius: 50%;
  display: grid;
  place-items: center;
  margin: auto;
  position: relative;
}
.lens-orbit:after {
  content: "";
  position: absolute;
  inset: -17px;
  border: 1px dashed #93b4a111;
  border-radius: 50%;
}
.lens-orbit > div {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #8eb9a2;
  background: linear-gradient(145deg, #2d473e, #1a302b);
  box-shadow:
    8px 8px 20px #0e2424,
    -8px -8px 20px #2f4840,
    inset 1px 1px 1px #6e9b7b30;
}
.lens-orbit > i {
  position: absolute;
  top: 1px;
  left: 50%;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #8bb69c;
  box-shadow: 0 0 14px #9de2ad;
}
.camera-footer {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 20px 1px 22px;
}
.camera-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  box-shadow:
    inset 3px 3px 7px #d0d9d4,
    inset -3px -3px 7px #fafffc;
  color: #6c8d7c;
}
.camera-footer b {
  font-size: 12px;
  font-weight: 600;
}
.camera-footer small {
  font-size: 9px;
  display: block;
  color: var(--sub);
  margin-top: 6px;
}
.camera-source {
  margin-left: auto;
  text-align: right;
}
.camera-source small {
  margin: 0 0 6px;
}
.camera-source b {
  font-size: 10px;
  letter-spacing: 0.07em;
}
.insight-column {
  display: flex;
  flex-direction: column;
  gap: 23px;
  min-width: 0;
}
.verdict-card {
  padding: 23px 25px;
  flex: 1;
}
.mini-label {
  font-size: 9px;
  color: #94a69c;
}
.verdict-main {
  display: flex;
  align-items: center;
  gap: 23px;
  margin: 30px 0 22px;
}
.verdict-symbol {
  width: 87px;
  height: 87px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(145deg, #e5eeeb, #edf3ef);
  box-shadow:
    7px 7px 18px #c8d4cc,
    -7px -7px 18px #fcfffb,
    inset 0 0 0 6px #e9eeed;
  flex-shrink: 0;
  color: #80998c;
}
.pass .verdict-symbol {
  color: #5e9d78;
}
.fail .verdict-symbol {
  color: #bf806d;
}
.verdict-kicker {
  font-size: 8px;
  color: #95a79b;
  letter-spacing: 0.14em;
}
.verdict-main h3 {
  font-size: clamp(27px, 2.6vw, 40px);
  font-weight: 550;
  letter-spacing: 0.05em;
  margin-top: 10px;
  line-height: 1.2;
}
.pass h3 {
  color: #568e6f;
}
.fail h3 {
  color: #b97662;
}
.verdict-reason {
  font-size: 11px;
  line-height: 1.8;
  color: #81938a;
  min-height: 36px;
}
.verdict-foot {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #d4ded8;
  font-size: 10px;
  color: #92a398;
  display: flex;
  align-items: center;
  gap: 7px;
}
.verdict-foot i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #8ca496;
}
.level-reading {
  margin-top: 15px;
  padding-top: 14px;
  border-top: 1px solid #d4ded8;
  font-size: 10px;
  color: var(--sub);
}
.level-reading > b {
  float: right;
  font-size: 18px;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.level-reading small {
  font-size: 9px;
}
.level-track {
  height: 7px;
  position: relative;
  border-radius: 10px;
  box-shadow:
    inset 2px 2px 4px #c3cec8,
    inset -2px -2px 4px #fafffc;
  margin: 15px 0 10px;
}
.level-track span {
  position: absolute;
  top: 0;
  height: 100%;
  background: #8fbaa2;
  border-radius: 8px;
}
.level-track i {
  position: absolute;
  height: 13px;
  width: 3px;
  border-radius: 4px;
  top: -3px;
  background: #4d6d5a;
  box-shadow: 0 0 0 2px #e9eeed;
}
.compute-card {
  padding: 21px 25px;
}
.chip-label {
  font-size: 8px;
  letter-spacing: 0.09em;
  color: #8c9b93;
  border: 1px solid #d5dfd8;
  padding: 5px 7px;
  border-radius: 5px;
}
.compute-body {
  display: flex;
  gap: 21px;
  align-items: center;
  margin: 25px 0 21px;
  position: relative;
}
.processor-icon {
  width: 68px;
  height: 68px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: #7b9586;
  background: linear-gradient(145deg, #e1e9e4, #f2f6f0);
  box-shadow:
    5px 5px 12px #cbd5ce,
    -5px -5px 12px #fcfff9;
}
.fps-value {
  font-size: 39px;
  font-weight: 500;
  letter-spacing: -0.06em;
  font-variant-numeric: tabular-nums;
  position: relative;
  z-index: 1;
}
.fps-value > span {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: #879b8e;
  margin-left: 8px;
}
.fps-value small {
  font-size: 9px;
  letter-spacing: 0.06em;
  font-weight: 400;
  display: block;
  color: var(--sub);
  margin-top: 5px;
}
.spark {
  position: absolute;
  right: 0;
  width: 35%;
  height: 49px;
  opacity: 0.65;
  bottom: 4px;
}
.spark path {
  stroke: #d0ddd3;
  fill: none;
}
.spark polyline {
  stroke: #88ac95;
  stroke-width: 2;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.compute-foot {
  border-top: 1px solid #d4ded8;
  padding-top: 15px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 10px;
  color: #8a9b90;
}
.compute-foot > b {
  font-size: 14px;
  font-weight: 500;
  color: #546e5d;
  font-variant-numeric: tabular-nums;
}
.compute-foot small {
  font-size: 9px;
  color: #97a69d;
}
.accelerated {
  margin-left: auto;
  font-size: 9px;
}
.control-deck select {
  width: 100%;
  border: 1px solid #fafffca0;
  border-radius: 10px;
  background: var(--paper);
  color: var(--text);
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 11px;
}
.start-button {
  width: 100%;
  height: 56px;
  border-radius: 17px;
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 0 19px;
  background: linear-gradient(130deg, #62947e, #487760);
  color: #f1fbef;
  font-size: 13px !important;
  letter-spacing: 0.06em;
  box-shadow:
    6px 6px 15px #b7c7ba,
    -6px -6px 15px #fafff7,
    inset 1px 1px 0 #ffffff30;
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}
.start-button > span:first-child {
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  border-radius: 50%;
  background: #ffffff15;
}
.start-button:hover:not(:disabled) {
  transform: translateY(-2px);
}
.start-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.button-arrow {
  margin-left: auto;
  font-size: 20px;
  font-weight: 300;
}
.control-message {
  color: #ad6f5c;
  font-size: 11px;
  margin-top: 10px !important;
  line-height: 1.7;
}
.setup-link {
  display: block;
  text-align: center;
  font-size: 10px;
  color: #7b9586 !important;
  margin-top: 12px;
}
.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 25px;
  margin-top: 28px;
}
.metric {
  position: relative;
  display: flex;
  align-items: center;
  gap: 20px;
  border-radius: 20px;
  padding: 24px;
  background: var(--paper);
  box-shadow:
    7px 7px 18px #cdd7d1,
    -7px -7px 18px #fafffc;
  border: 1px solid #f7fffa80;
}
.metric-icon {
  width: 49px;
  height: 49px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  box-shadow:
    inset 4px 4px 8px #cdd7d0,
    inset -4px -4px 8px #fafffc;
  color: #82978b;
  flex-shrink: 0;
}
.metric-icon.green {
  color: #6f9c7f;
}
.metric-icon.coral {
  color: #b08f80;
}
.metric small {
  display: block;
  font-size: 10px;
  color: #899b90;
  margin-bottom: 8px;
}
.metric b {
  font-size: 30px;
  font-weight: 550;
  letter-spacing: -0.04em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.metric em {
  font-style: normal;
  font-size: 10px;
  letter-spacing: 0;
  color: #a0ada4;
  margin-left: 9px;
  font-weight: 400;
}
.metric-index {
  position: absolute;
  right: 17px;
  top: 15px;
  font-size: 8px;
  color: #a5b4a9;
}
.rate-ring {
  width: 49px;
  height: 49px;
  display: grid;
  place-items: center;
  background: conic-gradient(#85a98f var(--rate), #d7e1d8 0);
  border-radius: 50%;
  position: relative;
  flex-shrink: 0;
  box-shadow:
    3px 3px 8px #cbd6ce,
    -3px -3px 8px #fafff7;
  color: #7b9a83;
}
.rate-ring:before {
  content: "";
  position: absolute;
  inset: 4px;
  border-radius: 50%;
  background: var(--paper);
}
.rate-ring :deep(svg) {
  z-index: 1;
}
.statistics-note {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 3px 0;
  color: #8b9c91;
  font-size: 9px;
}
.bottom-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 23px 0 20px;
  border-bottom: 1px solid #d5dfd8;
  margin-top: 8px;
}
.recent-results {
  display: flex;
  align-items: center;
  gap: 25px;
  min-width: 0;
}
.recent-title {
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.recent-title small {
  display: block;
  font-size: 7px;
  letter-spacing: 0.12em;
  color: #9aa99f;
  margin-top: 7px;
  font-weight: 400;
}
.result-pills {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
}
.result-pill {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 10px;
  border-radius: 9px;
  box-shadow:
    inset 2px 2px 5px #d0dbd2,
    inset -2px -2px 5px #fafff9;
  font-size: 10px;
  color: #849b8a !important;
}
.result-pill.pass {
  color: #5f8e70 !important;
}
.result-pill.fail {
  color: #b27c66 !important;
}
.result-pill small {
  font-size: 8px;
  color: #97a99c;
  margin-left: 5px;
  font-variant-numeric: tabular-nums;
}
.empty-records {
  font-size: 10px;
  color: #94a69a;
}
.flow-signature {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
  font-size: 9px;
  color: #8d9f91;
}
.flow-signature b {
  font-size: 8px;
  padding: 7px 9px;
  border-radius: 7px;
  box-shadow:
    3px 3px 7px #cdd8cf,
    -3px -3px 7px #fafff6;
  letter-spacing: 0.08em;
  color: #6d8a73;
}
.flow-signature i {
  width: 18px;
  height: 1px;
  background: #bdcfc0;
}
.show-footer {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding-top: 17px;
  color: #a3b0a5;
  font-size: 8px;
  letter-spacing: 0.1em;
}
.show-footer b {
  font-weight: 400;
  color: #819785;
  margin-left: 5px;
}
.result-enter-active,
.result-leave-active {
  transition:
    opacity 0.2s,
    transform 0.2s;
}
.result-enter-from {
  opacity: 0;
  transform: translateY(7px);
}
.result-leave-to {
  opacity: 0;
  transform: translateY(-7px);
}
@media (max-width: 1100px) {
  .showcase {
    padding: 0 25px 20px;
  }
  .show-grid {
    gap: 20px;
    grid-template-columns: minmax(0, 1.5fr) minmax(290px, 1fr);
  }
  .english-label {
    display: none;
  }
  .verdict-card,
  .compute-card {
    padding: 20px;
  }
  .verdict-main {
    gap: 15px;
    margin: 24px 0 16px;
  }
  .verdict-symbol {
    width: 65px;
    height: 65px;
  }
  .verdict-main h3 {
    font-size: 28px;
  }
  .metrics-row {
    gap: 17px;
  }
  .metric {
    gap: 12px;
    padding: 20px 16px;
  }
  .metric b {
    font-size: 26px;
  }
  .metric-icon,
  .rate-ring {
    width: 40px;
    height: 40px;
  }
  .flow-signature {
    display: none;
  }
  .show-tabs > span,
  .show-tabs > a {
    padding: 10px 16px;
  }
  .show-header {
    height: 92px;
  }
}
@media (max-width: 800px) {
  .show-grid {
    grid-template-columns: 1fr;
  }
  .insight-column {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
  }
  .control-deck {
    grid-column: 1/-1;
  }
  .video-well {
    height: 420px;
  }
  .metrics-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .show-tabs,
  .connection {
    display: none;
  }
  .intro {
    padding: 26px 0;
  }
  .statistics-note {
    flex-direction: column;
    gap: 6px;
  }
  .show-footer {
    font-size: 7px;
    flex-wrap: wrap;
  }
  .verdict-main h3 {
    font-size: 26px;
  }
  .verdict-symbol {
    width: 60px;
    height: 60px;
  }
  .show-clock {
    font-size: 14px;
  }
  .round-button {
    height: 35px;
    width: 35px;
  }
  .header-end {
    gap: 11px;
  }
}
@media (max-width: 500px) {
  .showcase {
    padding: 0 18px 18px;
  }
  .show-header {
    height: 83px;
  }
  .brand-emblem {
    height: 43px;
    width: 43px;
    border-radius: 14px;
  }
  .wordmark {
    font-size: 20px;
  }
  .wordmark small {
    font-size: 6px;
  }
  .header-end > a {
    display: none;
  }
  .identity {
    gap: 10px;
  }
  .show-clock {
    font-size: 12px;
  }
  .show-clock small {
    font-size: 8px;
  }
  .intro h1 {
    font-size: 27px;
  }
  .intro-copy {
    font-size: 10px;
  }
  .vision-card {
    padding: 16px 14px 0;
  }
  .video-well {
    height: 340px;
  }
  .insight-column {
    grid-template-columns: 1fr;
  }
  .control-deck {
    grid-column: auto;
  }
  .metric {
    padding: 18px 14px;
  }
  .metric b {
    font-size: 25px;
  }
  .metric-icon,
  .rate-ring {
    width: 35px;
    height: 35px;
  }
  .metric small {
    font-size: 9px;
  }
  .recent-results {
    gap: 15px;
    align-items: flex-start;
  }
  .result-pill small {
    display: none;
  }
  .show-footer {
    line-height: 1.8;
  }
  .show-footer > span:last-child {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .showcase * {
    transition: none !important;
    animation: none !important;
  }
}

.technical-grid {
  display: grid;
  grid-template-columns: 1.05fr 1.15fr 1fr;
  gap: 23px;
  margin-top: 23px;
}
.technical-card {
  padding: 19px 22px;
  border-radius: 21px;
  min-width: 0;
}
.pipeline-nodes {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 18px 0;
  color: #81958b;
  font-size: 10px;
}
.pipeline-nodes > span,
.pipeline-nodes > b {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.pipeline-nodes > b {
  font-weight: 500;
  color: #5d8a73;
  padding: 8px 10px;
  border-radius: 10px;
  box-shadow:
    inset 3px 3px 7px #cbd6ce,
    inset -3px -3px 7px #fafff9;
}
.pipeline-nodes > i {
  font-style: normal;
  color: #a4b5a8;
}
.timing-row {
  display: grid;
  grid-template-columns: 64px 1fr 72px;
  gap: 12px;
  align-items: center;
  font-size: 10px;
  margin-top: 10px;
  color: #81968a;
}
.timing-row > div,
.resource-track {
  height: 5px;
  border-radius: 8px;
  box-shadow:
    inset 2px 2px 4px #c5d2c9,
    inset -2px -2px 4px #fafffa;
  overflow: hidden;
}
.timing-row i,
.resource-track i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #a2bfa9, #749b80);
  border-radius: 8px;
  transition: width 0.5s;
}
.timing-row b {
  text-align: right;
  font-size: 11px;
  font-weight: 500;
  color: #5f7868;
  font-variant-numeric: tabular-nums;
}
.timing-row small {
  font-size: 8px;
  font-weight: 400;
  color: #96a59b;
}
.technical-note {
  font-size: 9px;
  color: #8a9f91;
  line-height: 1.6;
  margin-top: 14px !important;
}
.observation-values {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  padding: 21px 0 16px;
}
.observation-values > div + div {
  border-left: 1px solid #d1ddd4;
  padding-left: 15px;
}
.observation-values b {
  font-size: 24px;
  letter-spacing: -0.04em;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.observation-values em {
  font-style: normal;
  font-size: 9px;
  color: #94a99a;
  margin-left: 5px;
}
.observation-values small {
  display: block;
  color: #8b9f90;
  font-size: 9px;
  margin-top: 7px;
}
.rule-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.rule-chips > span {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 9px;
  color: #809688;
  border: 1px solid #d3dfd6;
  border-radius: 6px;
  padding: 5px 7px;
}
.rule-chips i {
  height: 4px;
  width: 4px;
  flex-shrink: 0;
  background: #7ea68b;
  border-radius: 50%;
}
.rule-chips i.forbidden {
  background: #bc9a89;
}
.rule-chips b {
  font-weight: 400;
  color: #5e7a66;
}
.runtime-values {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 25px;
  margin: 21px 0 17px;
}
.runtime-values > div > span {
  font-size: 9px;
  color: #8c9e90;
  display: block;
  margin-bottom: 9px;
}
.runtime-values b {
  font-weight: 500;
  font-size: 26px;
  font-variant-numeric: tabular-nums;
}
.runtime-values small {
  font-size: 10px;
  margin-left: 5px;
  color: #9aaa9d;
}
.resource-track {
  margin-top: 9px;
}
.runtime-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 9px;
  color: #8b9d8f;
}
.runtime-details > span {
  display: flex;
  justify-content: space-between;
  gap: 15px;
}
.runtime-details b {
  font-size: 10px;
  font-weight: 400;
  color: #6d8773;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 70%;
}
@media (min-width: 1101px) and (min-height: 980px) {
  .showcase .show-header {
    height: 74px;
  }
  .showcase .intro {
    padding: 18px 0;
  }
  .showcase .intro h1 {
    font-size: 30px;
    margin: 8px 0;
  }
  .showcase .intro-copy {
    font-size: 11px;
  }
  .showcase .insight-column {
    gap: 15px;
  }
  .showcase .verdict-card,
  .showcase .compute-card {
    padding: 15px 22px;
  }
  .showcase .verdict-main {
    margin: 15px 0 12px;
    gap: 17px;
  }
  .showcase .verdict-symbol {
    width: 54px;
    height: 54px;
  }
  .showcase .verdict-main h3 {
    font-size: 29px;
  }
  .showcase .verdict-symbol :deep(svg) {
    width: 30px;
    height: 30px;
  }
  .showcase .verdict-foot {
    margin-top: 11px;
    padding-top: 11px;
  }
  .showcase .compute-body {
    margin: 14px 0;
  }
  .showcase .processor-icon {
    height: 48px;
    width: 48px;
    border-radius: 14px;
  }
  .showcase .fps-value {
    font-size: 31px;
  }
  .showcase .compute-foot {
    padding-top: 11px;
  }
  .showcase .start-button {
    height: 47px;
  }
  .showcase .metric {
    padding: 16px 22px;
  }
  .showcase .metrics-row {
    margin-top: 20px;
  }
  .showcase .technical-grid {
    margin-top: 18px;
  }
  .showcase .technical-card {
    padding: 16px 20px;
  }
  .showcase .bottom-row {
    padding: 13px 0;
  }
  .showcase .show-footer {
    padding-top: 12px;
  }
  .showcase .technical-note {
    font-size: 8px;
  }
}
@media (max-width: 1100px) {
  .technical-grid {
    grid-template-columns: 1fr 1fr;
  }
  .technical-card:last-child {
    grid-column: 1/-1;
  }
  .runtime-values {
    margin: 16px 0;
  }
  .runtime-details {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 22px;
  }
  .runtime-details > span {
    gap: 10px;
  }
  .runtime-details b {
    max-width: none;
  }
}
@media (max-width: 700px) {
  .technical-grid {
    grid-template-columns: 1fr;
  }
  .technical-card:last-child {
    grid-column: auto;
  }
  .runtime-details {
    flex-direction: column;
    gap: 10px;
  }
}

@media (min-width: 1101px) and (min-height: 980px) {
  .showcase {
    overflow: auto;
  }
  .showcase .show-header {
    height: 64px;
  }
  .showcase .intro {
    padding: 12px 0;
  }
  .showcase .intro h1 {
    font-size: 28px;
    margin: 6px 0;
  }
  .showcase .intro-copy {
    display: none;
  }
  .showcase .technical-card {
    padding: 13px 20px;
  }
  .showcase .pipeline-nodes {
    margin: 14px 0;
  }
  .showcase .technical-note {
    margin-top: 10px !important;
  }
  .showcase .bottom-row {
    padding: 9px 0;
  }
}
</style>
