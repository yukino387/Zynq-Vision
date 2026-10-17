<script setup lang="ts">
import InfoFields from "../components/InfoFields.vue";
import { chinese, displayName } from "@vision/shared";
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { Named, Dataset, Model } from "../types";
import type { TrainingOptions } from "@vision/contracts";
import { useList } from "../composables/useList";
import { api, post, download } from "../api";
import { useDeviceStore } from "../stores/devices";
import { useNotificationStore } from "../stores/notifications";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import SortableTh from "../components/SortableTh.vue";
import Pager from "../components/Pager.vue";
import Drawer from "../components/Drawer.vue";
const metricFps = (row: Named): number | null => {
  const value = (row.metrics as { fps?: unknown } | null)?.fps;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
};
const route = useRoute(),
  router = useRouter(),
  devices = useDeviceStore(),
  notices = useNotificationStore();
const tab = computed(() =>
  String(route.params.tab || route.meta.defaultTab || "registry"),
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
const form = ref(false),
  detail = ref<Named | null>(null),
  datasets = ref<Dataset[]>([]),
  models = ref<Model[]>([]),
  datasetId = ref(""),
  modelId = ref(""),
  deviceId = ref(""),
  name = ref(""),
  busy = ref(false),
  importing = ref(false),
  manifest = ref(""),
  version = ref(""),
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
const chosenDataset = computed(() =>
  datasets.value.find((d) => d.id === datasetId.value),
);
const datasetSources = (dataset: Dataset) =>
  dataset.sourceCounts as Record<string, number>;
const datasetLabel = (dataset: Dataset) =>
  `${displayName(dataset.name)} / V${dataset.version} · ${dataset._count.items} 张${datasetSources(dataset)?.SIMULATION ? " · 含模拟样本" : "真实样本"}`;
const createdModel = (row: Named) =>
  (row.models as { id: string; version: string }[] | undefined)?.[0];
const detailOptions = computed(
  () => detail.value?.options as TrainingOptions | undefined,
);
const text = (r: Named, k: string) =>
  typeof r[k] === "object" ? JSON.stringify(r[k]) : String(r[k] ?? "—");
const trainingSummary = (row: Named) => {
  const options = row.options as Partial<TrainingOptions> | undefined;
  if (!options) return "";
  return `${options.device === "cuda" ? "CUDA GPU" : "CPU"} · 批大小 ${options.batchSize}${options.device === "cuda" && options.amp ? " · 混合精度" : ""}`;
};
/** 列表项是松散类型，收据里的 resident 表示这次是设备本地切换、没传字节。 */
const switchedLocally = (r: Named) =>
  Boolean((r.receipt as { resident?: boolean } | null)?.resident);
/** 所选设备上已经有这个版本的模型：提交后只切换，不传字节。 */
const willSwitch = computed(() => {
  const version = models.value.find((m) => m.id === modelId.value)?.version;
  if (!version) return false;
  return Boolean(
    devices.devices
      .find((d) => d.id === deviceId.value)
      ?.reportedState.models?.some((m) => m.version === version),
  );
});
watch(
  () => devices.recent[0],
  (e) => {
    if (e && /training\.|deployment\.|job.failed/.test(e.type))
      void list.load();
  },
);
async function openForm() {
  try {
    if (tab.value !== "deployments")
      datasets.value = (
        await api<{ items: Dataset[] }>("/datasets?status=FROZEN&pageSize=100")
      ).items;
    if (tab.value !== "training")
      models.value = (
        await api<{ items: Model[] }>("/models?pageSize=100")
      ).items;
    const requested = String(route.query.datasetId ?? "");
    if (requested)
      datasetId.value = datasets.value.some((d) => d.id === requested)
        ? requested
        : "";
    else if (!datasets.value.some((d) => d.id === datasetId.value))
      datasetId.value = "";
    if (!name.value) name.value = `缺陷模型 ${new Date().toLocaleDateString()}`;
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
  busy.value = true;
  try {
    const body =
      tab.value === "training"
        ? {
            name: name.value,
            datasetId: datasetId.value,
            options: trainingOptions.value,
          }
        : tab.value === "benchmarks"
          ? {
              name: name.value,
              modelId: modelId.value,
              datasetId: datasetId.value,
              deviceId: deviceId.value,
            }
          : { deviceId: deviceId.value, modelId: modelId.value };
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
    await post(`${endpoint.value}/${id}/${type}`);
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
    data.append(
      "metadata",
      JSON.stringify({
        name: name.value,
        version: version.value,
        manifest: JSON.parse(manifest.value),
      }),
    );
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
      if (route.query.create === "1") await openForm();
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
            ? "选择已准备好的数据集，开始 GPU 训练；完成后可查看模型并评估。"
            : tab === "registry"
              ? "查看模型效果、下载模型包，并继续评估或部署。"
              : tab === "deployments"
                ? "将评估通过的模型发布到设备，部署后检查实际检测结果。"
                : "评估候选模型，确认效果后再发布到设备。"
        }}
      </p>
    </div>
    <div class="heading-actions">
      <button v-if="tab === 'registry'" @click="importing = true">
        导入模型制品</button
      ><button v-else class="primary" @click="openForm">
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
  <div v-if="tab === 'training'" class="panel" style="margin-bottom: 20px">
    <div class="panel-body">
      <span class="tag">GPU 训练</span>
      <p class="note" style="margin: 8px 0 0; padding: 0">
        先完成样本标注，再将数据集锁定为训练版本。训练完成后会自动生成模型包。
        <RouterLink to="/data/annotation">去标注</RouterLink> ·
        <RouterLink to="/data/datasets">查看数据集</RouterLink>
      </p>
    </div>
  </div>
  <section v-if="tab === 'training'" class="lab-banner experiment-banner">
    <div>
      <span class="workspace-index">06 / 实验工作区</span>
      <h2>训练实验</h2>
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
  <section v-else-if="tab === 'deployments'" class="deployment-flow">
    <div
      v-for="(step, index) in [
        { label: '待执行', states: ['APPROVED'] },
        {
          label: '正在部署',
          states: [
            'DOWNLOADING',
            'VERIFYING',
            'VERIFIED',
            'ACTIVATING',
            'SELF_TEST',
            'ROLLBACK',
          ],
        },
        { label: '已生效', states: ['ACTIVE', 'SUPERSEDED'] },
        { label: '需处理', states: ['FAILED', 'ROLLED_BACK'] },
      ]"
      :key="step.label"
    >
      <small class="mono">0{{ index + 1 }}</small
      ><span>{{ step.label }}</span
      ><b class="mono">{{
        list.items.value.filter((r) =>
          step.states.some((state) => state === r.status),
        ).length
      }}</b>
    </div>
    <small class="flow-caption">本页部署状态</small>
  </section>
  <section v-else-if="tab === 'benchmarks'" class="benchmark-scope">
    <div>
      <span class="workspace-index">07 / 性能实验室</span>
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
        ><b class="mono">{{ metricFps(r)?.toFixed(2) ?? "—" }}</b>
      </div>
      <small v-if="!list.items.value.length" class="muted"
        >评估完成后显示实际指标</small
      >
    </div>
  </section>
  <form class="toolbar" @submit.prevent="list.filter">
    <input v-model="list.search.value" placeholder="搜索模型或任务…" /><select
      v-model="list.status.value"
    >
      <option value="">全部状态</option>
      <option
        v-for="s in [
          'CANDIDATE',
          'APPROVED',
          'QUEUED',
          'RUNNING',
          'COMPLETED',
          'FAILED',
          'ACTIVE',
          'ROLLED_BACK',
        ]"
        :key="s"
        :value="s"
      >
        {{ chinese(s) }}
      </option></select
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
      ><select
        v-model="list.sort.value"
        aria-label="排序字段"
        @change="list.filter"
      >
        <option value="createdAt">创建时间</option>
        <option value="name">名称</option></select
      ><select
        v-model="list.order.value"
        aria-label="排序方向"
        @change="list.filter"
      >
        <option value="desc">降序</option>
        <option value="asc">升序</option>
      </select></template
    ><span class="right inline-count">{{ list.total.value }} 条记录</span>
  </form>
  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!list.items.value.length"
    :hint="
      tab === 'training'
        ? '还没有训练任务。先在数据管理里冻结一个数据集，再回到这里发起训练。'
        : tab === 'deployments'
          ? '还没有部署记录。模型通过评估后，用「创建部署」下发到设备。'
          : '这里还是空的。训练完成并评估通过的模型会出现在这里。'
    "
    @retry="list.load"
    ><section
      v-if="tab === 'training'"
      class="experiment-log"
      aria-label="训练实验记录"
    >
      <article
        v-for="(r, index) in list.items.value"
        :key="r.id"
        class="experiment-entry"
      >
        <div class="experiment-time">
          <span class="mono">{{
            String(
              (list.page.value - 1) * list.pageSize.value + index + 1,
            ).padStart(3, "0")
          }}</span
          ><time>{{ new Date(r.createdAt).toLocaleDateString() }}</time
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
            ><span class="mono">{{ r.id.slice(-10) }}</span
            ><span>{{ chinese(text(r, "stage")) }}</span>
            <span v-if="r.options">{{ trainingSummary(r) }}</span>
          </div>
          <div class="experiment-progress">
            <div class="bar">
              <span :style="{ width: `${r.progress ?? 0}%` }" />
            </div>
            <span class="mono">{{
              r.progress === undefined ? "—" : `${r.progress}%`
            }}</span>
          </div>
          <p v-if="r.error" class="tone-crit">{{ r.error }}</p>
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
            >查看生成模型 →</RouterLink
          >
          <button @click="open(r)">实验详情</button
          ><button
            v-if="['QUEUED', 'RUNNING'].includes(r.status ?? '')"
            @click="action(r.id, 'cancel')"
            :disabled="busy"
            class="danger"
          >
            取消任务
          </button>
        </div>
      </article>
    </section>
    <section
      v-else-if="tab === 'deployments'"
      class="deployment-console"
      aria-label="部署执行记录"
    >
      <article
        v-for="r in list.items.value"
        :key="r.id"
        class="deployment-entry"
      >
        <header>
          <div>
            <span class="mono">{{ r.id.slice(-10) }}</span>
            <h3>{{ displayName(r.name) }}</h3>
          </div>
          <Status chip :value="r.status" />
        </header>
        <div class="deployment-route">
          <div>
            <small>当前目标</small
            ><b>{{
              displayName(
                (r.model as Model | undefined)?.name ?? text(r, "modelId"),
              )
            }}</b
            ><span class="mono">{{
              (r.model as Model | undefined)?.version ?? "—"
            }}</span>
          </div>
          <span class="deployment-arrow">→</span>
          <div>
            <small>接收设备</small
            ><b>{{
              displayName(
                devices.devices.find((d) => d.id === r.deviceId)?.name ??
                  text(r, "deviceId"),
              )
            }}</b
            ><span class="mono">{{
              r.previousVersion ? `前序版本 ${r.previousVersion}` : "无前序版本"
            }}</span>
          </div>
        </div>
        <div class="deployment-progress">
          <Status :value="r.status" /><span>{{
            chinese(text(r, "stage"))
          }}</span>
          <div class="bar">
            <span :style="{ width: `${r.progress ?? 0}%` }" />
          </div>
          <b class="mono">{{
            r.progress === undefined ? "—" : `${r.progress}%`
          }}</b>
        </div>
        <p v-if="r.error" class="error-box">{{ r.error }}</p>
        <footer>
          <span class="tag" :class="{ simulated: r.source === 'SIMULATION' }">{{
            chinese(r.source)
          }}</span
          ><span v-if="switchedLocally(r)" class="tag">本地切换</span
          ><time class="mono">{{ new Date(r.createdAt).toLocaleString() }}</time
          ><button @click="open(r)">执行证据</button
          ><button
            v-if="
              r.previousVersion && ['ACTIVE', 'FAILED'].includes(r.status ?? '')
            "
            :disabled="busy"
            @click="action(r.id, 'rollback')"
            class="danger"
          >
            回滚版本
          </button>
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
            <th>来源</th>
            <th>{{ tab === "benchmarks" ? "指标" : "状态 / 阶段" }}</th>
            <th>{{ tab === "registry" ? "架构" : "进度" }}</th>
            <SortableTh
              field="createdAt"
              label="时间"
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in list.items.value" :key="r.id">
            <td>
              <strong>{{ displayName(r.name) }}</strong
              ><small class="mono">{{ r.version ?? r.id.slice(-10) }}</small>
            </td>
            <td>
              <span
                class="tag"
                :class="{ simulated: r.source === 'SIMULATION' }"
                >{{ r.trainingId ? "本地训练" : chinese(r.source) }}</span
              >
            </td>
            <td v-if="tab === 'benchmarks'">
              <InfoFields
                :value="r.metrics"
                :fields="['fps', 'inferenceUs', 'accuracy']"
              />
            </td>
            <td v-else>
              <Status :value="r.status" /><small>{{
                chinese(text(r, "stage")) === "—"
                  ? ""
                  : chinese(text(r, "stage"))
              }}</small
              ><small style="color: var(--red)">{{
                text(r, "error") === "—" ? "" : text(r, "error")
              }}</small>
            </td>
            <td v-if="tab === 'registry'" class="mono">
              {{ text(r, "architecture") }}
              <InfoFields
                v-if="r.trainingId"
                :value="r.metrics"
                :fields="['mAP50', 'precision', 'recall']"
              />
            </td>
            <td v-else>
              <span class="mono">{{
                r.progress === undefined ? "—" : r.progress + "%"
              }}</span>
              <div
                v-if="r.progress !== undefined"
                class="bar"
                style="width: 95px; margin-top: 7px"
              >
                <span :style="{ width: `${r.progress}%` }" />
              </div>
            </td>
            <td>{{ new Date(r.createdAt).toLocaleString() }}</td>
            <td>
              <button @click="open(r)" class="table-action">详情</button
              ><button
                v-if="
                  tab === 'training' &&
                  ['QUEUED', 'RUNNING'].includes(r.status ?? '')
                "
                @click="action(r.id, 'cancel')"
                class="table-action"
                :disabled="busy"
              >
                取消</button
              ><button
                v-if="
                  tab === 'deployments' &&
                  r.previousVersion &&
                  ['ACTIVE', 'FAILED'].includes(r.status ?? '')
                "
                @click="action(r.id, 'rollback')"
                class="table-action"
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
  <Drawer
    v-if="form"
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
      ><label v-if="tab !== 'deployments'"
        >{{ tab === "training" ? "训练数据集" : "评估数据集"
        }}<select v-model="datasetId" required>
          <option value="">选择数据集</option>
          <option
            v-for="d in datasets"
            :key="d.id"
            :value="d.id"
            :disabled="tab === 'training' && d._count.items < 2"
          >
            {{ datasetLabel(d)
            }}{{
              tab === "training" && d._count.items < 2 ? " · 至少需要 2 张" : ""
            }}
          </option>
        </select></label
      >
      <div
        v-if="tab === 'training' && !datasets.some((d) => d._count.items >= 2)"
        class="training-empty"
      >
        <b>还没有可训练的数据集</b>
        <p>选入至少两张已标注样本，并锁定数据集版本。</p>
        <RouterLink to="/data/samples?annotation=complete" @click="form = false"
          >整理已标注样本 →</RouterLink
        >
      </div>
      <p
        v-if="
          tab === 'training' &&
          chosenDataset &&
          datasetSources(chosenDataset)?.SIMULATION
        "
        class="note"
      >
        此数据集含
        {{ datasetSources(chosenDataset).SIMULATION }}
        张模拟样本，适合验证操作流程；效果评估请使用真实图片。
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
            >计算设备<select v-model="trainingOptions.device">
              <option value="cuda">CUDA GPU</option>
              <option value="cpu">CPU（调试）</option>
            </select></label
          >
          <label v-if="trainingOptions.device === 'cuda'"
            ><input
              type="checkbox"
              v-model="trainingOptions.amp"
            />混合精度训练</label
          >
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
          使用冻结标注和固定六类检测结构。没有验证集时按种子划分 20%
          留出验证，至少需要两张样本。训练完成后可下载模型包、训练记录和检查点。
        </p>
      </template>
      <label v-if="tab !== 'training'"
        >模型<select v-model="modelId" required>
          <option value="">选择模型</option>
          <option v-for="m in models" :key="m.id" :value="m.id">
            {{ displayName(m.name) }} / {{ m.version }} /
            {{ chinese(m.status) }}
          </option>
        </select></label
      ><label v-if="tab !== 'training'"
        >设备<select v-model="deviceId" required>
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
        </select></label
      >
      <p v-if="tab === 'deployments' && willSwitch" class="note">
        该制品已经在所选设备的 SD 卡上：提交后板端跳过传输，直接切换。
      </p>
      <p v-else-if="tab !== 'training'" class="note">
        请选择兼容的模型、数据集和设备。
      </p>
      <button
        class="primary"
        :disabled="
          busy ||
          (tab === 'training' &&
            (!chosenDataset || chosenDataset._count.items < 2))
        "
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
      >查看生成模型 →</RouterLink
    >
    <InfoFields
      :value="detail"
      :fields="[
        'name',
        'version',
        'source',
        'status',
        'architecture',
        'stage',
        'progress',
        'datasetId',
        'modelId',
        'deviceId',
        'previousVersion',
        'createdAt',
        'error',
      ]"
    />
    <details>
      <summary>原始数据</summary>
      <pre>{{ JSON.stringify(detail, null, 2) }}</pre>
    </details></Drawer
  ><Drawer v-if="importing" title="导入模型包" @close="importing = false"
    ><form @submit.prevent="importModel">
      <label>模型名称<input v-model="name" required /></label
      ><label>版本<input v-model="version" required /></label
      ><label
        >模型清单（JSON）<textarea
          v-model="manifest"
          required
          rows="14"
          class="mono"
        /></label
      ><label
        >模型包（model.bin）<input
          type="file"
          @change="
            file = ($event.target as HTMLInputElement).files?.[0] ?? null
          "
          required /></label
      ><button class="primary" :disabled="busy">验证并导入</button>
    </form></Drawer
  >
</template>
<style scoped>
.training-empty {
  padding: 18px;
  margin: 16px 0;
  border: 1px solid var(--line);
  background: var(--surface-2);
  font-size: 13px;
}
.training-empty p {
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
</style>
