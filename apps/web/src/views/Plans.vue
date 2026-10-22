<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type {
  InspectionPlan,
  PlanRules,
  InspectionScenario,
} from "@vision/contracts";
import { postprocessSchema } from "@vision/contracts";
import { api, post } from "../api";
import { useAuthStore } from "../stores/auth";
import { useNotificationStore } from "../stores/notifications";
import Drawer from "../components/Drawer.vue";
import { useProductStore } from "../stores/product";
import AsyncState from "../components/AsyncState.vue";
import {
  UiButton,
  UiCard,
  UiBadge,
  UiInput,
  UiSelect,
  UiEmpty,
  UiModal,
} from "../components/ui";

const auth = useAuthStore(),
  router = useRouter(),
  route = useRoute(),
  notices = useNotificationStore(),
  workflow = useProductStore();
const plans = ref<InspectionPlan[]>([]),
  loading = ref(false),
  error = ref(""),
  busy = ref(false);
const editing = ref(false),
  detail = ref<InspectionPlan | null>(null),
  deleting = ref<InspectionPlan | null>(null);
const product = ref(""),
  purpose = ref<PlanRules["purpose"]>("PRESENCE"),
  instructions = ref(""),
  conditions = ref("");
const scenarios = ref<InspectionScenario[]>([]);
const postprocess = ref(postprocessSchema.parse({}));
const entryRegion = () => ({ x: 0, y: 0, width: 100, height: 100 });
const entries = ref([
  { name: "", min: 1, max: 1, positioned: false, region: entryRegion() },
]);
const region = ref({ x: 0, y: 0, width: 100, height: 100 });
const purposes = {
  PRESENCE: "部件齐全",
  COUNT: "数量与配装",
  APPEARANCE: "可见外观",
  POSITION: "位置范围 / 液面",
};
async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [result, templates] = await Promise.all([
      api<{ items: InspectionPlan[] }>("/plans?pageSize=100"),
      api<InspectionScenario[]>("/plans/scenarios"),
    ]);
    plans.value = result.items.filter((p) => Array.isArray(p.rules.classes));
    scenarios.value = templates;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
watch(
  [
    plans,
    () => route.query.edit,
    () => route.query.inspect,
    () => route.query.create,
  ],
  () => {
    if (route.query.create === "1" && auth.admin) open();
    else {
      const plan = plans.value.find((item) => item.id === route.query.planId);
      if (!plan) return;
      if (route.query.edit === "1" && auth.admin) open(plan);
      else if (route.query.inspect === "1") detail.value = plan;
      else return;
    }
    void router.replace({
      query: {
        ...route.query,
        edit: undefined,
        inspect: undefined,
        create: undefined,
      },
    });
  },
  { immediate: true },
);
function open(plan?: Pick<InspectionPlan, "name" | "rules">) {
  postprocess.value = postprocessSchema.parse(plan?.rules.postprocess ?? {});
  product.value = plan?.rules.product ?? "";
  purpose.value = plan?.rules.purpose ?? "PRESENCE";
  instructions.value = plan?.rules.instructions ?? "";
  conditions.value = plan?.rules.conditions ?? "";
  entries.value = plan
    ? plan.rules.classes.map((label, classId) => {
        const check = plan.rules.checks.find((c) => c.classId === classId);
        return {
          name: label,
          min: check?.min ?? 1,
          max: check?.max ?? 1,
          positioned: !!check?.region,
          region: check?.region
            ? {
                x: check.region.x * 100,
                y: check.region.y * 100,
                width: check.region.width * 100,
                height: check.region.height * 100,
              }
            : entryRegion(),
        };
      })
    : [{ name: "", min: 1, max: 1, positioned: false, region: entryRegion() }];
  region.value = plan
    ? (Object.fromEntries(
        Object.entries(plan.rules.region).map(([k, v]) => [
          k,
          Math.round(v * 100),
        ]),
      ) as typeof region.value)
    : { x: 0, y: 0, width: 100, height: 100 };
  editing.value = true;
}
async function save() {
  if (busy.value || !auth.admin) return;
  if (
    new Set(entries.value.map((entry) => entry.name.trim())).size !==
    entries.value.length
  ) {
    notices.add("类别名称不能重复", true);
    return;
  }
  if (
    region.value.x + region.value.width > 100 ||
    region.value.y + region.value.height > 100
  ) {
    notices.add("检查区域不能超出原图，请调整边距或宽高", true);
    return;
  }
  busy.value = true;
  try {
    const rules: PlanRules = {
      product: product.value,
      postprocess: postprocess.value,
      purpose: purpose.value,
      classes: entries.value.map((e) => e.name),
      instructions: instructions.value,
      conditions: conditions.value,
      referenceUrl: "",
      coordinateSpace: "NORMALIZED_FRAME",
      region: {
        x: region.value.x / 100,
        y: region.value.y / 100,
        width: region.value.width / 100,
        height: region.value.height / 100,
      },
      checks: entries.value.map((e, classId) => ({
        classId,
        min: e.min,
        max: e.max,
        ...(e.positioned
          ? {
              region: {
                x: e.region.x / 100,
                y: e.region.y / 100,
                width: e.region.width / 100,
                height: e.region.height / 100,
              },
            }
          : {}),
      })),
    };
    const saved = await post<InspectionPlan>("/plans", {
      name: product.value,
      rules,
    });
    editing.value = false;
    detail.value = null;
    await workflow.load();
    workflow.select(saved.id);
    notices.add("产品规则已保存，请确认后应用并开始检测");
    await router.push({
      name: route.query.returnTo === "workbench" ? "workbench" : "models",
      params:
        route.query.returnTo === "workbench" ? {} : { tab: "deployments" },
      query: {
        planId: saved.id,
        deviceId: route.query.deviceId,
        modelId: route.query.modelId,
        ...(route.query.returnTo === "workbench" ? { setup: "1" } : {}),
      },
    });
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
function ruleText(plan: InspectionPlan, classId: number) {
  const check = plan.rules.checks.find((c) => c.classId === classId);
  const count = !check
    ? "未设置"
    : check.max === 0
      ? "不应出现"
      : check.min === check.max
        ? `需要 ${check.min} 个`
        : `${check.min}–${check.max} 个`;
  return (
    count +
    (check?.region
      ? `；中心位置 X ${(check.region.x * 100).toFixed(0)}–${((check.region.x + check.region.width) * 100).toFixed(0)}%，Y ${(check.region.y * 100).toFixed(0)}–${((check.region.y + check.region.height) * 100).toFixed(0)}%`
      : "")
  );
}
async function requestDelete(plan: InspectionPlan) {
  detail.value = null;
  editing.value = false;
  await nextTick();
  deleting.value = plan;
}
async function remove() {
  if (!deleting.value || busy.value || !auth.admin) return;
  busy.value = true;
  try {
    await api(`/plans/${deleting.value.id}`, {
      method: "DELETE",
      body: JSON.stringify({ confirm: true }),
    });
    deleting.value = null;
    await load();
    notices.add("方案版本已删除，已有任务及历史数据保留");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>产品配置</h1>
      <p>
        定义检查对象、摆放要求、合格数量规则，再为方案组织采样与验证兼容模型。
      </p>
    </div>
    <div class="heading-actions">
      <UiButton v-if="auth.admin" variant="primary" icon="scan" @click="open()">
        新建检查方案
      </UiButton>
    </div>
  </div>

  <UiCard v-if="scenarios.length" padding="md" class="section-space">
    <template #header>
      <div>
        <h2 class="section-card-title">常用产品模板</h2>
        <p class="note">
          这些是可编辑的规则起点。保存方案并分配兼容模型后，Web 与 HDMI
          终端执行同一份规则。
        </p>
      </div>
      <UiButton
        variant="secondary"
        size="sm"
        icon="refresh"
        :loading="loading"
        @click="load"
      >
        刷新模板
      </UiButton>
    </template>

    <div class="plan-grid">
      <UiCard
        v-for="scenario in scenarios"
        :key="scenario.id"
        hover
        padding="md"
        class="scenario-card"
      >
        <h3>{{ scenario.name }}</h3>
        <p class="scenario-desc">{{ scenario.description }}</p>
        <div class="scenario-footer">
          <UiButton
            v-if="auth.admin"
            variant="outline"
            size="sm"
            @click="open({ name: scenario.name, rules: scenario.rules })"
          >
            使用此模板
          </UiButton>
        </div>
      </UiCard>
    </div>
  </UiCard>

  <div class="plan-intro">
    <div class="intro-block">
      <b>同一工位，适配不同产品</b>
      <p>
        外观缺陷、液面位置、数量检查都从方案开始。类别和数量由你定义，模型仍须满足设备支持的模板。
      </p>
    </div>
    <div class="intro-block">
      <b>应用到终端后生效</b>
      <p>保存的是采样与验收依据。将产品规则与已验证模型应用到终端后生效。</p>
    </div>
  </div>

  <AsyncState :loading="loading" :error="error" @retry="load">
    <UiCard v-if="!plans.length" padding="lg" class="plan-empty-card">
      <UiEmpty
        icon="clipboard"
        title="从你的第一个产品开始"
        description="例如：包装盒需要盒体、吸管和标签；托盘需要一盒饮品和两件配件。类别不必沿用默认名称。"
      >
        <template #actions>
          <UiButton
            v-if="auth.admin"
            variant="primary"
            icon="scan"
            @click="open()"
          >
            新增第一个产品方案
          </UiButton>
          <span v-else class="text-muted"
            >请管理员创建检查方案，维护人员可以查看并协助验证。</span
          >
        </template>
      </UiEmpty>
    </UiCard>

    <div v-else class="plan-grid">
      <UiCard
        v-for="plan in plans"
        :key="plan.id"
        hover
        padding="md"
        class="plan-card"
      >
        <template #header>
          <div class="plan-card-head">
            <UiBadge tone="neutral" chip size="sm">
              {{ purposes[plan.rules.purpose] ?? "已有方案" }}
            </UiBadge>
            <UiBadge tone="forest" chip size="sm">
              V{{ plan.version }} · 已保存
            </UiBadge>
          </div>
        </template>

        <h2 class="plan-name">{{ plan.rules.product }}</h2>
        <p class="plan-product">
          V{{ plan.version }} · {{ purposes[plan.rules.purpose] }}
        </p>

        <ul class="plan-class-list">
          <li v-for="(label, id) in plan.rules.classes" :key="id">
            <b>{{ label }}</b>
            <span>{{ ruleText(plan, id) }}</span>
          </li>
        </ul>

        <div class="row-actions section-space">
          <UiButton variant="secondary" size="sm" @click="detail = plan">
            查看配置
          </UiButton>
          <UiButton
            variant="primary"
            size="sm"
            :to="{
              name: 'models',
              params: { tab: 'deployments' },
              query: { planId: plan.id },
            }"
          >
            使用此产品
          </UiButton>
        </div>
      </UiCard>
    </div>
  </AsyncState>
  <Drawer v-if="editing" title="配置产品" @close="editing = false"
    ><form @submit.prevent="save">
      <p class="note">每次保存生成新版本，正在运行的生产保持原版本。</p>
      <label
        >产品名称<input
          v-model="product"
          placeholder="填写实际产品或配装组合"
          required
          maxlength="120"
      /></label>
      <label
        >检查目标<UiSelect v-model="purpose">
          <option value="PRESENCE">部件齐全：检查必需部件是否存在</option>
          <option value="COUNT">数量与配装：检查种类、数量</option>
          <option value="APPEARANCE">可见外观：检查指定异常是否出现</option>
          <option value="POSITION">位置范围：检查液面或部件的合格位置</option>
        </UiSelect></label
      >
      <h3>需要识别的对象与合格数量</h3>
      <p class="note">
        缺件检查标注实际存在的部件；外观异常可将合格数量设为 0。
        自动计件还需要产品主体或必需部件作为存在依据，合格数量至少为 1。
      </p>
      <div
        v-for="(entry, index) in entries"
        :key="index"
        class="plan-class-row"
      >
        <label
          >类别 {{ index + 1
          }}<input
            v-model="entry.name"
            required
            maxlength="40"
            placeholder="例如：盒体、标签或污渍" /></label
        ><label
          >最少<input
            v-model.number="entry.min"
            type="number"
            min="0"
            max="100"
            required /></label
        ><label
          >最多<input
            v-model.number="entry.max"
            type="number"
            :min="entry.min"
            max="100"
            required /></label
        ><button
          type="button"
          :disabled="entries.length === 1"
          @click="entries.splice(index, 1)"
          :aria-label="`移除类别${index + 1}`"
        >
          移除
        </button>
        <details class="section-space" :open="entry.positioned">
          <summary>位置范围（可选）</summary>
          <label class="check-row"
            ><input
              type="checkbox"
              v-model="entry.positioned"
            />仅统计框中心落在指定范围内的该类对象</label
          >
          <div v-if="entry.positioned" class="plan-region">
            <label
              v-for="(label, key) in {
                x: '左边距',
                y: '上边距',
                width: '宽度',
                height: '高度',
              }"
              :key="key"
              >{{ label }} %
              <input
                type="number"
                v-model.number="entry.region[key]"
                :min="key === 'width' || key === 'height' ? 1 : 0"
                max="100"
                required
              />
            </label>
          </div>
        </details>
      </div>
      <button
        type="button"
        :disabled="entries.length >= 6"
        @click="
          entries.push({
            name: '',
            min: purpose === 'APPEARANCE' ? 0 : 1,
            max: purpose === 'APPEARANCE' ? 0 : 1,
            positioned: false,
            region: entryRegion(),
          })
        "
      >
        添加类别
      </button>
      <p class="note">当前兼容模板最多 6 类，这是设备边界，不限定产品种类。</p>
      <details class="section-space">
        <summary>目标框后处理与跟踪</summary>
        <p class="note">
          先过滤无效和过小框。置信度优先模式保留更可信的同类框，再处理包含与重叠；
          同分时优先较小框。不同类别保留，避免删除瓶体与液面、托盘与物件。跟踪
          ID
          仅用于当前会话。固定机位使用空场参考辅助离场判断；开始生产时先保持空场。
          单件数量参考连续多帧，数量组合不稳定时转人工复核；生产件数按过件记录统计。
        </p>
        <div class="plan-region">
          <label
            >包含框处理<UiSelect v-model="postprocess.algorithm">
              <option value="BOX_FILTER_V3">置信度优先</option>
              <option value="BOX_FILTER_V2">小框优先（原版本）</option>
            </UiSelect></label
          >
          <label
            >重叠去重 IoU<input
              v-model.number="postprocess.nmsIou"
              type="number"
              min="0.05"
              max="0.95"
              step="0.01"
              required
          /></label>
          <label
            >包含覆盖率<input
              v-model.number="postprocess.containment"
              type="number"
              min="0.5"
              max="1"
              step="0.01"
              required
          /></label>
          <label
            >最小框面积 / 原图面积<input
              v-model.number="postprocess.minArea"
              type="number"
              min="0"
              max="0.1"
              step="0.00001"
              required
          /></label>
          <label
            >单帧最多目标<input
              v-model.number="postprocess.maxDetections"
              type="number"
              min="1"
              max="300"
              required
          /></label>
          <label
            >跟踪匹配 IoU<input
              v-model.number="postprocess.trackIou"
              type="number"
              min="0.05"
              max="0.95"
              step="0.01"
              required
          /></label>
          <label
            >确认帧数<input
              v-model.number="postprocess.trackMinHits"
              type="number"
              min="1"
              max="10"
              required
          /></label>
          <label
            >允许丢失帧数<input
              v-model.number="postprocess.trackMaxMisses"
              type="number"
              min="0"
              max="30"
              required
          /></label>
          <label
            >最长丢失时间 ms<input
              v-model.number="postprocess.trackMaxGapMs"
              type="number"
              min="100"
              max="5000"
              step="1"
              required
          /></label>
        </div>
        <p class="note">
          目标超出上限会转人工复核，不用截断后的数量给出合格结论。
        </p>
      </details>
      <label
        >摆放与采样指引<textarea
          v-model="instructions"
          rows="3"
          required
          maxlength="2000"
          placeholder="告诉工人如何摆放，以及需要采集哪些正常、缺件、偏位和空场景图片"
        /></label
      ><label
        >成像条件<textarea
          v-model="conditions"
          rows="2"
          maxlength="1000"
          placeholder="例如：固定俯拍、柔和光线、背景和距离保持一致"
        />
      </label>
      <details class="section-space">
        <summary>检查区域（原图百分比）</summary>
        <p class="note">
          只统计整体检查区域内的对象；此配置不改变模型输入或图像裁剪。
        </p>
        <div class="plan-region">
          <label
            v-for="(label, key) in {
              x: '左边距',
              y: '上边距',
              width: '宽度',
              height: '高度',
            }"
            :key="key"
            >{{ label }} %<input
              v-model.number="region[key]"
              type="number"
              :min="key === 'width' || key === 'height' ? 1 : 0"
              max="100"
              required
          /></label>
        </div>
      </details>
      <div class="form-actions section-space">
        <UiButton
          variant="primary"
          type="submit"
          :disabled="busy"
          :loading="busy"
        >
          {{ busy ? "保存中…" : "保存并继续 →" }}
        </UiButton>
        <UiButton variant="secondary" type="button" @click="editing = false">
          取消
        </UiButton>
      </div>
    </form></Drawer
  >
  <Drawer
    v-if="detail && !editing"
    :title="`${detail.rules.product} · V${detail.version}`"
    @close="detail = null"
  >
    <UiBadge tone="forest" chip size="sm" class="mb-2"
      >规则已保存 · 应用到设备后生效</UiBadge
    >
    <h3>{{ detail.rules.product }}</h3>
    <p class="plan-purpose-desc">{{ purposes[detail.rules.purpose] }}</p>
    <div
      v-for="(label, id) in detail.rules.classes"
      :key="id"
      class="list-line"
    >
      <b>{{ label }}</b>
      <span>{{ ruleText(detail, id) }}</span>
    </div>
    <h3 class="mt-4">工人采样指引</h3>
    <p class="plan-instructions">{{ detail.rules.instructions }}</p>
    <p class="plan-conditions">
      {{ detail.rules.conditions || "未补充成像条件" }}
    </p>
    <p class="note">
      确认规则后，直接应用并开始检测。缺少兼容模型时，应用页会提供准备入口。
    </p>
    <div class="form-actions">
      <UiButton
        variant="primary"
        :to="{
          name: 'models',
          params: { tab: 'deployments' },
          query: { planId: detail.id },
        }"
        @click="detail = null"
        >使用此产品</UiButton
      >
      <UiButton v-if="auth.admin" variant="secondary" @click="open(detail)">
        修改并保存新版本
      </UiButton>
      <UiButton
        v-if="auth.admin"
        variant="danger"
        :disabled="busy"
        @click="requestDelete(detail)"
      >
        删除方案版本
      </UiButton>
    </div>
  </Drawer>

  <!-- 删除确认弹窗 -->
  <UiModal
    :model-value="Boolean(deleting)"
    title="删除方案版本"
    @close="!busy && (deleting = null)"
  >
    <template v-if="deleting">
      <p>
        确认删除“<b>{{ deleting.name }} / V{{ deleting.version }}</b
        >”？
      </p>
      <p class="note">
        此版本将从方案列表和新任务选项中移除。已关联任务继续使用原版本，已有图片、标注、数据集和检测记录保留。其他方案版本不受影响。
      </p>
    </template>
    <template #footer>
      <UiButton variant="secondary" :disabled="busy" @click="deleting = null">
        取消
      </UiButton>
      <UiButton
        variant="danger"
        :disabled="busy"
        :loading="busy"
        @click="remove"
      >
        {{ busy ? "正在删除…" : "确认删除" }}
      </UiButton>
    </template>
  </UiModal>
</template>
<style scoped>
.plan-intro {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  padding: 24px;
  background: var(--surface);
  border: 1px solid var(--line);
  margin-bottom: 24px;
}
.plan-intro p,
.plan-empty p {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.8;
}
.plan-empty {
  padding: 36px;
  background: var(--surface);
  border: 1px dashed var(--line);
}
.plan-empty ol {
  font-size: 14px;
  line-height: 2.2;
  padding-left: 20px;
}
.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
  gap: 20px;
}
.plan-card {
  padding: 24px;
  border: 1px solid var(--line);
  background: var(--surface);
}
.plan-card-head {
  display: flex;
  justify-content: space-between;
  color: var(--muted);
  font-size: 11px;
}
.plan-card h2 {
  font-size: 21px;
  margin: 20px 0 8px;
}
.plan-card p {
  color: var(--muted);
  font-size: 13px;
}
.plan-card ul {
  list-style: none;
  padding: 0;
  margin: 20px 0;
}
.plan-card li {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.plan-card li span {
  color: var(--muted);
}
.plan-class-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) 70px 70px auto;
  gap: 8px;
  align-items: center;
}
.plan-class-row > details {
  grid-column: 1 / -1;
}
.plan-class-row input {
  min-width: 0;
}
.plan-region {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.plan-instructions {
  white-space: pre-wrap;
  line-height: 1.8;
}
@media (max-width: 760px) {
  .plan-intro {
    grid-template-columns: 1fr;
  }
  .plan-class-row {
    grid-template-columns: 1fr 1fr;
  }
  .plan-class-row label:first-child {
    grid-column: 1/-1;
  }
  .plan-empty {
    padding: 24px;
  }
}
</style>
