<script setup lang="ts">
import { ref, onMounted } from "vue";
import type { InspectionPlan, PlanRules } from "@vision/contracts";
import { api, post } from "../api";
import { useAuthStore } from "../stores/auth";
import { useNotificationStore } from "../stores/notifications";
import Drawer from "../components/Drawer.vue";
import AsyncState from "../components/AsyncState.vue";

const auth = useAuthStore(),
  notices = useNotificationStore();
const plans = ref<InspectionPlan[]>([]),
  loading = ref(false),
  error = ref(""),
  busy = ref(false);
const editing = ref(false),
  detail = ref<InspectionPlan | null>(null);
const name = ref(""),
  product = ref(""),
  purpose = ref<PlanRules["purpose"]>("PRESENCE"),
  instructions = ref(""),
  conditions = ref("");
const entries = ref([{ name: "", min: 1, max: 1 }]);
const region = ref({ x: 0, y: 0, width: 100, height: 100 });
const purposes = {
  PRESENCE: "部件齐全",
  COUNT: "数量与配装",
  APPEARANCE: "可见外观",
};
async function load() {
  loading.value = true;
  error.value = "";
  try {
    plans.value = (
      await api<{ items: InspectionPlan[] }>("/plans?pageSize=100")
    ).items.filter((p) => Array.isArray(p.rules.classes));
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
function open(plan?: InspectionPlan) {
  name.value = plan?.name ?? "";
  product.value = plan?.rules.product ?? "";
  purpose.value = plan?.rules.purpose ?? "PRESENCE";
  instructions.value = plan?.rules.instructions ?? "";
  conditions.value = plan?.rules.conditions ?? "";
  entries.value = plan
    ? plan.rules.classes.map((label, classId) => {
        const check = plan.rules.checks.find((c) => c.classId === classId);
        return { name: label, min: check?.min ?? 1, max: check?.max ?? 1 };
      })
    : [{ name: "", min: 1, max: 1 }];
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
      })),
    };
    detail.value = await post<InspectionPlan>("/plans", {
      name: name.value,
      rules,
    });
    editing.value = false;
    await load();
    notices.add("方案版本已保存，可以安排采样");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
function ruleText(plan: InspectionPlan, classId: number) {
  const check = plan.rules.checks.find((c) => c.classId === classId);
  return !check
    ? "未设置"
    : check.max === 0
      ? "不应出现"
      : check.min === check.max
        ? `需要 ${check.min} 个`
        : `${check.min}–${check.max} 个`;
}
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>产品与检查方案</h1>
      <p>先说明检查什么、怎样摆放、什么算合格，再为这个方案采样和准备模型。</p>
    </div>
    <button v-if="auth.admin" class="primary" @click="open()">
      新建检查方案
    </button>
  </div>
  <div class="plan-intro">
    <div>
      <b>同一工位，适配不同产品</b>
      <p>
        包装部件、托盘配装、可见外观都从方案开始。类别和数量由你定义，模型仍须满足设备支持的模板。
      </p>
    </div>
    <div>
      <b>方案配置 ≠ 已在设备生效</b>
      <p>
        保存的是采样与验收依据。当前板端尚未接入通用规则下发，现场结果以设备实际回报为准。
      </p>
    </div>
  </div>
  <AsyncState :loading="loading" :error="error" @retry="load">
    <section v-if="!plans.length" class="plan-empty">
      <h2>从你的第一个产品开始</h2>
      <p>
        例如：包装盒需要盒体、吸管和标签；托盘需要一盒饮品和两件配件。类别不必沿用钢材缺陷名称。
      </p>
      <ol>
        <li>填写产品和检查目标</li>
        <li>写清合格数量、检查区域和摆放要求</li>
        <li>建立采样任务，交给工人采集</li>
      </ol>
      <button v-if="auth.admin" class="primary" @click="open()">
        创建第一个方案
      </button>
      <p v-else>请管理员创建检查方案，维护人员可以查看并协助验证。</p>
    </section>
    <div class="plan-grid">
      <article v-for="plan in plans" :key="plan.id" class="plan-card">
        <div class="plan-card-head">
          <span>{{ purposes[plan.rules.purpose] ?? "已有方案" }}</span
          ><span>V{{ plan.version }} · 已保存</span>
        </div>
        <h2>{{ plan.name }}</h2>
        <p>{{ plan.rules.product }}</p>
        <ul>
          <li v-for="(label, id) in plan.rules.classes" :key="id">
            <b>{{ label }}</b
            ><span>{{ ruleText(plan, id) }}</span>
          </li>
        </ul>
        <div class="form-actions">
          <button @click="detail = plan">查看方案</button
          ><RouterLink
            v-if="auth.admin"
            class="button-link"
            :to="{
              name: 'data',
              params: { tab: 'tasks' },
              query: { planId: plan.id, create: '1' },
            }"
            >安排采样 →</RouterLink
          >
        </div>
      </article>
    </div>
  </AsyncState>
  <Drawer v-if="editing" title="配置检查方案" @close="editing = false"
    ><form @submit.prevent="save">
      <p class="note">每次保存生成新版本，已有采样任务继续引用原版本。</p>
      <label
        >方案名称<input
          v-model="name"
          placeholder="例如：小盒饮品包装检查"
          required
          maxlength="120" /></label
      ><label
        >产品名称<input
          v-model="product"
          placeholder="填写实际产品或配装组合"
          required
          maxlength="120" /></label
      ><label
        >检查目标<select v-model="purpose">
          <option value="PRESENCE">部件齐全：检查必需部件是否存在</option>
          <option value="COUNT">数量与配装：检查种类、数量</option>
          <option value="APPEARANCE">可见外观：检查指定异常是否出现</option>
        </select></label
      >
      <h3>需要识别的对象与合格数量</h3>
      <p class="note">
        缺件检查标注实际存在的部件；外观异常可将合格数量设为 0。
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
      </div>
      <button
        type="button"
        :disabled="entries.length >= 6"
        @click="
          entries.push({
            name: '',
            min: purpose === 'APPEARANCE' ? 0 : 1,
            max: purpose === 'APPEARANCE' ? 0 : 1,
          })
        "
      >
        添加类别
      </button>
      <p class="note">当前兼容模板最多 6 类，这是设备边界，不限定产品种类。</p>
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
        <p class="note">用于采样和验收说明；保存区域不会自动改变板端裁剪。</p>
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
        <button class="primary" :disabled="busy">
          {{ busy ? "保存中…" : "保存方案版本" }}</button
        ><button type="button" @click="editing = false">取消</button>
      </div>
    </form></Drawer
  >
  <Drawer
    v-if="detail && !editing"
    :title="`${detail.name} · V${detail.version}`"
    @close="detail = null"
    ><p class="tag">已保存 · 未下发到设备</p>
    <h3>{{ detail.rules.product }}</h3>
    <p>{{ purposes[detail.rules.purpose] }}</p>
    <div
      v-for="(label, id) in detail.rules.classes"
      :key="id"
      class="list-line"
    >
      <b>{{ label }}</b
      ><span>{{ ruleText(detail, id) }}</span>
    </div>
    <h3>工人采样指引</h3>
    <p class="plan-instructions">{{ detail.rules.instructions }}</p>
    <p>{{ detail.rules.conditions || "未补充成像条件" }}</p>
    <p class="note">
      检查区域以原图百分比记录；训练和板端预处理应另行验证一致性。尚未完成设备规则下发。
    </p>
    <div class="form-actions">
      <RouterLink
        v-if="auth.admin"
        class="button-link primary"
        :to="{
          name: 'data',
          params: { tab: 'tasks' },
          query: { planId: detail.id, create: '1' },
        }"
        @click="detail = null"
        >为此方案安排采样</RouterLink
      ><button v-if="auth.admin" @click="open(detail)">修改并保存新版本</button>
    </div></Drawer
  >
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
