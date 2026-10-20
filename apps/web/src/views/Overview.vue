<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { displayName } from "@vision/shared";
import type { InspectionPlan } from "@vision/contracts";
import { api } from "../api";
import { useAuthStore } from "../stores/auth";
import AsyncState from "../components/AsyncState.vue";
import Icon from "../components/Icon.vue";
const auth = useAuthStore();
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
  if (!auth.admin)
    return {
      title: "设备、标注与模型验证",
      body: "维护当前硬件模板，协助完成标注和训练。方案变更与正式发布由管理员负责。",
      label: "查看训练任务",
      to: "/models/training",
    };
  if (!plans.value.length)
    return {
      title: "先建立你的产品检查方案",
      body: "填写产品、识别对象、合格数量和摆放要求，再安排工人采样。支持部件齐全、数量配装和可见外观等任务。",
      label: "配置第一个方案",
      to: "/plans",
    };
  if (pendingReal.value)
    return {
      title: `${pendingReal.value} 张真实样本等待审核`,
      body: "完成标注即确认图片可用于训练；不合适的图片可直接弃用。",
      label: "审核采样数据",
      to: "/data/annotation",
    };
  return {
    title: "按方案推进下一次换型",
    body: "查看采样进度、整理审核后的数据，验证候选模型，再决定是否发布。训练完成不会自动替换设备模型。",
    label: "查看产品与方案",
    to: "/plans",
  };
});
const actions = computed(() => [
  {
    number: "01",
    title: "产品与方案",
    body: "定义检查对象、数量和采样标准",
    to: "/plans",
    owner: "管理员配置",
  },
  {
    number: "02",
    title: "安排与采样",
    body: "按当前产品方案留样，不重复记为检测件数",
    to: "/workbench",
    owner: "现场人员留样",
  },
  {
    number: "03",
    title: "标注与审核",
    body: "标出对象，接纳或退回现场样本",
    to: auth.admin ? "/data/annotation" : "/data/annotation",
    owner: "管理员 / 工程师",
  },
  {
    number: "04",
    title: "训练与验证",
    body: "冻结数据，训练并验证候选模型",
    to: "/models/training",
    owner: "管理员 / 技术维护人员",
  },
  ...(auth.admin
    ? [
        {
          number: "05",
          title: "批准发布",
          body: "核对效果和兼容性，再发布或回退",
          to: "/models/deployments",
          owner: "仅管理员",
        },
      ]
    : []),
  {
    number: "06",
    title: "现场使用与反馈",
    body: "查看板端批次结果，提交复核意见",
    to: "/production",
    owner: "工人 / 管理员",
  },
]);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>{{ auth.admin ? "管理首页" : "技术维护" }}</h1>
      <p>围绕产品与检查方案，把现场采样、模型准备和正式发布连接起来。</p>
    </div>
    <button
      class="overview-refresh"
      @click="load"
      :disabled="loading"
      :aria-busy="loading"
    >
      <Icon name="refresh" :size="16" />{{ loading ? "刷新中…" : "刷新概览" }}
    </button>
  </div>
  <AsyncState :loading="loading" :error="error" @retry="load">
    <section class="management-next">
      <div>
        <span class="eyebrow">{{
          auth.admin ? "当前需要你处理" : "维护职责"
        }}</span>
        <h2>{{ next.title }}</h2>
        <p>{{ next.body }}</p>
        <RouterLink class="button-link primary" :to="next.to"
          >{{ next.label }} →</RouterLink
        >
      </div>
      <aside>
        <b>可配置，不限定一种产品</b>
        <p>
          方案决定检查什么；兼容模型负责识别；业务规则用于判定。网络模板和量化参数由开发者维护。
        </p>
        <RouterLink to="/plans">查看方案能力与边界</RouterLink>
      </aside>
    </section>
    <div v-if="ready" class="management-counts">
      <RouterLink to="/plans"
        ><Icon name="clipboard" /><strong>{{ plans.length }}</strong
        ><span>已配置方案版本</span></RouterLink
      ><RouterLink to="/data/samples"
        ><Icon name="database" /><strong>{{ ready.realSamples }}</strong
        ><span>真实现场样本</span></RouterLink
      ><RouterLink :to="auth.admin ? '/data/annotation' : '/data/annotation'"
        ><Icon name="audit" /><strong>{{
          auth.admin ? pendingReal : ready.annotatedReal
        }}</strong
        ><span>{{
          auth.admin ? "真实样本待筛选与标注" : "已完成标注"
        }}</span></RouterLink
      ><RouterLink to="/models/registry"
        ><Icon name="layers" /><strong>{{ ready.candidateModels }}</strong
        ><span>候选模型，尚需验证</span></RouterLink
      >
    </div>
    <section class="management-section">
      <div class="section-heading">
        <h2>从方案到现场</h2>
        <span>每一步都有明确负责人</span>
      </div>
      <div class="management-actions">
        <RouterLink
          v-for="action in actions"
          :key="action.number"
          :to="action.to"
          ><small>{{ action.number }} / {{ action.owner }}</small>
          <h3>{{ action.title }} <span>→</span></h3>
          <p>{{ action.body }}</p></RouterLink
        >
      </div>
    </section>
    <section v-if="plans.length" class="management-section">
      <div class="section-heading">
        <h2>产品与检查方案</h2>
        <RouterLink to="/plans">全部方案 →</RouterLink>
      </div>
      <div class="management-plans">
        <RouterLink v-for="plan in plans.slice(0, 3)" :key="plan.id" to="/plans"
          ><b>{{ displayName(plan.name) }}</b
          ><span>{{ plan.rules.product }} · V{{ plan.version }}</span
          ><small>已保存配置，未下发规则</small></RouterLink
        >
      </div>
    </section>
    <section class="responsibility-note">
      <b>职责分工</b>
      <p>
        <strong>工人</strong
        >按任务采样、查看结果和提交反馈。<strong>管理员</strong>定义方案、审核数据、决定训练与发布。<strong>技术维护人员</strong>维护设备和模板，协助标注、训练与验证。
      </p>
      <RouterLink v-if="auth.admin" to="/access/users"
        >管理人员与权限 →</RouterLink
      >
    </section>
  </AsyncState>
</template>
<style scoped>
.overview-refresh {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.management-next {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 48px;
  padding: 32px;
  border: 1px solid var(--line);
  border-left: 4px solid var(--forest);
  background: var(--surface);
  border-radius: 12px;
  box-shadow: 0 3px 12px #17211504;
}
.management-next h2 {
  font-size: clamp(23px, 2.3vw, 32px);
  margin: 12px 0;
}
.management-next p {
  font-size: 14px;
  line-height: 1.9;
  color: var(--muted);
  max-width: 620px;
  margin-bottom: 24px;
}
.management-next aside {
  border-left: 1px solid var(--line);
  padding-left: 28px;
  align-self: center;
  color: var(--ink-2);
}
.management-next aside p {
  font-size: 13px;
  margin-bottom: 12px;
}
.management-next aside a {
  font-size: 12px;
}
.eyebrow {
  font-size: 12px;
  color: var(--forest);
  font-weight: 600;
}
.management-counts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-top: 20px;
}
.management-counts > a {
  position: relative;
  display: grid;
  gap: 10px;
  background: var(--surface);
  border: 1px solid var(--line);
  padding: 22px;
  text-decoration: none;
  color: var(--ink);
  border-radius: 10px;
}
.management-counts .icon {
  position: absolute;
  right: 20px;
  top: 23px;
  color: var(--muted);
}
.management-counts strong {
  font-size: 32px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.management-counts span {
  font-size: 12px;
  color: var(--muted);
}
.management-section {
  margin-top: 30px;
}
.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.section-heading h2 {
  font-size: 19px;
  margin: 0;
}
.section-heading span,
.section-heading a {
  font-size: 12px;
  color: var(--muted);
}
.management-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.management-actions > a {
  padding: 22px;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink);
  text-decoration: none;
  border-radius: 10px;
}
.management-actions small {
  font-size: 11px;
  color: var(--muted);
}
.management-actions h3 {
  font-size: 17px;
  margin: 16px 0 8px;
}
.management-actions h3 span {
  float: right;
  color: var(--forest);
  transition: transform 180ms var(--ease-out);
}
.management-actions > a:hover h3 span {
  transform: translateX(4px);
}
.management-actions p {
  font-size: 12px;
  color: var(--muted);
  margin: 0;
  line-height: 1.8;
}
.management-actions > a:hover,
.management-counts > a:hover,
.management-plans > a:hover {
  border-color: color-mix(in srgb, var(--forest) 50%, var(--line));
  box-shadow: 0 5px 18px #17211508;
  transform: translateY(-2px);
}
.management-actions > a,
.management-counts > a,
.management-plans > a {
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms var(--ease-out);
}
.management-plans {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.management-plans > a {
  padding: 22px;
  display: grid;
  gap: 10px;
  background: var(--surface);
  border: 1px solid var(--line);
  text-decoration: none;
  color: var(--ink);
  border-radius: 10px;
}
.management-plans span,
.management-plans small {
  font-size: 12px;
  color: var(--muted);
}
.responsibility-note {
  margin-top: 28px;
  padding: 24px;
  border-top: 1px solid var(--line);
  font-size: 13px;
  line-height: 1.9;
  color: var(--ink-2);
}
.responsibility-note p {
  color: var(--muted);
}
.responsibility-note strong {
  color: var(--ink);
  margin: 0 6px;
}
@media (max-width: 1000px) {
  .management-next {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .management-next aside {
    border-left: 0;
    border-top: 1px solid var(--line);
    padding: 20px 0 0;
  }
  .management-actions,
  .management-plans {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .management-next {
    padding: 24px;
  }
  .management-counts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .management-actions,
  .management-plans {
    grid-template-columns: 1fr;
  }
  .section-heading {
    align-items: start;
  }
}
</style>
