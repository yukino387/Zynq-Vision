<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter, type RouteLocationRaw } from "vue-router";
import { productClassesMatch } from "@vision/shared";
import type { Model } from "@vision/contracts";
import { api, post, errorText } from "../api";
import { useProductStore } from "../stores/product";
import { useDeviceStore } from "../stores/devices";
import { useAuthStore } from "../stores/auth";
import { UiButton } from "./ui";
const props = defineProps<{ inline?: boolean }>();
const emit = defineEmits<{ started: []; cancel: [] }>();
const route = useRoute(),
  router = useRouter(),
  product = useProductStore(),
  devices = useDeviceStore(),
  auth = useAuthStore();
const models = ref<Model[]>([]),
  deviceId = ref(String(route.query.deviceId || devices.selected)),
  modelId = ref(""),
  busy = ref(false),
  error = ref(""),
  loadError = ref(""),
  loading = ref(true);
const targets = computed(() =>
  devices.devices.filter((item) => item.type === "ZYNQ"),
);
const device = computed(() =>
  targets.value.find((item) => item.id === deviceId.value),
);
const state = computed(() => device.value?.terminal?.state);
const online = computed(() => device.value?.connectionState === "ONLINE");
const compatibleCurrent = computed(
  () =>
    !!product.current &&
    productClassesMatch(
      product.current.rules.classes,
      state.value?.model?.classes ?? [],
    ),
);
const compatibleModels = computed(() =>
  models.value.filter(
    (model) =>
      product.current &&
      model.source === "IMPORT" &&
      productClassesMatch(
        product.current.rules.classes,
        Array.isArray(model.manifest.classes) ? model.manifest.classes : [],
      ),
  ),
);
const selectedModel = computed(() =>
  modelId.value
    ? compatibleModels.value.find((model) => model.id === modelId.value)
    : state.value?.model,
);
const unchanged = computed(
  () =>
    online.value &&
    !!product.current &&
    state.value?.product?.id === product.id &&
    state.value.product.version === product.current.version &&
    (!modelId.value || modelId.value === state.value.model?.id),
);
const editProduct = computed<RouteLocationRaw>(() => ({
  name: "plans",
  query: {
    planId: product.id,
    deviceId: deviceId.value || undefined,
    modelId: modelId.value || undefined,
    returnTo: props.inline ? "workbench" : undefined,
    ...(auth.admin ? { edit: "1" } : { inspect: "1" }),
  },
}));
const rules = computed(
  () =>
    product.current?.rules.classes.map((name, classId) => {
      const check = product.current!.rules.checks.find(
        (item) => item.classId === classId,
      );
      return {
        name,
        quantity: !check
          ? "未设置数量"
          : check.max === 0
            ? "禁止出现"
            : check.min === check.max
              ? `每件 ${check.min} 个`
              : `每件 ${check.min}–${check.max} 个`,
      };
    }) ?? [],
);
type Issue = {
  kind: string;
  title: string;
  detail: string;
  action: string;
  to?: RouteLocationRaw;
};
const issue = computed<Issue | null>(() => {
  if (loading.value) return null;
  if (loadError.value)
    return {
      kind: "load",
      title: "配置读取失败",
      detail: loadError.value,
      action: "重新读取",
    };
  if (!product.current)
    return {
      kind: "product",
      title: "先选择要检测的产品",
      detail: "产品决定检测哪些对象，以及什么情况算合格。",
      action: auth.admin ? "新建产品" : "查看已有产品",
      to: { name: "plans", query: auth.admin ? { create: "1" } : {} },
    };
  if (!product.current.rules.checks.some((check) => check.min > 0)) {
    const onlyDefects = product.current.rules.checks.every(
      (check) => check.max === 0,
    );
    return {
      kind: "rules",
      title: "这个产品还不能自动计件",
      detail: onlyDefects
        ? "当前所有对象都设为“禁止出现”。系统能发现异常，却无法确认正常产品是否经过。请加入每件都会出现的产品主体，并使用能识别它的模型。"
        : "所有对象的最少数量都是 0，系统无法确认产品是否经过。请将每件都会出现的产品主体或必需部件设为至少 1 个。",
      action: auth.admin ? "补充产品主体" : "查看产品规则",
      to: editProduct.value,
    };
  }
  if (!online.value)
    return {
      kind: "device",
      title: device.value ? "设备未连接，暂时无法开始" : "请选择检测设备",
      detail: "连接设备后刷新状态；上方可更换接收设备。",
      action: "刷新设备状态",
    };
  if (state.value?.pendingRequestId)
    return {
      kind: "pending",
      title: "上一件检测结果还未确认",
      detail: "先在现场工作台核对记录，再开始下一批检测。",
      action: "去核对记录",
      to: { name: "workbench" },
    };
  if (
    modelId.value &&
    !compatibleModels.value.some((model) => model.id === modelId.value)
  )
    return {
      kind: "model",
      title: "请重新选择模型",
      detail:
        "所选模型与当前产品的类别不匹配，请展开识别模型选项，重新选择兼容模型。",
      action: "查看可用模型",
      to: {
        name: "models",
        params: { tab: "registry" },
        query: { planId: product.id },
      },
    };
  if (!modelId.value && !compatibleCurrent.value)
    return {
      kind: "model",
      title: "缺少能识别此产品的模型",
      detail:
        "模型的识别类别及顺序需要与产品规则一致。可导入并批准现有模型，或从样本训练新模型。",
      action: "准备兼容模型",
      to: {
        name: "models",
        params: { tab: "registry" },
        query: { planId: product.id },
      },
    };
  if (!auth.admin && modelId.value && modelId.value !== state.value?.model?.id)
    return {
      kind: "permission",
      title: "需要管理员更换模型",
      detail: "当前产品需要不同的模型，请联系管理员完成切换。",
      action: "查看模型",
      to: {
        name: "models",
        params: { tab: "registry" },
        query: { planId: product.id },
      },
    };
  return null;
});
const actionLabel = computed(() =>
  busy.value
    ? "正在准备并开始检测…"
    : unchanged.value
      ? state.value?.production
        ? props.inline
          ? "返回实时画面"
          : "查看现场检测"
        : "开始检测"
      : state.value?.production
        ? "切换产品并开始检测"
        : "开始检测",
);
const consequence = computed(() =>
  unchanged.value
    ? state.value?.production
      ? "此产品正在设备上检测，点击后查看实时画面和计件结果。"
      : `沿用设备现有配置，开始后自动创建新批次${props.inline ? "。" : "，并进入现场工作台。"}`
    : state.value?.production
      ? `将结束“${state.value.product?.product || state.value.product?.name || "当前产品"}”的批次，切换为“${product.current?.rules.product}”并开始新批次。`
      : `将产品规则和所选模型发送到设备，成功后开始新批次${props.inline ? "。" : "，并进入现场工作台。"}`,
);
watch(
  [
    () => product.current,
    deviceId,
    () => state.value?.model?.id,
    () => route.query.modelId,
    models,
  ],
  () => {
    error.value = "";
    modelId.value =
      typeof route.query.modelId === "string"
        ? route.query.modelId
        : compatibleCurrent.value
          ? ""
          : (compatibleModels.value[0]?.id ?? "");
  },
  { immediate: true },
);
watch(
  () => route.query.planId,
  (id) => {
    if (typeof id === "string") product.select(id);
  },
  { immediate: true },
);
watch(
  targets,
  (items) => {
    if (!deviceId.value)
      deviceId.value =
        items.find((item) => item.connectionState === "ONLINE")?.id ??
        items[0]?.id ??
        "";
  },
  { immediate: true },
);
watch(
  () => devices.selected,
  (id) => {
    if (props.inline && id) deviceId.value = id;
  },
);
async function load() {
  loading.value = true;
  loadError.value = "";
  try {
    await Promise.all([
      product.load(),
      api<{ items: Model[] }>(
        "/models?status=APPROVED&realOnly=true&pageSize=100",
      ).then((result) => {
        models.value = result.items;
      }),
    ]);
  } catch (e) {
    loadError.value = errorText(e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
function selectProduct(event: Event) {
  product.select((event.target as HTMLSelectElement).value);
  void router.replace({
    query: {
      ...route.query,
      planId: product.id || undefined,
      modelId: undefined,
    },
  });
}
function workbench() {
  devices.selected = deviceId.value;
  if (props.inline) {
    emit("started");
    return Promise.resolve();
  }
  return router.push({ name: "workbench" });
}
async function refreshDevice() {
  busy.value = true;
  error.value = "";
  try {
    await devices.snapshot();
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function apply() {
  if (issue.value || loading.value || busy.value) return;
  if (unchanged.value && state.value?.production) {
    await workbench();
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await post(`/devices/${deviceId.value}/product`, {
      planId: product.id,
      ...(modelId.value ? { modelId: modelId.value } : {}),
      confirm: true,
      start: true,
    });
    devices.selected = deviceId.value;
    await devices.snapshot();
    await workbench();
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="application-panel" aria-label="检测准备">
    <form @submit.prevent="apply">
      <fieldset :disabled="busy || loading">
        <div class="setup-grid">
          <section class="setup-section">
            <label for="inspection-product">要检测什么产品？</label>
            <UiSelect
              id="inspection-product"
              :model-value="product.id"
              size="lg"
              block
              @change="selectProduct"
            >
              <option value="">选择产品</option>
              <option
                v-for="plan in product.plans"
                :key="plan.id"
                :value="plan.id"
              >
                {{ plan.rules.product }} · V{{ plan.version }}
              </option>
            </UiSelect>
            <template v-if="product.current">
              <div class="section-caption">
                <span>本次合格规则</span
                ><RouterLink :to="editProduct">{{
                  auth.admin ? "修改规则" : "查看规则"
                }}</RouterLink>
              </div>
              <ul class="rule-list">
                <li v-for="rule in rules" :key="rule.name">
                  <span>{{ rule.name }}</span
                  ><b>{{ rule.quantity }}</b>
                </li>
              </ul>
            </template>
          </section>
          <section class="setup-section device-section">
            <label for="inspection-device">{{
              inline ? "当前检测设备" : "在哪台设备上检测？"
            }}</label>
            <p v-if="inline" class="device-name">
              {{ device?.name || "尚未选择" }}
            </p>
            <UiSelect
              v-else
              id="inspection-device"
              v-model="deviceId"
              size="lg"
              block
              @change="devices.selected = deviceId"
            >
              <option value="">选择设备</option>
              <option v-for="item in targets" :key="item.id" :value="item.id">
                {{ item.name
                }}{{ item.connectionState !== "ONLINE" ? " · 未连接" : "" }}
              </option>
            </UiSelect>
            <div class="device-now">
              <span class="section-caption">设备当前状态</span>
              <strong
                ><i :class="{ online }" />{{
                  !online ? "未连接" : state?.production ? "正在检测" : "已停止"
                }}</strong
              >
              <p v-if="state?.product">
                {{ online ? "当前产品" : "上次产品" }}：{{
                  state.product.product || state.product.name
                }}
                · V{{ state.product.version }}
              </p>
              <p v-else>设备还未设置产品</p>
              <p
                v-if="product.current && !unchanged && online"
                class="selection-note"
              >
                上方选择的是即将检测的产品，点击开始后才会切换。
              </p>
            </div>
          </section>
        </div>
        <details class="model-options" :open="issue?.kind === 'model'">
          <summary>
            识别模型：{{ selectedModel?.version || "尚未匹配"
            }}<span>{{
              compatibleCurrent && !modelId
                ? "沿用设备现有模型 · 可更换"
                : "查看或更换"
            }}</span>
          </summary>
          <p>模型负责识别画面中的对象，产品规则负责判断数量、缺件和异常。</p>
          <label for="inspection-model">使用模型</label>
          <UiSelect id="inspection-model" v-model="modelId" block>
            <option v-if="compatibleCurrent" value="">
              沿用当前模型 · {{ state?.model?.version }}
            </option>
            <option v-else value="" disabled>选择兼容模型</option>
            <option
              v-for="model in compatibleModels"
              :key="model.id"
              :value="model.id"
            >
              {{ model.name }} · {{ model.version }}
            </option>
          </UiSelect>
        </details>
        <div v-if="issue" class="next-action needs-attention" role="status">
          <div>
            <h2>{{ issue.title }}</h2>
            <p>{{ issue.detail }}</p>
            <p
              v-if="issue.kind === 'rules' && rules.length >= 6"
              class="capacity-note"
            >
              当前 6
              个类别已占满。请为产品主体留出一个类别，调整后需使用对应模型。
            </p>
          </div>
          <UiButton
            v-if="issue.to"
            variant="primary"
            :to="issue.to"
            @click="issue.kind === 'pending' && (devices.selected = deviceId)"
            >{{ issue.action }}</UiButton
          >
          <UiButton
            v-else
            variant="primary"
            :disabled="busy"
            @click="issue.kind === 'load' ? load() : refreshDevice()"
            >{{ issue.action }}</UiButton
          >
        </div>
        <div v-else class="next-action" :aria-busy="busy || loading">
          <p>{{ loading ? "正在读取产品、设备和模型配置…" : consequence }}</p>
          <UiButton
            variant="primary"
            type="submit"
            :disabled="busy || loading"
            :loading="busy"
            >{{ actionLabel }}</UiButton
          >
        </div>
        <UiButton
          v-if="inline"
          variant="ghost"
          class="cancel-setup"
          :disabled="busy || loading"
          @click="emit('cancel')"
          >取消</UiButton
        >
      </fieldset>
    </form>
    <p v-if="error" class="error-box" role="alert">
      {{ error }}。请核对设备当前状态，已生效的配置会保留。<RouterLink
        :to="{ name: 'workbench' }"
        @click="devices.selected = deviceId"
        >查看现场状态</RouterLink
      >
    </p>
  </section>
</template>
<style scoped>
.application-panel {
  max-width: 1120px;
  padding: 28px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
  margin-bottom: 24px;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.setup-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 36px;
}
.setup-section {
  min-width: 0;
}
.device-name {
  font-size: 16px;
  font-weight: 600;
  padding: 11px 0;
}
.cancel-setup {
  margin-top: 10px;
}
.setup-section > label {
  display: block;
  font-size: 18px;
  font-weight: 650;
  margin-bottom: 12px;
}
.setup-section .ui-select {
  width: 100%;
}
.section-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--muted);
  margin: 20px 0 10px;
}
.rule-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.rule-list li {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
  font-size: 14px;
}
.rule-list b {
  font-weight: 500;
}
.device-section {
  border-left: 1px solid var(--line);
  padding-left: 36px;
}
.device-now strong {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
}
.device-now i {
  width: 8px;
  height: 8px;
  background: var(--muted);
  border-radius: 50%;
}
.device-now i.online {
  background: var(--green);
}
p {
  line-height: 1.75;
  margin: 8px 0;
  font-size: 14px;
}
.selection-note {
  color: var(--muted);
}
.model-options {
  border-top: 1px solid var(--line);
  margin-top: 24px;
  padding-top: 16px;
  font-size: 13px;
}
summary {
  cursor: pointer;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
summary span {
  color: var(--muted);
  margin-left: 12px;
}
.model-options select {
  display: block;
  max-width: 560px;
  margin-top: 6px;
}
.next-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-radius: 10px;
  padding: 18px 20px;
  margin-top: 22px;
  background: var(--surface-2);
}
.next-action p {
  margin: 0;
}
.next-action :deep(.ui-button) {
  flex-shrink: 0;
}
.needs-attention {
  background: var(--warn-bg);
  border: 1px solid var(--warn-line);
}
h2 {
  font-size: 17px;
  margin: 0 0 7px;
}
.capacity-note {
  margin-top: 7px !important;
  color: var(--muted);
}
@media (max-width: 760px) {
  .application-panel {
    padding: 20px;
  }
  .setup-grid {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .device-section {
    border-left: 0;
    border-top: 1px solid var(--line);
    padding: 24px 0 0;
  }
  .next-action {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
