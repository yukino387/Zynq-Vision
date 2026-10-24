<script setup lang="ts">
import InfoFields from "../components/InfoFields.vue";
import { chinese, displayName } from "@vision/shared";
import { ref, computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { InspectionPlan } from "@vision/contracts";
import type { Named, Dataset, Model } from "../types";
import type { TrainingOptions } from "@vision/contracts";
import { useAuthStore } from "../stores/auth";
import { useList } from "../composables/useList";
import { api, post, download } from "../api";
import { useDeviceStore } from "../stores/devices";
import { useNotificationStore } from "../stores/notifications";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import SortableTh from "../components/SortableTh.vue";
import Pager from "../components/Pager.vue";
import Drawer from "../components/Drawer.vue";
import ProductApplication from "../components/ProductApplication.vue";
import { useProductStore } from "../stores/product";
const workflow = useProductStore();

const canRollback = (id: unknown) =>
  devices.devices.some((d) => d.id === id && d.capabilities.modelUpdate);
const metricFps = (row: Named): number | null => {
  const value = (row.metrics as { fps?: unknown } | null)?.fps;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
};
const route = useRoute(),
  auth = useAuthStore(),
  router = useRouter(),
  devices = useDeviceStore(),
  notices = useNotificationStore();
const tab = computed(() =>
  String(route.params.tab || route.meta.defaultTab || "registry"),
);
const filterStatuses = computed(
  () =>
    ({
      registry: ["CANDIDATE", "APPROVED"],
      training: ["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"],
      deployments: [
        "DOWNLOADING",
        "VERIFYING",
        "VERIFIED",
        "ACTIVATING",
        "SELF_TEST",
        "ACTIVE",
        "SUPERSEDED",
        "FAILED",
        "ROLLED_BACK",
      ],
      benchmarks: ["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"],
    })[tab.value] ?? [],
);
const endpoint = computed(
    () =>
      ({
        registry: "/models",
        training: "/trainings",
        benchmarks: "/benchmarks",
        deployments: "/deployments",
      })[tab.value] ?? "/models",
  ),
  list = useList<Named>(endpoint);
list.realOnly.value = "true";
// 模型仓库默认只展示已批准版本；切换子页时恢复全部状态。
list.status.value = tab.value === "registry" ? "APPROVED" : "";
watch(
  tab,
  (t) => {
    list.status.value = t === "registry" ? "APPROVED" : "";
    list.filter();
  },
  { flush: "post" },
);
onMounted(() => {
  if (list.status.value) list.filter();
});
const form = ref(false),
  detail = ref<Named | null>(null),
  datasets = ref<Dataset[]>([]),
  models = ref<Model[]>([]),
  datasetId = ref(""),
  productId = ref(""),
  products = ref<InspectionPlan[]>([]),
  modelId = ref(""),
  deviceId = ref(""),
  name = ref(""),
  confirmDeploy = ref(false),
  busy = ref(false),
  importing = ref(false),
  importClasses = ref(""),
  file = ref<File | null>(null);
const trainingOptions = ref<TrainingOptions>({
  colorMode: "GRAY",
  epochs: 50,
  batchSize: 32,
  learningRate: 0.001,
  seed: 7020,
  device: "cuda",
  amp: true,
  workers: 4,
});
type Readiness = {
  planId: string;
  total: number;
  annotated: number;
  pending: number;
  excluded: number;
  minimum: number;
  ready: boolean;
  message: string;
};
const readiness = ref<Readiness | null>(null),
  readinessError = ref("");
watch(
  [() => tab.value, () => workflow.id],
  () => {
    if (tab.value === "training") productId.value = workflow.id;
  },
  { immediate: true },
);
watch(
  [productId, () => tab.value],
  async ([id, currentTab]) => {
    readiness.value = null;
    readinessError.value = "";
    if (currentTab !== "training" || !id) return;
    workflow.select(id);
    if (route.query.planId !== id)
      void router.replace({ query: { ...route.query, planId: id } });
    try {
      const result = await api<Readiness>(
        `/trainings/readiness?planId=${encodeURIComponent(id)}`,
      );
      if (productId.value === id && tab.value === "training")
        readiness.value = result;
    } catch (e) {
      if (productId.value === id)
        readinessError.value = e instanceof Error ? e.message : String(e);
    }
  },
  { immediate: true },
);
const approvalNote = ref("");
watch(
  () => detail.value?.id,
  () => {
    approvalNote.value = "";
  },
);
async function approveModel() {
  if (!detail.value) return;
  busy.value = true;
  try {
    await post(`/models/${detail.value.id}/approve`, {
      confirm: true,
      note: approvalNote.value.trim() || "管理员确认可用于生产",
    });
    detail.value = await api<Named>(`/models/${detail.value.id}`);
    await list.load();
    approvalNote.value = "";
    notices.add("模型已确认可用于生产，可在准备生产时选用");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
const chosenDataset = computed(() =>
  datasets.value.find((d) => d.id === datasetId.value),
);
const trainableDataset = (dataset: Dataset) => dataset._count.items >= 2;
const trainingBlocker = computed(() => {
  if (tab.value === "training")
    return !productId.value
      ? "先在上方选择准备训练的产品"
      : readinessError.value ||
          (!readiness.value
            ? "正在统计当前产品的训练图片…"
            : readiness.value.ready
              ? ""
              : readiness.value.message);
  if (productId.value) return "";
  const dataset = chosenDataset.value;
  if (!dataset) return "还没有真实数据集。先选择已标注图片并加入数据集。";
  if (dataset._count.items < 2)
    return `“${dataset.name}”当前有 ${dataset._count.items} 张样本，训练至少需要 2 张已标注样本。`;

  return "";
});
function trainingError(value: unknown) {
  const message = String(value ?? "");
  return message.includes("Frozen dataset checksum mismatch")
    ? "数据集快照校验失败，训练未开始。请用当前真实样本创建新版本并重新锁定。"
    : message;
}
const datasetSources = (dataset: Dataset) =>
  dataset.sourceCounts as Record<string, number>;
const datasetLabel = (dataset: Dataset) =>
  `${displayName(dataset.name)} / V${dataset.version} · ${dataset._count.items} 张${datasetSources(dataset)?.SIMULATION ? " · 含模拟样本" : "真实样本"}`;
const createdModel = (row: Named) =>
  (row.models as { id: string; version: string }[] | undefined)?.[0];
/** 表格与卡片里的模型引用：接口在评估、部署记录里都带了 model。 */
const rowModel = (row: Named) => row.model as Model | undefined;
/** 部署记录优先用接口带回的设备名，设备已删除时才回落到 ID。 */
const deviceName = (row: Named) =>
  (row.device as { name?: string } | undefined)?.name ??
  devices.devices.find((d) => d.id === row.deviceId)?.name ??
  text(row, "deviceId");
/** 阶段值来自训练脚本与板端协议，个别取值没有公共词条，在这里收口成中文。 */
const stageLabels: Record<string, string> = {
  QUEUE: "排队",
  TRAIN: "训练中",
  VALIDATE: "验证中",
  TRANSFER: "传输中",
  UPLOAD: "上传中",
  PACKAGE: "打包中",
  DONE: "已完成",
};
const stageText = (row: Named) =>
  stageLabels[text(row, "stage")] ?? chinese(text(row, "stage"));
const detailOptions = computed(
  () => detail.value?.options as TrainingOptions | undefined,
);
/** 详情抽屉只展示已格式化的值：时间、阶段、进度不再以原始字段形式出现。 */
const detailView = computed(() => {
  const row = detail.value;
  if (!row) return null;
  return {
    ...row,
    error: tab.value === "training" ? trainingError(row.error) : row.error,
    stage: stageText(row),
    progress: row.progress == null ? "进度未上报" : `${row.progress}%`,
  };
});
const detailFields = computed(() =>
  tab.value === "registry"
    ? ["name", "version", "error"]
    : ["name", "stage", "progress", "error"],
);
const text = (r: Named, k: string) =>
  r[k] == null
    ? ""
    : typeof r[k] === "object"
      ? JSON.stringify(r[k])
      : String(r[k]);
const trainingSummary = (row: Named) => {
  const options = row.options as Partial<TrainingOptions> | undefined;
  if (!options) return "";
  return `${options.device === "cuda" ? "CUDA GPU" : "CPU"} · 批大小 ${options.batchSize}${options.device === "cuda" && options.amp ? " · 混合精度" : ""}`;
};
/** 列表项是松散类型，收据里的 resident 表示这次是设备本地切换、没传字节。 */
const switchedLocally = (r: Named) =>
  Boolean((r.receipt as { resident?: boolean } | null)?.resident);
watch(
  () => devices.recent[0],
  (e) => {
    if (e && /training\.|deployment\.|job.failed/.test(e.type))
      void list.load();
  },
);
async function openForm() {
  try {
    if (tab.value === "training") {
      products.value = (
        await api<{ items: InspectionPlan[] }>("/plans?pageSize=100")
      ).items.filter((plan) => Array.isArray(plan.rules?.classes));
      productId.value = String(
        route.query.planId ??
          (workflow.id ||
            (products.value.length === 1 ? products.value[0]!.id : "")),
      );
    }
    if (tab.value !== "deployments" && tab.value !== "training")
      datasets.value = (
        await api<{ items: Dataset[] }>(
          tab.value === "training"
            ? "/datasets?realOnly=true&pageSize=100"
            : "/datasets?realOnly=true&pageSize=100",
        )
      ).items;
    if (tab.value !== "training")
      models.value = (
        await api<{ items: Model[] }>(
          tab.value === "deployments"
            ? "/models?status=APPROVED&realOnly=true&pageSize=100"
            : "/models?realOnly=true&pageSize=100",
        )
      ).items;
    const requested = String(route.query.datasetId ?? "");
    if (requested)
      datasetId.value = datasets.value.some((d) => d.id === requested)
        ? requested
        : "";
    else if (!datasets.value.some((d) => d.id === datasetId.value))
      datasetId.value =
        tab.value === "training"
          ? (datasets.value.find(trainableDataset)?.id ??
            datasets.value[0]?.id ??
            "")
          : "";
    if (!name.value) name.value = `现场模型 ${new Date().toLocaleDateString()}`;
    deviceId.value = devices.current?.id ?? "";
    form.value = true;
  } catch (e) {
    notices.error(e);
  }
}
function closeForm() {
  form.value = false;
  if (route.query.create) {
    const query = { ...route.query };
    delete query.create;
    void router.replace({ query });
  }
}
async function create() {
  if (tab.value === "training" && trainingBlocker.value) {
    notices.add(trainingBlocker.value, true);
    return;
  }
  busy.value = true;
  try {
    const body =
      tab.value === "training"
        ? {
            name: name.value,
            ...(productId.value
              ? { planId: productId.value }
              : { datasetId: datasetId.value }),
            options: trainingOptions.value,
          }
        : tab.value === "benchmarks"
          ? {
              name: name.value,
              modelId: modelId.value,
              datasetId: datasetId.value,
              deviceId: deviceId.value,
            }
          : {
              deviceId: deviceId.value,
              modelId: modelId.value,
              confirm: confirmDeploy.value,
            };
    await post(endpoint.value, body);
    await list.load();
    closeForm();
    notices.add("任务已提交");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function action(id: string, type: string) {
  busy.value = true;
  try {
    await post(
      `${endpoint.value}/${id}/${type}`,
      type === "rollback" ? { confirm: true } : undefined,
    );
    await list.load();
    notices.add("操作已完成");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function open(row: Named) {
  try {
    detail.value =
      tab.value === "registry" ? await api<Named>(`/models/${row.id}`) : row;
  } catch (e) {
    notices.error(e);
  }
}
async function importModel() {
  if (!file.value) return;
  busy.value = true;
  try {
    const data = new FormData();
    data.append("name", name.value);
    const classes = importClasses.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (classes.length) data.append("classes", JSON.stringify(classes));
    data.append("file", file.value);
    await api("/models/import", { method: "POST", body: data });
    importing.value = false;
    await list.load();
    notices.add("制品校验通过，模型已导入");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
watch(
  () => [
    tab.value,
    route.query.create,
    route.query.datasetId,
    route.query.modelId,
  ],
  async () => {
    form.value = false;
    detail.value = null;
    try {
      if (route.query.create === "1" && tab.value !== "deployments")
        await openForm();
      if (tab.value === "registry" && typeof route.query.modelId === "string")
        detail.value = await api<Named>(`/models/${route.query.modelId}`);
    } catch (error) {
      notices.error(error);
    }
  },
  { immediate: true },
);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>
        {{
          route.meta.tabs?.find((t) => t.tab === tab)?.label ?? route.meta.title
        }}
      </h1>
      <p>
        {{
          tab === "training"
            ? "选择产品，使用已完成标注的图片训练，数据版本自动留存。"
            : tab === "registry"
              ? "查看模型效果、下载模型包，并由管理员批准发布。"
              : tab === "deployments"
                ? "选择要检测的产品和设备。开始后，实时画面与计件结果会显示在现场工作台。"
                : "评估候选模型，确认效果后再发布到设备。"
        }}
      </p>
    </div>
    <div class="heading-actions">
      <button v-if="tab === 'registry'" @click="importing = true">
        导入模型制品</button
      ><button
        v-else-if="tab !== 'deployments'"
        class="primary"
        :disabled="tab === 'training' && !!trainingBlocker"
        @click="openForm"
      >
        {{
          tab === "training"
            ? "创建训练"
            : tab === "benchmarks"
              ? "创建评估"
              : "创建部署"
        }}
      </button>
    </div>
  </div>
  <ProductApplication v-if="tab === 'deployments'" />
  <section v-if="tab === 'training'" class="lab-banner experiment-banner">
    <div>
      <span class="workspace-index"
        >当前产品 · {{ workflow.current?.rules.product || "尚未选择" }}</span
      >
      <h2>
        {{ readiness?.ready ? "图片已就绪，可以创建训练" : "先准备训练图片" }}
      </h2>
      <p class="banner-note">
        {{ trainingBlocker || readiness?.message }}
        <RouterLink
          :to="{
            name: 'data',
            params: { tab: 'annotation' },
            query: { planId: productId || undefined },
          }"
          >为此产品补充标注</RouterLink
        >
        <span
          >训练使用已完成标注、未弃用的真实图片；提交时自动固定本次图片版本。</span
        >
      </p>
      <p v-if="readiness">
        真实图片 {{ readiness.total }} 张 · 可训练 {{ readiness.annotated }} 张
        · 待标注 {{ readiness.pending }} 张 · 已弃用/待补充
        {{ readiness.excluded }} 张
      </p>
    </div>
    <div class="experiment-register">
      <span
        >运行中
        <b>{{
          list.items.value.filter((r) => r.status === "RUNNING").length
        }}</b></span
      ><span
        >排队中
        <b>{{
          list.items.value.filter((r) => r.status === "QUEUED").length
        }}</b></span
      ><small>本页任务</small>
    </div>
  </section>
  <section v-else-if="tab === 'benchmarks'" class="benchmark-scope">
    <div>
      <h2>性能对照</h2>
    </div>
    <div class="benchmark-scale">
      <span>吞吐 / FPS</span>
      <div
        v-for="r in list.items.value.slice(0, 5)"
        :key="r.id"
        class="benchmark-track"
      >
        <span>{{ displayName(r.name) }}</span
        ><meter
          v-if="metricFps(r) !== null"
          min="0"
          :max="
            Math.max(30, ...list.items.value.map((row) => metricFps(row) ?? 0))
          "
          :value="metricFps(r) ?? 0"
          :aria-label="`${displayName(r.name)} 帧率`"
        /><span v-else class="muted">未上报</span
        ><b class="mono">{{ metricFps(r)?.toFixed(2) ?? "未测量" }}</b>
      </div>
      <small v-if="!list.items.value.length" class="muted"
        >评估完成后显示实际指标</small
      >
    </div>
  </section>
  <component
    :is="tab === 'deployments' ? 'details' : 'div'"
    :class="{ 'model-history': tab === 'deployments' }"
  >
    <summary v-if="tab === 'deployments'">
      模型更新记录 · {{ list.total.value }} 条
    </summary>
    <p v-if="tab === 'deployments'" class="note">
      这里只记录模型更新。生产批次和检测结果请在侧栏对应页面查看。
    </p>
    <form class="toolbar" @submit.prevent="list.filter">
      <input
        v-model="list.search.value"
        placeholder="搜索模型或任务…"
      /><UiSelect v-model="list.status.value">
        <option value="">全部状态</option>
        <option v-for="s in filterStatuses" :key="s" :value="s">
          {{ chinese(s) }}
        </option></UiSelect
      ><button
        :class="{ busy: list.loading.value }"
        :disabled="list.loading.value"
      >
        筛选</button
      ><button
        type="button"
        :class="{ busy: list.loading.value }"
        :disabled="list.loading.value"
        @click="list.load"
      >
        刷新</button
      ><template v-if="['training', 'deployments'].includes(tab)"
        ><UiSelect
          v-model="list.sort.value"
          aria-label="排序字段"
          @change="list.filter"
        >
          <option value="createdAt">创建时间</option>
          <option value="name">名称</option></UiSelect
        ><UiSelect
          v-model="list.order.value"
          aria-label="排序方向"
          @change="list.filter"
        >
          <option value="desc">降序</option>
          <option value="asc">升序</option>
        </UiSelect></template
      ><span class="right inline-count">{{ list.total.value }} 条记录</span>
    </form>
    <AsyncState
      :loading="list.loading.value"
      :error="list.error.value"
      :empty="!list.items.value.length"
      :hint="
        tab === 'training'
          ? '还没有训练任务。为产品准备至少两张完成标注的图片，即可创建训练。'
          : tab === 'deployments'
            ? '还没有应用记录。在上方选择产品、兼容模型与设备后应用。'
            : '这里还是空的。训练完成后可在模型仓库查看并下载模型。'
      "
      @retry="list.load"
      ><details
        v-if="tab === 'training'"
        class="experiment-log"
        aria-label="训练实验记录"
        :open="
          list.items.value.some((row) =>
            ['QUEUED', 'RUNNING'].includes(row.status ?? ''),
          )
        "
      >
        <summary>
          训练任务记录 ·
          {{ list.total.value }} 条（展开查看历史成功、失败及日志）
        </summary>
        <article
          v-for="r in list.items.value"
          :key="r.id"
          class="experiment-entry"
        >
          <div class="experiment-time">
            <time>{{ new Date(r.createdAt).toLocaleDateString() }}</time
            ><small class="mono">{{
              new Date(r.createdAt).toLocaleTimeString()
            }}</small>
          </div>
          <div class="experiment-body">
            <div class="experiment-entry-head">
              <h3>{{ displayName(r.name) }}</h3>
              <Status :value="r.status" />
            </div>
            <div class="experiment-source">
              <span
                class="tag"
                :class="{ simulated: r.source === 'SIMULATION' }"
                >{{ r.options ? "本地训练" : chinese(r.source) }}</span
              ><span>{{ stageText(r) }}</span>
              <span v-if="r.options">{{ trainingSummary(r) }}</span>
              <span v-if="r.dataset"
                >数据集：{{ displayName((r.dataset as Dataset).name) }} / V{{
                  (r.dataset as Dataset).version
                }}</span
              >
            </div>
            <div class="experiment-progress">
              <UiProgress
                :value="r.progress"
                style="height: 4px; flex: 1; max-width: 400px"
              />
              <span class="mono">{{
                r.progress == null ? "进度未上报" : `${r.progress}%`
              }}</span>
            </div>
            <p v-if="r.error" class="tone-crit">{{ trainingError(r.error) }}</p>
          </div>
          <div class="experiment-actions">
            <RouterLink
              v-if="createdModel(r)"
              class="button-link"
              :to="{
                name: 'models',
                params: { tab: 'registry' },
                query: { modelId: createdModel(r)!.id },
              }"
              >查看模型</RouterLink
            >
            <button class="table-action" @click="open(r)">实验详情</button
            ><button
              v-if="['QUEUED', 'RUNNING'].includes(r.status ?? '')"
              @click="action(r.id, 'cancel')"
              :disabled="busy"
              class="table-action danger"
            >
              取消任务
            </button>
          </div>
        </article>
      </details>
      <section
        v-else-if="tab === 'deployments'"
        class="deployment-console"
        aria-label="模型更新记录"
      >
        <article
          v-for="r in list.items.value"
          :key="r.id"
          class="deployment-entry"
        >
          <header>
            <div>
              <h3>{{ displayName(r.name) }}</h3>
            </div>
            <Status chip :value="r.status" />
          </header>
          <div class="deployment-route">
            <div>
              <small>当前目标</small
              ><b>{{ displayName(rowModel(r)?.name ?? text(r, "modelId")) }}</b
              ><span class="mono">{{
                rowModel(r)?.version ?? "版本未提供"
              }}</span>
            </div>
            <span class="deployment-arrow">→</span>
            <div>
              <small>接收设备</small><b>{{ displayName(deviceName(r)) }}</b
              ><span class="mono">{{
                r.previousVersion
                  ? `前序版本 ${r.previousVersion}`
                  : "无前序版本"
              }}</span>
            </div>
          </div>
          <div class="deployment-progress">
            <Status :value="r.status" /><span>{{ stageText(r) }}</span>
            <UiProgress :value="r.progress" style="height: 4px; flex: 1" />
            <b class="mono">{{
              r.progress == null ? "进度未上报" : `${r.progress}%`
            }}</b>
          </div>
          <p v-if="r.error" class="error-box">{{ r.error }}</p>
          <footer>
            <span
              class="tag"
              :class="{ simulated: r.source === 'SIMULATION' }"
              >{{ chinese(r.source) }}</span
            ><span v-if="switchedLocally(r)" class="tag">本地切换</span
            ><time class="mono">{{
              new Date(r.createdAt).toLocaleString()
            }}</time>
            <div class="deployment-actions">
              <button @click="open(r)">执行证据</button
              ><button
                v-if="
                  canRollback(r.deviceId) &&
                  r.previousVersion &&
                  ['ACTIVE', 'FAILED'].includes(r.status ?? '')
                "
                :disabled="busy"
                @click="action(r.id, 'rollback')"
                class="danger"
              >
                回滚版本
              </button>
            </div>
          </footer>
        </article>
      </section>
      <div v-else class="panel table-wrap">
        <table>
          <thead>
            <tr>
              <!-- 四个 tab 的接口白名单都允许 name 与 createdAt，这两列可以安全排序 -->
              <SortableTh
                field="name"
                label="名称 / 版本"
                :active="list.sort.value"
                :order="list.order.value"
                @sort="list.sortBy"
              />
              <th>{{ tab === "benchmarks" ? "评估模型" : "生成方式" }}</th>
              <th>{{ tab === "benchmarks" ? "指标" : "状态" }}</th>
              <th>{{ tab === "registry" ? "指标" : "进度" }}</th>
              <SortableTh
                field="createdAt"
                label="时间"
                :active="list.sort.value"
                :order="list.order.value"
                @sort="list.sortBy"
              />
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in list.items.value" :key="r.id">
              <td>
                <strong>{{ displayName(r.name) }}</strong
                ><small class="mono">{{ r.version ?? "版本未提供" }}</small>
              </td>
              <td v-if="tab === 'benchmarks'">
                <strong>{{
                  displayName(rowModel(r)?.name ?? "未关联模型")
                }}</strong
                ><small class="mono">{{
                  rowModel(r)?.version ?? "版本未提供"
                }}</small>
              </td>
              <td v-else>
                <span
                  class="tag"
                  :class="{ simulated: r.source === 'SIMULATION' }"
                  >{{
                    r.trainingId
                      ? "训练生成"
                      : r.source === "SIMULATION"
                        ? "模拟"
                        : "导入"
                  }}</span
                >
              </td>
              <td v-if="tab === 'benchmarks'">
                <div class="cell-metrics">
                  <InfoFields
                    :value="r.metrics"
                    :fields="['fps', 'inferenceUs']"
                  />
                </div>
              </td>
              <td v-else>
                <Status :value="r.status" /><small v-if="tab !== 'registry'">{{
                  stageText(r)
                }}</small
                ><small style="color: var(--red)">{{ text(r, "error") }}</small>
              </td>
              <td v-if="tab === 'registry'">
                <div v-if="r.trainingId" class="cell-metrics">
                  <InfoFields
                    :value="r.metrics"
                    :fields="['mAP50', 'precision', 'recall']"
                  />
                </div>
                <span v-else class="muted">—</span>
              </td>
              <td v-else>
                <span class="mono">{{
                  r.progress == null ? "进度未上报" : r.progress + "%"
                }}</span>
                <UiProgress
                  v-if="r.progress !== undefined"
                  :value="r.progress"
                  style="width: 95px; height: 4px; margin-top: 7px"
                />
              </td>
              <td>{{ new Date(r.createdAt).toLocaleString() }}</td>
              <td class="action-cell">
                <div class="row-actions">
                  <button @click="open(r)" class="table-action">详情</button
                  ><button
                    v-if="
                      tab === 'training' &&
                      ['QUEUED', 'RUNNING'].includes(r.status ?? '')
                    "
                    @click="action(r.id, 'cancel')"
                    class="table-action danger"
                    :disabled="busy"
                  >
                    取消</button
                  ><button
                    v-if="
                      tab === 'deployments' &&
                      canRollback(r.deviceId) &&
                      r.previousVersion &&
                      ['ACTIVE', 'FAILED'].includes(r.status ?? '')
                    "
                    @click="action(r.id, 'rollback')"
                    class="table-action danger"
                    :disabled="busy"
                  >
                    回滚</button
                  ><button
                    v-if="tab === 'registry'"
                    @click="
                      download(
                        `/models/${r.id}/export`,
                        `model-${r.id}.zip`,
                        'POST',
                      ).catch(notices.error)
                    "
                    class="table-action"
                  >
                    导出
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div></AsyncState
    >
    <Pager
      :page="list.page.value"
      :total="list.total.value"
      :page-size="list.pageSize.value"
      @update:page="
        (p) => {
          list.page.value = p;
          list.load();
        }
      "
      @update:page-size="list.setPageSize"
    />
  </component>
  <Drawer
    v-if="form && tab !== 'deployments'"
    :title="
      tab === 'training'
        ? '创建训练'
        : tab === 'benchmarks'
          ? '创建模型评估'
          : '部署模型'
    "
    @close="closeForm"
    ><form @submit.prevent="create">
      <label v-if="tab !== 'deployments'"
        >任务名称<input v-model="name" required /></label
      ><label v-if="tab === 'training'"
        >训练产品<UiSelect v-model="productId" required>
          <option value="" disabled>选择产品</option>
          <option v-for="p in products" :key="p.id" :value="p.id">
            {{ p.rules.product }} · V{{ p.version }}
          </option>
        </UiSelect></label
      >
      <p v-if="tab === 'training'" class="note">
        使用该产品已完成标注、未弃用的真实图片，自动生成本次训练的数据版本。
      </p>
      <label v-if="tab !== 'deployments' && tab !== 'training'"
        >{{ tab === "training" ? "训练数据集" : "评估数据集"
        }}<UiSelect v-model="datasetId" required>
          <option value="">选择数据集</option>
          <option v-for="d in datasets" :key="d.id" :value="d.id">
            {{ datasetLabel(d)
            }}{{
              tab === "training"
                ? trainableDataset(d)
                  ? " · 可训练"
                  : d._count.items < 2
                    ? " · 样本不足"
                    : " · 待审核并锁定"
                : ""
            }}
          </option>
        </UiSelect></label
      >
      <p v-if="tab === 'training' && trainingBlocker" class="note">
        {{ trainingBlocker }}
      </p>
      <template v-if="tab === 'training'">
        <fieldset class="training-modes">
          <legend>输入模式</legend>
          <label :class="{ active: trainingOptions.colorMode === 'GRAY' }"
            ><input
              type="radio"
              value="GRAY"
              v-model="trainingOptions.colorMode"
            /><b>灰度</b><small>使用明暗与纹理信息</small></label
          ><label :class="{ active: trainingOptions.colorMode === 'RGB' }"
            ><input
              type="radio"
              value="RGB"
              v-model="trainingOptions.colorMode"
            /><b>彩色 RGB</b><small>保留颜色，需板端支持 RGB</small></label
          >
        </fieldset>
        <label
          >训练轮数<input
            v-model.number="trainingOptions.epochs"
            type="number"
            min="1"
            max="1000"
            required
        /></label>
        <div class="training-presets">
          <span>常用轮数</span
          ><button
            v-for="epochs in [5, 50, 100]"
            :key="epochs"
            type="button"
            :aria-pressed="trainingOptions.epochs === epochs"
            @click="trainingOptions.epochs = epochs"
          >
            {{ epochs === 5 ? "5 轮 · 流程检查" : `${epochs} 轮` }}
          </button>
        </div>
        <details class="training-advanced">
          <summary>
            高级训练参数
            <span
              >{{ trainingOptions.device === "cuda" ? "CUDA GPU" : "CPU" }} ·
              批大小 {{ trainingOptions.batchSize }}</span
            >
          </summary>
          <label
            >批大小<input
              v-model.number="trainingOptions.batchSize"
              type="number"
              min="1"
              max="32"
              required
          /></label>
          <label
            >学习率<input
              v-model.number="trainingOptions.learningRate"
              type="number"
              min="0.000001"
              max="0.1"
              step="any"
              required
          /></label>
          <label
            >随机种子<input
              v-model.number="trainingOptions.seed"
              type="number"
              min="0"
              max="2147483647"
              required
          /></label>
          <label
            >计算设备<UiSelect v-model="trainingOptions.device">
              <option value="cuda">CUDA GPU</option>
              <option value="cpu">CPU（调试）</option>
            </UiSelect></label
          >
          <UiSwitch
            v-if="trainingOptions.device === 'cuda'"
            v-model="trainingOptions.amp"
            label="混合精度训练"
          />
          <label
            >数据加载进程<input
              v-model.number="trainingOptions.workers"
              type="number"
              min="0"
              max="8"
              required
          /></label>
        </details>
        <p class="note">
          使用已完成标注的真实数据，类别沿用产品配置，当前硬件模板最多支持六类。没有验证集时按种子划分
          20%
          留出验证，至少需要两张样本。训练完成后可下载模型包、训练记录和检查点。
        </p>
      </template>
      <label v-if="tab !== 'training'"
        >模型<UiSelect v-model="modelId" required>
          <option value="">选择模型</option>
          <option v-for="m in models" :key="m.id" :value="m.id">
            {{ displayName(m.name) }} / {{ m.version }} /
            {{ chinese(m.status) }}
          </option>
        </UiSelect></label
      >
      <p v-if="tab === 'deployments' && !models.length" class="note">
        还没有已批准的模型。请先由管理员在“模型仓库”批准发布。
      </p>
      <label v-if="tab !== 'training'"
        >设备<UiSelect v-model="deviceId" required>
          <option value="">选择设备</option>
          <option
            v-for="d in devices.devices"
            :key="d.id"
            :value="d.id"
            :disabled="!d.capabilities.modelUpdate"
          >
            {{ displayName(d.name) }}
            {{ !d.capabilities.modelUpdate ? "· 不支持模型更新" : "" }}
          </option>
        </UiSelect></label
      >
      <label v-if="tab === 'deployments'" class="confirm-line">
        <input v-model="confirmDeploy" type="checkbox" />
        设备正在生产或产品类别会变化时，确认停止当前生产、结束当前批次并重新开始
      </label>
      <p v-if="tab === 'deployments'" class="note">
        下发模型只更新设备模型，不会创建或切换批次；产品规则请在设备页单独分配。
      </p>
      <p v-else-if="tab !== 'training'" class="note">
        请选择兼容的模型、数据集和设备。
      </p>
      <button
        class="primary"
        :disabled="busy || (tab === 'training' && !!trainingBlocker)"
      >
        {{
          busy
            ? "正在提交…"
            : tab === "training"
              ? trainingOptions.device === "cuda"
                ? "开始 GPU 训练"
                : "开始 CPU 调试训练"
              : "提交任务"
        }}
      </button>
    </form></Drawer
  ><Drawer
    v-if="detail"
    :title="
      tab === 'training'
        ? '训练详情'
        : tab === 'registry'
          ? '模型详情'
          : '任务详情'
    "
    @close="detail = null"
  >
    <div class="detail-head">
      <Status chip :value="detail.status" />
      <span class="mono" :title="detail.id"
        >任务编号：{{ detail.id.slice(-10) }}</span
      >
      <time class="mono">{{
        new Date(detail.createdAt).toLocaleString()
      }}</time>
    </div>
    <div v-if="tab === 'registry' && detail.trainingId" class="detail-metrics">
      <InfoFields
        :value="detail.metrics"
        :fields="['mAP50', 'precision', 'recall', 'fps']"
      />
    </div>
    <RouterLink
      v-if="tab === 'registry' && detail.status === 'APPROVED'"
      class="button-link primary"
      :to="{
        name: 'models',
        params: { tab: 'deployments' },
        query: { modelId: detail.id, planId: workflow.id || undefined },
      }"
      >使用此模型开始检测</RouterLink
    >
    <section
      v-if="tab === 'registry' && detail.status !== 'APPROVED'"
      class="approval-gate"
    >
      <h3>确认用于生产</h3>
      <p>请先核查训练结果与现场样本效果，再确认此版本可用于生产。</p>
      <form v-if="auth.admin" @submit.prevent="approveModel">
        <label
          >验收说明（可选）<textarea
            v-model="approvalNote"
            maxlength="1000"
            rows="3"
            placeholder="记录已验证的产品、工位条件、效果及适用限制"
          />
        </label>
        <button class="primary" :disabled="busy">确认可用于生产</button>
      </form>
      <p v-else>请由管理员完成发布批准。</p>
    </section>
    <div v-if="detailOptions" class="training-detail">
      <span
        >输入模式<b>{{
          detailOptions.colorMode === "GRAY" ? "灰度" : "彩色 RGB"
        }}</b></span
      ><span
        >训练轮数<b>{{ detailOptions.epochs }} 轮</b></span
      ><span
        >计算设备<b>{{
          detailOptions.device === "cuda" ? "CUDA GPU" : "CPU"
        }}</b></span
      ><span
        >批大小<b>{{ detailOptions.batchSize }}</b></span
      >
    </div>
    <RouterLink
      v-if="createdModel(detail)"
      class="button-link primary"
      :to="{
        name: 'models',
        params: { tab: 'registry' },
        query: { modelId: createdModel(detail)!.id },
      }"
      >查看生成模型</RouterLink
    >
    <InfoFields :value="detailView" :fields="detailFields" />
    <details>
      <summary>技术详情</summary>
      <pre>{{ JSON.stringify(detail, null, 2) }}</pre>
    </details></Drawer
  ><Drawer v-if="importing" title="导入模型包" @close="importing = false"
    ><form @submit.prevent="importModel">
      <label>模型名称<input v-model="name" required /></label
      ><label
        >类别（最多 6 个，按训练时的顺序，逗号分隔；留空使用默认六类）<input
          v-model="importClasses"
          placeholder="例如：defect, unused_1, unused_2" /></label
      ><label
        >模型包（model.bin）<input
          type="file"
          @change="
            file = ($event.target as HTMLInputElement).files?.[0] ?? null
          "
          required
      /></label>
      <p class="note">
        系统会从 model.bin
        自动读取版本、输入通道、量化参数和整包哈希，并继续用固定图校验；不需要再填
        manifest。
      </p>
      <button class="primary" :disabled="busy">验证并导入</button>
    </form></Drawer
  >
</template>
<style scoped>
.model-history {
  max-width: 1120px;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 16px 20px;
  background: var(--surface);
}
.model-history > summary {
  cursor: pointer;
  color: var(--muted);
  font-size: 13px;
}
.terminal-model-guide {
  padding: 1rem;
  margin: 1rem 0;
}
.training-empty {
  padding: 16px 18px;
  margin: 16px 0;
  border: 1px solid var(--line);
  border-left: 3px solid var(--line-strong);
  background: var(--surface-2);
  font-size: 13px;
}
.training-empty b {
  display: block;
  margin-bottom: 6px;
}
.training-empty p {
  margin: 0 0 8px;
  color: var(--muted);
  line-height: 1.7;
}
.training-modes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 0;
  border: 0;
  margin: 20px 0;
}
.training-modes legend {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 10px;
}
.training-modes label {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--line);
  margin: 0;
  cursor: pointer;
}
.training-modes label.active {
  border-color: var(--forest);
  background: var(--surface-2);
}
.training-modes small {
  grid-column: 1/-1;
  font-size: 11px;
  line-height: 1.6;
  color: var(--muted);
}
.training-modes input {
  width: auto;
}
.training-presets {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--muted);
  margin: -6px 0 20px;
}
.training-presets button {
  font-size: 11px;
  padding: 6px 9px;
}
.training-presets button[aria-pressed="true"] {
  border-color: var(--forest);
  color: var(--forest);
}
.training-advanced {
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: 15px 0;
  margin: 20px 0;
}
.training-advanced summary {
  font-size: 13px;
  cursor: pointer;
  margin-bottom: 12px;
}
.training-advanced summary span {
  display: block;
  font-size: 11px;
  color: var(--muted);
  margin: 8px 0 0 16px;
}
.training-detail {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin: 20px 0 26px;
}
.training-detail span {
  font-size: 12px;
  color: var(--muted);
}
.training-detail b {
  display: block;
  font-size: 16px;
  color: var(--ink);
  margin-top: 8px;
}
/* 表格里的指标：三行带分隔线的字段列表会把行高撑到 100px 以上，
   收成「标签 + 数值」的紧凑两列，行高回到与其他单元格一致。 */
.cell-metrics .detail-fields,
.detail-metrics .detail-fields {
  grid-template-columns: auto auto;
  justify-content: start;
  column-gap: 14px;
  row-gap: 3px;
}
.cell-metrics .detail-fields :deep(dt),
.cell-metrics .detail-fields :deep(dd),
.detail-metrics .detail-fields :deep(dt),
.detail-metrics .detail-fields :deep(dd) {
  border: 0;
  padding: 0;
  font-size: 11px;
  line-height: 1.7;
}
.cell-metrics .detail-fields :deep(dd),
.detail-metrics .detail-fields :deep(dd) {
  text-align: left;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
}
.detail-metrics {
  border: 1px solid var(--line);
  background: var(--surface-2);
  padding: 10px 14px;
  margin-bottom: 20px;
}
.detail-metrics .detail-fields :deep(dt),
.detail-metrics .detail-fields :deep(dd) {
  font-size: 12px;
  line-height: 1.9;
}
/* 详情抽屉的字段列表：值跟标签就近成对，不再被右对齐甩到对面边缘。 */
.detail-fields {
  grid-template-columns: minmax(96px, 0.34fr) minmax(0, 1fr);
  column-gap: 16px;
}
.detail-fields :deep(dd) {
  text-align: left;
}
.detail-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding-bottom: 14px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--line);
  font-size: 10px;
  color: var(--muted);
}
.detail-head time {
  margin-left: auto;
}
.approval-gate {
  border: 1px solid var(--line);
  border-left: 3px solid var(--forest);
  background: var(--surface-2);
  padding: 16px 18px;
  margin-bottom: 20px;
}
.approval-gate h3 {
  margin: 0 0 8px;
}
.approval-gate p {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: var(--ink-2);
}
.approval-gate .approval-missing {
  margin-top: 6px;
  color: var(--muted);
}
.approval-gate form {
  margin-top: 14px;
  padding-top: 4px;
  border-top: 1px solid var(--line);
}
</style>
