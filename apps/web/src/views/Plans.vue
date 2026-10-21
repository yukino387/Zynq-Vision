<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
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
import AsyncState from "../components/AsyncState.vue";

const auth = useAuthStore(),
  notices = useNotificationStore();
const plans = ref<InspectionPlan[]>([]),
  loading = ref(false),
  error = ref(""),
  busy = ref(false);
const editing = ref(false),
  detail = ref<InspectionPlan | null>(null),
  deleting = ref<InspectionPlan | null>(null);
const name = ref(""),
  product = ref(""),
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
function open(plan?: Pick<InspectionPlan, "name" | "rules">) {
  postprocess.value = postprocessSchema.parse(plan?.rules.postprocess ?? {});
  name.value = plan?.name ?? "";
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
    detail.value = await post<InspectionPlan>("/plans", {
      name: name.value || product.value,
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
      <p>先说明检查什么、怎样摆放、什么算合格，再为这个方案采样和准备模型。</p>
    </div>
    <button v-if="auth.admin" class="primary" @click="open()">
      新建检查方案
    </button>
  </div>
  <section v-if="scenarios.length" class="panel section-space">
    <h2>常见应用场景 · 服务端配置</h2>
    <p class="note">
      这些是可编辑的规则起点。保存方案并分配兼容模型后，Web 与 HDMI
      执行同一份规则。
    </p>
    <div class="plan-grid">
      <article
        v-for="scenario in scenarios"
        :key="scenario.id"
        class="plan-card"
      >
        <h3>{{ scenario.name }}</h3>
        <p>{{ scenario.description }}</p>
        <button
          v-if="auth.admin"
          @click="open({ name: scenario.name, rules: scenario.rules })"
        >
          以此配置方案
        </button>
      </article>
    </div>
    <button @click="load" :disabled="loading">刷新服务端场景</button>
  </section>
  <div class="plan-intro">
    <div>
      <b>同一工位，适配不同产品</b>
      <p>
        外观缺陷、液面位置、数量检查都从方案开始。类别和数量由你定义，模型仍须满足设备支持的模板。
      </p>
    </div>
    <div>
      <b>应用到终端后生效</b>
      <p>保存的是采样与验收依据。将产品规则与已验证模型应用到终端后生效。</p>
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
        <li>导入或拍摄图片，完成标注后训练</li>
      </ol>
      <button v-if="auth.admin" class="primary" @click="open()">
        新增第一个产品
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
        <div class="row-actions section-space">
          <button class="table-action" @click="detail = plan">查看配置</button
          ><RouterLink
            v-if="auth.admin"
            class="table-action"
            :to="{
              name: 'data',
              params: { tab: 'annotation' },
              query: { planId: plan.id },
            }"
            >准备样本 →</RouterLink
          >
          <button
            v-if="auth.admin"
            class="table-action danger"
            :disabled="busy"
            @click="requestDelete(plan)"
          >
            删除方案版本
          </button>
        </div>
      </article>
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
      <details>
        <summary>配置名称（可选）</summary>
        <label
          >名称<input v-model="name" :placeholder="product" maxlength="120"
        /></label>
      </details>
      <label
        >检查目标<select v-model="purpose">
          <option value="PRESENCE">部件齐全：检查必需部件是否存在</option>
          <option value="COUNT">数量与配装：检查种类、数量</option>
          <option value="APPEARANCE">可见外观：检查指定异常是否出现</option>
          <option value="POSITION">位置范围：检查液面或部件的合格位置</option>
        </select></label
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
          先过滤无效和过小框，再删除同类包含框（外框面积至少为内框的 1.5
          倍），最后做同类重叠去重。不同类别保留，避免删除瓶体与液面、托盘与物件。跟踪
          ID 仅用于当前会话；生产件数仍按过件记录统计。
        </p>
        <div class="plan-region">
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
    ><p class="tag">已保存的方案版本</p>
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
      类别、数量与位置范围随方案下发。请在设备配置中分配此版本，设备当前方案以现场工作台为准。
    </p>
    <div class="form-actions">
      <RouterLink
        v-if="auth.admin"
        class="button-link primary"
        :to="{
          name: 'data',
          params: { tab: 'annotation' },
          query: { planId: detail.id },
        }"
        @click="detail = null"
        >为此方案准备样本</RouterLink
      ><button v-if="auth.admin" @click="open(detail)">修改并保存新版本</button>
      <button
        v-if="auth.admin"
        class="danger"
        :disabled="busy"
        @click="requestDelete(detail)"
      >
        删除方案版本
      </button>
    </div></Drawer
  >
  <Drawer
    v-if="deleting"
    title="删除方案版本"
    @close="!busy && (deleting = null)"
  >
    <p>确认删除“{{ deleting.name }} / V{{ deleting.version }}”？</p>
    <p class="note">
      此版本将从方案列表和新任务选项中移除。已关联任务继续使用原版本，已有图片、标注、数据集和检测记录保留。其他方案版本不受影响。
    </p>
    <div class="form-actions">
      <button class="danger" :disabled="busy" @click="remove">
        {{ busy ? "正在删除…" : "确认删除" }}</button
      ><button :disabled="busy" @click="deleting = null">取消</button>
    </div>
  </Drawer>
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
