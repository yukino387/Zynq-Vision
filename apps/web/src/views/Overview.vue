<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { chinese, displayName, fieldLabel } from "@vision/shared";
import { api } from "../api";
import { useDeviceStore } from "../stores/devices";
import AsyncState from "../components/AsyncState.vue";
import Status from "../components/Status.vue";
import ImageViewer from "../components/ImageViewer.vue";
import Sparkline from "../components/Sparkline.vue";
import DistributionBar from "../components/DistributionBar.vue";
import type { RouteLocationRaw } from "vue-router";

interface Overview {
  trainingReadiness: {
    realSamples: number;
    annotatedReal: number;
    simulatedSamples: number;
    readyDatasets: {
      id: string;
      name: string;
      version: number;
      count: number;
    }[];
    candidateModels: number;
    approvedModels: number;
    activeDeployments: number;
  } | null;
  window: { from: string; to: string };
  inspections: {
    total: number;
    pass: number;
    fail: number;
    review: number;
    error: number;
  };
  samples: { pending: number; reviewed: number };
  devices: {
    total: number;
    online: number;
    stale: number;
    offline: number;
    fault: number;
  };
  through: {
    fps?: number;
    inferenceUs?: number;
    cycleUs?: number;
    frameId?: number;
    errorCode?: number;
  } | null;
  pipeline: {
    pendingReview: number;
    reviewSamples: number;
    pendingDeployments: number;
  } | null;
  /** 数据闭环的每一环：已完成的量与还在等人工的量。对操作工为 null。 */
  loop:
    | {
        key: string;
        label: string;
        done: number;
        waiting: number;
        to: string;
      }[]
    | null;
  firmwareGaps: { unsupported: string[] } | null;
}

const devices = useDeviceStore(),
  data = ref<Overview | null>(null),
  loading = ref(false),
  error = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    data.value = await api<Overview>("/overview");
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
/** 检测完成或设备状态变化时刷新计数，不轮询。 */
watch(
  () => devices.recent[0],
  (event) => {
    if (
      event &&
      /inspection\.completed|status\.changed|device\.error|job\./.test(
        event.type,
      )
    )
      void load();
  },
);

const current = computed(() => devices.current);
const ready = computed(() => data.value?.trainingReadiness);
const next = computed<{
  title: string;
  body: string;
  label: string;
  to: RouteLocationRaw;
}>(() => {
  const r = ready.value;
  if (r?.approvedModels && !r.activeDeployments)
    return {
      title: "模型已评估通过，可以部署到设备",
      body: "选择模型和目标设备，部署后查看实际检测结果。",
      label: "去部署模型",
      to: "/models/deployments",
    };
  if (r?.candidateModels)
    return {
      title: "新模型已生成，下一步验证效果",
      body: "先评估模型，再决定是否发布到板卡。",
      label: "去评估模型",
      to: "/models/benchmarks",
    };
  if (r?.readyDatasets.length)
    return {
      title: "数据已准备好，可以开始训练",
      body: `已有 ${r.readyDatasets.length} 个真实数据集可以使用。选择灰度或彩色输入，即可发起 GPU 训练。`,
      label: "开始训练",
      to: {
        name: "models",
        params: { tab: "training" },
        query: { datasetId: r.readyDatasets[0]!.id, create: "1" },
      },
    };
  if (r && r.annotatedReal >= 2)
    return {
      title: "把已标注的样本整理成训练数据集",
      body: `已有 ${r.annotatedReal} 张真实样本完成标注。选入数据集并锁定版本后，就能开始训练。`,
      label: "整理数据集",
      to: "/data/samples?annotation=complete",
    };
  if (r?.realSamples)
    return {
      title: "先把已有图片标注好",
      body: `已有 ${r.realSamples} 张真实样本，其中 ${r.annotatedReal} 张已标注。框出缺陷并选择类别，让图片成为可训练的数据。`,
      label: `继续标注 ${r.realSamples - r.annotatedReal} 张`,
      to: "/data/annotation?annotation=pending",
    };
  return {
    title: "从采集第一张样本开始",
    body: "用板卡摄像头采集，或直接导入已有图片；完成标注后训练自己的缺陷检测模型。",
    label: "去采集样本",
    to: "/workbench",
  };
});
const steps = computed(() => [
  {
    title: "采集样本",
    body: "从摄像头采集，或导入图片",
    to: "/data/samples",
    done: (ready.value?.realSamples ?? 0) > 0,
  },
  {
    title: "框选缺陷",
    body: "标出位置，选择缺陷类别",
    to: "/data/annotation",
    done: (ready.value?.annotatedReal ?? 0) >= 2,
  },
  {
    title: "整理数据集",
    body: "选择已标注样本，锁定版本",
    to: "/data/datasets",
    done: !!ready.value?.readyDatasets.length,
  },
  {
    title: "训练模型",
    body: "选择输入模式，使用 GPU 训练",
    to: "/models/training",
    done: !!(ready.value?.candidateModels || ready.value?.approvedModels),
  },
  {
    title: "上板验证",
    body: "评估并部署，查看真实效果",
    to: "/models/deployments",
    done: (ready.value?.activeDeployments ?? 0) > 0,
  },
]);
const ms = (us: number | undefined) =>
  us === undefined ? null : `${(us / 1000).toFixed(1)} ms`;
/** 窗口默认是滚动的 24 小时，起止同刻，所以只报截止时间。 */
const windowLabel = computed(() => {
  if (!data.value) return "";
  const hours = Math.round(
    (new Date(data.value.window.to).getTime() -
      new Date(data.value.window.from).getTime()) /
      3600_000,
  );
  const at = new Date(data.value.window.to);
  const hhmm = `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
  return `近 ${hours} 小时 · 截至 ${hhmm}`;
});
const gaps = computed(() =>
  Object.entries(current.value?.capabilities ?? {})
    .filter(([, supported]) => supported === false)
    .map(([key]) => key),
);
/** 本班次结果分布。合格给安静色：它是预期状态，不该在饼图里抢眼。 */
const resultSlices = computed(() => [
  {
    label: "合格",
    value: data.value?.inspections.pass ?? 0,
    tone: "quiet" as const,
  },
  {
    label: "不通过",
    value: data.value?.inspections.fail ?? 0,
    tone: "crit" as const,
  },
  {
    label: "待复核",
    value: data.value?.inspections.review ?? 0,
    tone: "warn" as const,
  },
  {
    label: "异常",
    value: data.value?.inspections.error ?? 0,
    tone: "info" as const,
  },
]);
/** 遥测不落库，趋势是客户端从 WS 攒的最近若干帧。 */
const latency = computed(() =>
  devices.history.map((h) =>
    h.inferenceUs === null ? null : h.inferenceUs / 1000,
  ),
);
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>项目工作台</h1>
      <p>从几张样本开始，训练并验证你的缺陷检测模型。</p>
    </div>
    <div class="heading-actions">
      <RouterLink class="button-link primary" :to="{ name: 'workbench' }"
        >打开摄像头与检测</RouterLink
      >
      <button :class="{ busy: loading }" :disabled="loading" @click="load">
        刷新
      </button>
    </div>
  </div>

  <AsyncState :loading="loading" :error="error" @retry="load">
    <template v-if="data">
      <section v-if="ready" class="project-hero">
        <div>
          <span class="project-eyebrow">下一步</span>
          <h2>{{ next.title }}</h2>
          <p>{{ next.body }}</p>
          <RouterLink class="button-link primary" :to="next.to"
            >{{ next.label }} <span aria-hidden="true">→</span></RouterLink
          >
        </div>
        <div class="project-hero-aside">
          <span>真实样本标注进度</span
          ><strong
            >{{ ready.annotatedReal
            }}<small> / {{ ready.realSamples }} 张</small></strong
          >
          <div class="project-progress">
            <span
              :style="{
                width: `${ready.realSamples ? (ready.annotatedReal / ready.realSamples) * 100 : 0}%`,
              }"
            />
          </div>
          <small>审核图片与完成标注分别记录；训练使用已完成的标注。</small>
        </div>
      </section>
      <div v-if="ready" class="project-stats">
        <RouterLink to="/data/samples"
          ><small>真实样本</small
          ><strong>{{ ready.realSamples }}<span>张</span></strong
          ><span>板卡、手机与导入图片 →</span></RouterLink
        >
        <RouterLink to="/data/annotation?annotation=complete"
          ><small>已完成标注</small
          ><strong>{{ ready.annotatedReal }}<span>张</span></strong
          ><span
            >{{ ready.realSamples - ready.annotatedReal }} 张待标注 →</span
          ></RouterLink
        >
        <RouterLink to="/data/datasets"
          ><small>可训练的真实数据集</small
          ><strong>{{ ready.readyDatasets.length }}<span>个</span></strong
          ><span>至少 2 张已标注样本，已锁定版本 →</span></RouterLink
        >
        <RouterLink to="/models/registry"
          ><small>真实模型</small
          ><strong
            >{{ ready.candidateModels + ready.approvedModels
            }}<span>个</span></strong
          ><span
            >{{ ready.candidateModels }} 个待评估 ·
            {{ ready.activeDeployments }} 个部署中 →</span
          ></RouterLink
        >
      </div>
      <p v-if="ready?.simulatedSamples" class="project-demo-note">
        另有
        {{ ready.simulatedSamples }}
        张模拟样本，仅用于演示和流程验证。<RouterLink
          to="/data/samples?source=SIMULATION"
          >查看模拟样本</RouterLink
        >
      </p>
      <section class="project-workflow" aria-label="建模流程">
        <RouterLink
          v-for="(step, i) in steps"
          :key="step.title"
          :to="step.to"
          :class="{ done: step.done }"
          ><span class="project-step-number">{{
            step.done ? "✓" : i + 1
          }}</span>
          <div>
            <b>{{ step.title }}</b
            ><small>{{ step.body }}</small>
          </div>
          <span aria-hidden="true">→</span></RouterLink
        >
      </section>
      <details class="project-diagnostics">
        <summary>
          检测统计与设备详情 <span>{{ windowLabel }}</span>
        </summary>
        <!-- 要人处理的事情排在最前，而不是埋在表格里 -->
        <div v-if="data.pipeline?.pendingReview" class="banner warn">
          <b>{{ data.pipeline?.pendingReview }} 件待复核</b>
          <span>确认检测结果后完成归档</span>
          <RouterLink
            class="right"
            :to="{ name: 'records', params: { tab: 'queue' } }"
            >去处理</RouterLink
          >
        </div>

        <section class="control-room">
          <div class="control-room-camera">
            <div class="canvas-title">
              <span
                >当前设备 / {{ displayName(current?.name ?? "未选择") }}</span
              ><Status :value="current?.connectionState" />
            </div>
            <ImageViewer
              compact
              :jpeg="
                current?.connectionState === 'ONLINE'
                  ? devices.previews[current.id]?.jpeg
                  : undefined
              "
              :boxes="
                current?.connectionState === 'ONLINE'
                  ? devices.previews[current.id]?.detections
                  : undefined
              "
            /><RouterLink to="/workbench" class="control-room-enter"
              >打开检测工作台 →</RouterLink
            >
          </div>
          <div class="control-room-readouts">
            <div class="panel-head">
              <h3>窗口内检测</h3>
              <Status :value="devices.connected ? 'ONLINE' : 'CONNECTING'" />
            </div>
            <div class="cells">
              <div>
                <small>已检</small><strong>{{ data.inspections.total }}</strong>
              </div>
              <div>
                <small>合格</small
                ><strong class="tone-quiet">{{ data.inspections.pass }}</strong>
              </div>
              <div>
                <small>不通过</small
                ><strong class="tone-crit">{{ data.inspections.fail }}</strong>
              </div>
              <div>
                <small>待复核</small
                ><strong class="tone-warn">{{
                  data.inspections.review
                }}</strong>
              </div>
              <div>
                <small>节拍</small>
                <strong class="mono"
                  >{{
                    current?.telemetry?.fps
                      ? current?.telemetry?.fps.toFixed(2)
                      : "—"
                  }}<small v-if="current?.telemetry?.fps" class="unit"
                    >fps</small
                  ></strong
                >
              </div>
            </div>
          </div>
        </section>

        <!-- 数据闭环：每一步都点得进去，卡在哪一环一眼看得出 -->
        <div v-if="data.loop" class="panel section-space">
          <div class="panel-head">
            <h3>数据闭环 · 当前存量</h3>
            <span class="tag">累计口径 · 点任一步进入</span>
          </div>
          <div class="loop">
            <RouterLink
              v-for="(s, stepIndex) in data.loop"
              :key="s.key"
              class="stage"
              :class="{ waiting: s.waiting > 0 }"
              :to="'/' + s.to"
            >
              <small class="stage-index mono">{{
                String(stepIndex + 1).padStart(2, "0")
              }}</small
              ><span class="label">{{ s.label }}</span>
              <span class="done mono">{{ s.done }}</span>
              <span v-if="s.waiting" class="wait mono"
                >{{ s.waiting }} 待处理</span
              >
              <span v-else class="idle">—</span>
            </RouterLink>
          </div>
        </div>

        <div class="two-columns section-space">
          <div class="panel">
            <div class="panel-head">
              <h3>窗口内结果分布</h3>
              <span class="mono" style="font-size: 11px; color: var(--muted)"
                >共 {{ data.inspections.total }} 件</span
              >
            </div>
            <div class="panel-body">
              <DistributionBar :slices="resultSlices" unit=" 件" />
            </div>
          </div>
          <div class="panel">
            <div class="panel-head">
              <h3>推理耗时趋势</h3>
              <span class="tag">最近 {{ latency.length }} 帧</span>
            </div>
            <div class="panel-body">
              <Sparkline :values="latency" label="单帧推理" unit=" ms" />
            </div>
          </div>
        </div>

        <div class="two-columns section-space">
          <div class="panel">
            <div class="panel-head"><h3>设备</h3></div>
            <div class="panel-body">
              <div class="list-line" style="padding-top: 0">
                <div>
                  <b>{{ displayName(current?.name ?? "（无设备）") }}</b>
                  <small class="mono">{{ current?.id?.slice(-10) }}</small>
                </div>
                <Status :value="current?.connectionState" />
              </div>
              <dl class="key-values">
                <dt>运行状态</dt>
                <dd>{{ chinese(current?.runtimeState) }}</dd>
                <dt>模型版本</dt>
                <dd>{{ current?.reportedState?.modelVersion ?? "未上报" }}</dd>
                <dt>方案版本</dt>
                <dd>{{ current?.reportedState?.planVersion ?? "未上报" }}</dd>
                <dt>版本同步</dt>
                <dd><Status :value="current?.syncState" /></dd>
                <dt>推理耗时</dt>
                <dd class="mono">
                  {{ ms(current?.telemetry?.inferenceUs) ?? "未上报" }}
                </dd>
                <dt>帧周期</dt>
                <dd class="mono">
                  {{ ms(current?.telemetry?.cycleUs) ?? "未上报" }}
                </dd>
                <dt>错误码</dt>
                <dd class="mono">
                  {{ current?.telemetry?.errorCode ?? "未上报" }}
                </dd>
                <dt>固件版本</dt>
                <dd class="muted">未上报</dd>
              </dl>
            </div>
          </div>

          <div>
            <div class="panel">
              <div class="panel-head">
                <h3>待处理事项</h3>
                <span class="tag">待处理在前</span>
              </div>
              <div class="panel-body">
                <dl class="key-values">
                  <dt>待复核判定</dt>
                  <dd class="tone-warn">
                    {{ data.pipeline?.pendingReview ?? 0 }}
                  </dd>
                  <template v-if="data.pipeline">
                    <dt>待审核样本</dt>
                    <dd class="tone-warn">{{ data.pipeline.reviewSamples }}</dd>
                    <dt>待批准部署</dt>
                    <dd class="tone-warn">
                      {{ data.pipeline.pendingDeployments }}
                    </dd>
                  </template>
                  <dt>离线设备</dt>
                  <dd :class="data.devices.offline ? 'tone-crit' : 'muted'">
                    {{ data.devices.offline }}
                  </dd>
                </dl>
              </div>
            </div>

            <div class="panel section-space">
              <div class="panel-head">
                <h3>当前设备未支持</h3>
                <span v-if="gaps.length" class="tag crit"
                  >{{ gaps.length }} 项</span
                >
              </div>
              <div class="panel-body">
                <p v-if="!gaps.length" class="muted">没有记录到缺失能力。</p>
                <ul v-else class="gap-list">
                  <li v-for="g in gaps" :key="g" class="mono">
                    {{ g === "modelVersion" ? "模型版本上报" : fieldLabel(g) }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </details>
    </template>
  </AsyncState>
</template>
<style scoped>
.project-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 250px;
  gap: 40px;
  align-items: center;
  padding: 32px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-left: 4px solid var(--forest);
}
.project-eyebrow {
  font-size: 12px;
  color: var(--forest);
  font-weight: 600;
  letter-spacing: 0.08em;
}
.project-hero h2 {
  font-size: clamp(22px, 2vw, 30px);
  line-height: 1.4;
  margin: 12px 0;
}
.project-hero p {
  color: var(--muted);
  max-width: 620px;
  line-height: 1.8;
  margin: 0 0 22px;
}
.project-hero-aside {
  border-left: 1px solid var(--line);
  padding-left: 28px;
  display: grid;
  gap: 12px;
  color: var(--muted);
  font-size: 12px;
}
.project-hero-aside strong {
  font-size: 40px;
  color: var(--ink);
  font-weight: 600;
  line-height: 1.1;
}
.project-hero-aside strong small {
  font-size: 14px;
  font-weight: 400;
  color: var(--muted);
}
.project-hero-aside > small {
  line-height: 1.7;
}
.project-progress {
  height: 6px;
  background: var(--surface-3);
  border-radius: 3px;
  overflow: hidden;
}
.project-progress span {
  display: block;
  height: 100%;
  background: var(--forest);
}
.project-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}
.project-stats > a {
  padding: 21px;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink);
  display: grid;
  gap: 12px;
  text-decoration: none;
}
.project-stats > a:hover {
  border-color: var(--forest);
}
.project-stats small {
  font-size: 12px;
  color: var(--muted);
}
.project-stats strong {
  font-size: 32px;
  font-weight: 600;
  line-height: 1.1;
}
.project-stats strong span {
  font-size: 12px;
  margin-left: 8px;
  color: var(--muted);
  font-weight: 400;
}
.project-stats a > span {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.5;
}
.project-demo-note {
  font-size: 12px;
  color: var(--muted);
  margin: 14px 0 22px;
}
.project-demo-note a {
  margin-left: 10px;
}
.project-workflow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 24px 0;
  background: var(--surface);
  border: 1px solid var(--line);
}
.project-workflow a {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 14px;
  text-decoration: none;
  color: var(--ink);
  border-right: 1px solid var(--line);
}
.project-workflow a:last-child {
  border: 0;
}
.project-workflow a:hover {
  background: var(--surface-2);
}
.project-step-number {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  font-size: 12px;
  color: var(--muted);
}
.done .project-step-number {
  background: var(--forest);
  border-color: var(--forest);
  color: white;
}
.project-workflow b {
  font-size: 13px;
  display: block;
  white-space: nowrap;
}
.project-workflow small {
  font-size: 11px;
  color: var(--muted);
  display: block;
  line-height: 1.6;
  margin-top: 6px;
}
.project-workflow a > span:last-child {
  margin-left: auto;
  color: var(--muted);
}
.project-diagnostics {
  margin-top: 26px;
  border-top: 1px solid var(--line);
  padding-top: 18px;
}
.project-diagnostics > summary {
  cursor: pointer;
  font-size: 14px;
  padding-bottom: 18px;
}
.project-diagnostics > summary > span {
  font-size: 11px;
  color: var(--muted);
  margin-left: 14px;
}
@media (max-width: 1200px) {
  .project-workflow {
    grid-template-columns: repeat(3, 1fr);
  }
  .project-workflow a {
    border-bottom: 1px solid var(--line);
  }
  .project-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .project-hero {
    grid-template-columns: 1fr;
    padding: 22px;
    gap: 22px;
  }
  .project-hero-aside {
    border-left: 0;
    border-top: 1px solid var(--line);
    padding: 20px 0 0;
  }
  .project-stats {
    gap: 10px;
  }
  .project-stats > a {
    padding: 16px;
  }
  .project-workflow {
    grid-template-columns: 1fr;
  }
  .project-workflow a {
    border-right: 0;
  }
  .project-demo-note {
    line-height: 1.8;
  }
}
</style>
