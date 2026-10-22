<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { displayName } from "@vision/shared";
import type { InspectionPlan } from "@vision/contracts";
import { api } from "../api";
import { useAuthStore } from "../stores/auth";
import { useDeviceStore } from "../stores/devices";
import AsyncState from "../components/AsyncState.vue";
import Icon from "../components/Icon.vue";
import { UiButton, UiCard, UiBadge, UiStat } from "../components/ui";

const auth = useAuthStore(),
  devices = useDeviceStore();
interface Overview {
  samples: { pending: number };
  pipeline: { pendingReview: number } | null;
  trainingReadiness: {
    realSamples: number;
    annotatedReal: number;
    simulatedSamples: number;
    readyDatasets: { id: string }[];
    candidateModels: number;
    activeDeployments: number;
  } | null;
}
const data = ref<Overview | null>(null),
  plans = ref<InspectionPlan[]>([]),
  pendingReal = ref(0),
  loading = ref(false),
  error = ref("");
const ready = computed(() => data.value?.trainingReadiness);
async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [overview, result, pending] = await Promise.all([
      api<Overview>("/overview"),
      api<{ items: InspectionPlan[] }>("/plans?pageSize=100"),
      api<{ total: number }>(
        "/samples?realOnly=true&reviewed=false&pageSize=1",
      ),
    ]);
    data.value = overview;
    pendingReal.value = pending.total;
    plans.value = result.items.filter((p) => Array.isArray(p.rules.classes));
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
const next = computed(() => {
  if (!plans.value.length)
    return {
      title: "先配置要检测的产品",
      body: "设置识别对象和合格数量，保存后即可准备检测。",
      label: auth.admin ? "新建产品" : "查看产品配置",
      to: auth.admin ? "/plans?create=1" : "/plans",
    };
  if (data.value?.pipeline?.pendingReview)
    return {
      title: `${data.value.pipeline.pendingReview} 件检测结果需要复核`,
      body: "查看单件图像与机器判定，再给出人工处理结论。",
      label: "处理待复核记录",
      to: "/records/queue",
    };
  const device = devices.current,
    state = device?.terminal?.state;
  if (device?.connectionState !== "ONLINE")
    return {
      title: "检测设备尚未连接",
      body: "检查供电和网线，在设备诊断中确认连接状态。",
      label: "查看设备连接",
      to: "/diagnostics/registry",
    };
  if (state?.production)
    return {
      title: `正在检测：${state.product?.product || state.product?.name || device.name}`,
      body: "在现场工作台查看实时画面、单件结果和当前批次计数，也可以停止检测或更换产品。",
      label: "查看现场检测",
      to: "/workbench",
    };
  return {
    title: "准备开始检测",
    body: "进入现场工作台，沿用现有配置开检，或直接选择其他产品。批次会随检测自动创建。",
    label: "进入现场工作台",
    to: "/workbench",
  };
});
const actions = [
  {
    title: "现场检测",
    body: "开始、停止、换型和查看实时画面",
    to: "/workbench",
  },
  { title: "产品配置", body: "设置识别对象、合格数量和位置范围", to: "/plans" },
  {
    title: "样本与标注",
    body: "补充训练图片，标注目标并整理样本",
    to: "/data/annotation",
  },
  {
    title: "模型管理",
    body: "导入或查看模型，核对效果并批准使用",
    to: "/models/registry",
  },
];
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>{{ auth.admin ? "管理首页" : "技术维护" }}</h1>
      <p>围绕产品与检查方案，把现场采样、模型准备和正式发布连接起来。</p>
    </div>
    <div class="heading-actions">
      <UiButton variant="secondary" icon="chart" to="/analytics">
        统计看板
      </UiButton>
      <UiButton
        variant="secondary"
        icon="refresh"
        :loading="loading"
        @click="load"
      >
        {{ loading ? "刷新中…" : "刷新概览" }}
      </UiButton>
    </div>
  </div>

  <AsyncState :loading="loading" :error="error" @retry="load">
    <!-- 下一步推进任务卡片 -->
    <UiCard variant="accent" padding="lg" class="management-next-card">
      <div class="management-next-grid">
        <div class="management-next-main">
          <UiBadge tone="forest" chip dot :pulse="true" class="mb-3">
            {{ auth.admin ? "当前需要你处理" : "维护职责" }}
          </UiBadge>
          <h2>{{ next.title }}</h2>
          <p>{{ next.body }}</p>
          <UiButton variant="primary" size="md" :to="next.to">
            {{ next.label }}
          </UiButton>
        </div>
        <aside class="management-next-aside">
          <b>可配置，不限定一种产品</b>
          <p>
            方案决定检查什么；兼容模型负责识别；业务规则用于判定。网络模板和量化参数由开发者维护。
          </p>
          <RouterLink to="/plans" class="text-link"
            >查看方案能力与边界</RouterLink
          >
        </aside>
      </div>
    </UiCard>

    <!-- 核心统计指标 -->
    <div v-if="ready" class="management-counts">
      <UiStat
        label="已配置方案版本"
        :value="plans.length"
        icon="clipboard"
        to="/plans"
        hint="点击进入方案配置"
      />
      <UiStat
        label="真实现场样本"
        :value="ready.realSamples"
        icon="database"
        to="/data/samples"
        hint="工位实采原始画面"
      />
      <UiStat
        :label="auth.admin ? '真实样本待审核与标注' : '已完成标注样本'"
        :value="auth.admin ? pendingReal : ready.annotatedReal"
        icon="audit"
        to="/data/annotation"
        :tone="auth.admin && pendingReal > 0 ? 'warn' : 'default'"
        :hint="auth.admin ? '建议及时审核以供训练' : '已标注可冻结'"
      />
      <UiStat
        label="候选模型（待验证）"
        :value="ready.candidateModels"
        icon="layers"
        to="/models/registry"
        hint="核对效果后由管理员批准使用"
      />
    </div>

    <!-- 常用操作流程卡片 -->
    <section class="management-section">
      <div class="section-heading">
        <div>
          <h2>常用操作</h2>
          <span class="subtext">按当前需要选择，不必逐项完成</span>
        </div>
      </div>
      <div class="management-actions">
        <UiCard
          v-for="action in actions"
          :key="action.to"
          hover
          padding="md"
          class="action-card"
        >
          <RouterLink :to="action.to" class="action-card-link">
            <h3 class="action-title">
              {{ action.title }}
            </h3>
            <p class="action-body">{{ action.body }}</p>
          </RouterLink>
        </UiCard>
      </div>
    </section>

    <!-- 产品与检查方案展示 -->
    <section v-if="plans.length" class="management-section">
      <div class="section-heading">
        <div>
          <h2>产品与检查方案</h2>
          <span class="subtext">当前可用的现场检验规格</span>
        </div>
        <UiButton variant="ghost" size="sm" to="/plans">全部方案</UiButton>
      </div>
      <div class="management-plans">
        <UiCard
          v-for="plan in plans.slice(0, 3)"
          :key="plan.id"
          hover
          padding="md"
          class="plan-card-item"
        >
          <RouterLink
            :to="{
              name: 'models',
              params: { tab: 'deployments' },
              query: { planId: plan.id },
            }"
            class="plan-card-link"
          >
            <div class="plan-card-head">
              <b>{{ plan.rules.product }}</b>
              <UiBadge tone="info" chip size="sm">V{{ plan.version }}</UiBadge>
            </div>

            <small class="plan-status-text">{{
              plan.rules.checks.some((check) => check.min > 0)
                ? "规则已保存，开检时核对设备与模型"
                : "需补充计件主体"
            }}</small>
          </RouterLink>
        </UiCard>
      </div>
    </section>

    <!-- 职责分工提示卡片 -->
    <UiCard variant="flat" padding="md" class="responsibility-card">
      <div class="responsibility-inner">
        <div class="resp-icon">
          <Icon name="users" :size="20" />
        </div>
        <div class="resp-content">
          <b>职责分工说明</b>
          <p>
            <strong>现场工人</strong>：按任务留样、监控画面与复核；
            <strong>管理员</strong>：制定产品方案、审核样本并批准模型上线；
            <strong>技术维护人员</strong>：维护设备通信与部署、协助模型验证。
          </p>
        </div>
        <div v-if="auth.admin" class="resp-action">
          <UiButton variant="outline" size="sm" to="/access/users">
            管理人员与权限
          </UiButton>
        </div>
      </div>
    </UiCard>
  </AsyncState>
</template>

<style scoped>
.mb-3 {
  margin-bottom: 12px;
}

.management-next-card {
  margin-top: 4px;
}

.management-next-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 40px;
  align-items: center;
}

.management-next-main h2 {
  font-size: clamp(22px, 2.2vw, 30px);
  margin: 10px 0 14px;
  color: var(--ink);
  line-height: 1.35;
}

.management-next-main p {
  font-size: 14px;
  line-height: 1.8;
  color: var(--muted);
  max-width: 600px;
  margin-bottom: 22px;
}

.management-next-aside {
  border-left: 1px solid var(--line);
  padding-left: 28px;
  color: var(--ink-2);
}

.management-next-aside b {
  display: block;
  font-size: 14px;
  color: var(--ink);
  margin-bottom: 8px;
}

.management-next-aside p {
  font-size: 13px;
  line-height: 1.7;
  color: var(--muted);
  margin-bottom: 14px;
}

.text-link {
  font-size: 13px;
  color: var(--forest);
  text-decoration: none;
  font-weight: 550;
}
.text-link:hover {
  text-decoration: underline;
}

/* 统计卡片栅格 */
.management-counts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-top: 24px;
}

.management-section {
  margin-top: 32px;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 16px;
}

.section-heading h2 {
  font-size: 18px;
  font-weight: 650;
  margin: 0;
  color: var(--ink);
}

.section-heading .subtext {
  font-size: 12px;
  color: var(--muted);
  margin-left: 8px;
}

/* 工作流动作卡片 */
.management-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.action-card {
  height: 100%;
}

.action-card-link {
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.action-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.action-owner {
  font-size: 11px;
  color: var(--muted);
}

.action-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.action-arrow {
  color: var(--forest);
  transition: transform 0.18s ease;
}

.action-card:hover .action-arrow {
  transform: translateX(4px);
}

.action-body {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
  line-height: 1.6;
}

/* 方案卡片 */
.management-plans {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.plan-card-item {
  height: 100%;
}

.plan-card-link {
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 6px;
  height: 100%;
}

.plan-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.plan-card-head b {
  font-size: 15px;
  color: var(--ink);
}

.plan-spec {
  font-size: 13px;
  color: var(--muted);
}

.plan-status-text {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
}

/* 职责卡片 */
.responsibility-card {
  margin-top: 32px;
}

.responsibility-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}

.resp-icon {
  color: var(--forest);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--surface);
  flex-shrink: 0;
  border: 1px solid var(--line);
}

.resp-content {
  flex: 1;
  min-width: 0;
}

.resp-content b {
  display: block;
  font-size: 14px;
  color: var(--ink);
  margin-bottom: 4px;
}

.resp-content p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--muted);
}

.resp-content strong {
  color: var(--ink);
}

.resp-action {
  flex-shrink: 0;
}

@media (max-width: 1000px) {
  .management-next-grid {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .management-next-aside {
    border-left: 0;
    border-top: 1px solid var(--line);
    padding: 20px 0 0;
  }
  .management-counts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .management-actions,
  .management-plans {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .responsibility-inner {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 600px) {
  .management-counts,
  .management-actions,
  .management-plans {
    grid-template-columns: 1fr;
  }
}
</style>
