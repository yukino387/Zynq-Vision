<script setup lang="ts">
import InfoFields from "../components/InfoFields.vue";
import { chinese, displayName } from "@vision/shared";
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { Named, Sample } from "../types";
import type { InspectionPlan } from "@vision/contracts";
import { useList } from "../composables/useList";
import { api, post, download } from "../api";
import { useNotificationStore } from "../stores/notifications";
import { useAuthStore } from "../stores/auth";
import { useTaskStore } from "../stores/tasks";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import SortableTh from "../components/SortableTh.vue";
import Pager from "../components/Pager.vue";
import Drawer from "../components/Drawer.vue";
import AssetThumbnail from "../components/AssetThumbnail.vue";
import type { Asset } from "../types";
import ImageViewer from "../components/ImageViewer.vue";
import AnnotationEditor from "../components/AnnotationEditor.vue";
const route = useRoute(),
  router = useRouter(),
  tasks = useTaskStore(),
  auth = useAuthStore(),
  notices = useNotificationStore();
const tab = computed(() =>
  String(route.params.tab || route.meta.defaultTab || "samples"),
);
const endpoint = computed(() =>
    tab.value === "tasks"
      ? "/tasks"
      : tab.value === "datasets"
        ? "/datasets"
        : "/samples",
  ),
  list = useList<Named>(endpoint);
const gallery = ref(true);
const plans = ref<InspectionPlan[]>([]),
  taskPlanId = ref("");
const importProgress = ref({ done: 0, total: 0 });
const sampleScope = ref("REAL"),
  annotationFilter = ref("");
list.pageSize.value = 50;
const assets = (row: Named) => (row.assets as Asset[] | undefined) ?? [];
const selectedIds = ref<string[]>([]),
  sample = ref<Sample | null>(null),
  annotating = ref(false),
  dataset = ref<Named | null>(null),
  createOpen = ref(false),
  name = ref(""),
  version = ref(1),
  target = ref(30),
  busy = ref(false),
  reviewVerdict = ref("ACCEPT"),
  reviewNote = ref(""),
  datasetId = ref(""),
  datasets = ref<Named[]>([]);
const creatingDataset = ref(false);
const isDatasetCreation = computed(
  () => tab.value === "datasets" || creatingDataset.value,
);
const datasetQuality = computed(
  () =>
    dataset.value?.quality as
      | {
          sourceCounts: Record<string, number>;
          classes: Record<string, number>;
        }
      | undefined,
);
const datasetItems = computed(
  () => (dataset.value?.items as unknown[] | undefined)?.length ?? 0,
);
const annotationReady = (row: Named) =>
  Number(
    (row._count as { annotations?: number } | undefined)?.annotations ?? 0,
  ) > 0;
const completedOnPage = computed(() =>
  list.items.value.filter(annotationReady),
);
function openDatasetCreation() {
  creatingDataset.value = true;
  createOpen.value = true;
  name.value = `缺陷样本 ${new Date().toLocaleDateString()}`;
}
watch(
  () => [
    tab.value,
    route.query.source,
    route.query.annotation,
    route.query.datasetId,
    route.query.create,
    route.query.planId,
  ],
  () => {
    creatingDataset.value = tab.value === "datasets";
    taskPlanId.value = String(route.query.planId ?? "");
    if (auth.engineer && tab.value === "tasks")
      void api<{ items: InspectionPlan[] }>("/plans?pageSize=100")
        .then((r) => {
          plans.value = r.items.filter((p) => Array.isArray(p.rules.classes));
        })
        .catch(notices.error);
    selectedIds.value = [];
    datasetId.value = String(route.query.datasetId ?? "");
    sampleScope.value = String(route.query.source ?? "REAL");
    annotationFilter.value = String(
      route.query.annotation ?? (tab.value === "annotation" ? "pending" : ""),
    );
    list.realOnly.value =
      !["tasks", "datasets"].includes(tab.value) && sampleScope.value === "REAL"
        ? "true"
        : "";
    list.source.value = ["BOARD", "MOBILE", "IMPORT", "SIMULATION"].includes(
      sampleScope.value,
    )
      ? sampleScope.value
      : "";
    list.annotation.value = ["tasks", "datasets"].includes(tab.value)
      ? ""
      : annotationFilter.value;
    list.reviewed.value = tab.value === "review" ? "false" : "";
    list.status.value = "";
    if (route.query.create === "1") {
      creatingDataset.value = tab.value === "datasets";
      createOpen.value = true;
    }
    if (datasetId.value) void selectDataset();
    list.filter();
  },
  { immediate: true },
);
watch([sampleScope, annotationFilter], () => {
  list.realOnly.value = sampleScope.value === "REAL" ? "true" : "";
  list.source.value = ["BOARD", "MOBILE", "IMPORT", "SIMULATION"].includes(
    sampleScope.value,
  )
    ? sampleScope.value
    : "";
  list.annotation.value = annotationFilter.value;
  list.filter();
});
watch(
  () => selectedIds.value.length,
  (count, previous) => {
    if (count > 0 && previous === 0) void selectDataset();
  },
);
const selectedRows = computed(() => list.items.value);
const missingAnnotation = computed(() =>
  list.items.value.find(
    (row) => selectedIds.value.includes(row.id) && !annotationReady(row),
  ),
);
const text = (row: Named, key: string) =>
  row[key] === null || row[key] === undefined
    ? "—"
    : typeof row[key] === "object"
      ? JSON.stringify(row[key])
      : String(row[key]);
const counts = (r: Named, k: string) =>
  String((r._count as Record<string, number> | undefined)?.[k] ?? 0);
async function create(startSampling = false) {
  busy.value = true;
  try {
    const isDataset = isDatasetCreation.value;
    const created = await post<Named>(isDataset ? "/datasets" : "/tasks", {
      name: name.value,
      ...(isDataset
        ? { version: version.value }
        : {
            target: target.value,
            ...(taskPlanId.value ? { planId: taskPlanId.value } : {}),
          }),
    });
    createOpen.value = false;
    name.value = "";
    await list.load();
    if (isDataset) {
      if (selectedIds.value.length) {
        await post(`/datasets/${created.id}/items`, {
          sampleIds: selectedIds.value,
        });
        selectedIds.value = [];
      }
      dataset.value = await api(`/datasets/${created.id}`);
      notices.add("数据集已创建，可以继续添加样本或锁定版本");
    } else {
      notices.add("采样任务已创建");
      await tasks.load();
      if (startSampling) {
        tasks.selected = created.id;
        await router.push({ name: "workbench" });
      }
    }
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function open(row: Named, annotation = false) {
  try {
    if (tab.value === "datasets") {
      dataset.value = await api(`/datasets/${row.id}`);
    } else {
      sample.value = await api(`/samples/${row.id}`);
      annotating.value = annotation;
      reviewVerdict.value = "ACCEPT";
      reviewNote.value = "";
    }
  } catch (e) {
    notices.error(e);
  }
}
async function action(id: string, type: string) {
  busy.value = true;
  try {
    if (type === "export") await post(`/datasets/${id}/export-jobs`);
    else await post(`/datasets/${id}/${type}`);
    await list.load();
    if (dataset.value) dataset.value = await api(`/datasets/${id}`);
    notices.add(
      type === "freeze"
        ? "数据集已冻结"
        : type === "clone"
          ? "新版本已创建"
          : "导出已排队，可在系统任务队列中下载",
    );
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function selectDataset() {
  try {
    datasets.value = (
      await api<{ items: Named[] }>("/datasets?status=DRAFT&pageSize=100")
    ).items;
  } catch (e) {
    notices.error(e);
  }
}
async function addItems() {
  if (!datasetId.value || missingAnnotation.value) return;
  busy.value = true;
  try {
    await post(`/datasets/${datasetId.value}/items`, {
      sampleIds: selectedIds.value,
    });
    selectedIds.value = [];
    notices.add("已加入数据集，标注版本已记录");
    dataset.value = await api(`/datasets/${datasetId.value}`);
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function upload(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  if (!files.length) return;
  busy.value = true;
  importProgress.value = { done: 0, total: files.length };
  const failures: string[] = [];
  try {
    for (const file of files) {
      try {
        const form = new FormData();
        form.append(
          "metadata",
          JSON.stringify({
            source: "IMPORT",
            taskId: tasks.selected || undefined,
            clientId: crypto.randomUUID(),
            idempotencyKey: crypto.randomUUID(),
            localSequence: 0,
            capturedAt: new Date().toISOString(),
          }),
        );
        form.append("file", file);
        await api("/samples/upload", { method: "POST", body: form });
      } catch {
        failures.push(file.name);
      }
      importProgress.value.done++;
    }
    await list.load();
    const added = files.length - failures.length;
    if (added) notices.add(`已导入 ${added} 张图片，可继续标注`);
    if (failures.length)
      notices.add(
        `${failures.length} 张导入失败：${failures.slice(0, 3).join("、")}${failures.length > 3 ? "…" : ""}`,
        true,
      );
  } finally {
    busy.value = false;
    importProgress.value.total = 0;
    input.value = "";
  }
}
async function review(next = false) {
  if (!sample.value) return;
  busy.value = true;
  try {
    await post(`/samples/${sample.value.id}/review`, {
      verdict: reviewVerdict.value,
      note: reviewNote.value,
      hard: sample.value.hard,
    });
    sample.value = await api(`/samples/${sample.value.id}`);
    if (next) list.page.value = 1;
    await list.load();
    notices.add("样本审核已保存");
    if (next) {
      const item = list.items.value.find((r) => r.id !== sample.value?.id);
      if (item) await open(item);
      else {
        sample.value = null;
        notices.add("当前没有其他待审核样本");
      }
    }
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function saveAnnotation(next = false) {
  const nextId =
    list.items.value[
      list.items.value.findIndex((row) => row.id === sample.value?.id) + 1
    ]?.id;
  if (sample.value) sample.value = await api(`/samples/${sample.value.id}`);
  await list.load();
  if (next) {
    const nextRow =
      list.items.value.find((row) => row.id === nextId) ??
      list.items.value.find((row) => row.id !== sample.value?.id);
    if (nextRow) await open(nextRow, true);
    else {
      sample.value = null;
      notices.add("当前列表已全部处理，可切换筛选或整理数据集");
    }
  }
}
async function adjacent(delta: number) {
  if (!sample.value) return;
  const index =
    list.items.value.findIndex((r) => r.id === sample.value!.id) + delta;
  const item = list.items.value[index];
  if (item) await open(item, true);
}
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
          tab === "annotation"
            ? "按方案中的对象类别框选标注。缺件由规则判断，不为不存在的部件画框。"
            : tab === "datasets"
              ? "整理已标注样本，由管理员审核后冻结训练版本。"
              : tab === "samples"
                ? auth.engineer
                  ? "整理采集与导入的图片，完成标注并提交管理员审核。"
                  : "查看采样结果和审核状态；需要补充时按任务重新采集。"
                : tab === "tasks"
                  ? "按产品方案安排采样；工人按任务中的摆放指引完成采集。"
                  : ""
        }}
      </p>
    </div>
    <div class="heading-actions">
      <label
        v-if="tab !== 'tasks' && tab !== 'datasets'"
        class="button"
        style="
          margin: 0;
          cursor: pointer;
          border: 1px solid var(--line);
          padding: 9px 12px;
          border-radius: 4px;
        "
        >{{
          importProgress.total
            ? `正在导入 ${importProgress.done}/${importProgress.total}`
            : "导入图片（可多选）"
        }}<input
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp"
          style="display: none"
          @change="upload"
          :disabled="busy" /></label
      ><button
        v-if="auth.engineer && ['tasks', 'datasets'].includes(tab)"
        class="primary"
        @click="
          creatingDataset = tab === 'datasets';
          createOpen = true;
        "
      >
        {{ tab === "tasks" ? "创建任务" : "创建数据集" }}
      </button>
    </div>
  </div>
  <section v-if="tab === 'datasets'" class="lab-banner dataset-banner">
    <div>
      <span class="workspace-index">05 / 数据集实验室</span>
      <h2>数据集版本</h2>
    </div>
    <div class="lab-index">
      <b class="mono">{{ list.total.value }}</b
      ><span>数据集版本</span>
    </div>
    <div class="lab-flow">
      <span>01 整理样本</span><span>02 完成标注</span><span>03 冻结版本</span>
    </div>
  </section>
  <div
    v-if="['samples', 'review', 'annotation'].includes(tab)"
    class="library-view-control"
  >
    <div>
      <span class="workspace-index">{{
        tab === "annotation" ? "04 / 标注工作区" : "03 / 图像资源库"
      }}</span
      ><span>{{ list.total.value }} 张图像</span>
    </div>
    <div class="segmented" aria-label="样本视图">
      <button
        :aria-pressed="gallery"
        :class="{ active: gallery }"
        @click="gallery = true"
      >
        图像</button
      ><button
        :aria-pressed="!gallery"
        :class="{ active: !gallery }"
        @click="gallery = false"
      >
        表格
      </button>
    </div>
  </div>
  <form class="toolbar" @submit.prevent="list.filter">
    <input v-model="list.search.value" placeholder="搜索名称…" /><select
      v-model="sampleScope"
      v-if="!['tasks', 'datasets'].includes(tab)"
    >
      <option value="REAL">真实样本</option>
      <option value="ALL">全部来源（含模拟）</option>
      <option value="BOARD">{{ chinese("BOARD") }}</option>
      <option value="MOBILE">{{ chinese("MOBILE") }}</option>
      <option value="IMPORT">{{ chinese("IMPORT") }}</option>
      <option value="SIMULATION">{{ chinese("SIMULATION") }}</option></select
    ><select
      v-if="['samples', 'annotation'].includes(tab)"
      v-model="annotationFilter"
      aria-label="标注进度"
    >
      <option value="">全部标注进度</option>
      <option value="pending">待标注</option>
      <option value="complete">已完成标注</option>
    </select>
    <select
      v-model="list.status.value"
      v-if="tab !== 'annotation'"
      aria-label="审核状态"
    >
      <option value="">全部状态</option>
      <option
        v-for="s in tab === 'datasets'
          ? ['DRAFT', 'READY', 'FROZEN']
          : tab === 'tasks'
            ? ['OPEN', 'COMPLETED']
            : tab === 'review'
              ? ['PENDING', 'NEEDS_WORK']
              : ['PENDING', 'REVIEWED', 'NEEDS_WORK', 'REJECTED']"
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
    ><template
      v-if="gallery && ['samples', 'review', 'annotation'].includes(tab)"
      ><select
        v-model="list.sort.value"
        aria-label="排序字段"
        @change="list.filter"
      >
        <option value="createdAt">创建时间</option>
        <option value="name">名称</option>
        <option value="status">状态</option></select
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
  <div v-if="tab === 'annotation'" class="data-next-action">
    <span>默认展示待标注的真实图片；完成标注后可整理训练数据集。</span
    ><RouterLink to="/data/samples?annotation=complete"
      >整理已标注样本 →</RouterLink
    >
  </div>
  <div v-if="tab === 'samples' && auth.engineer" class="data-next-action">
    <span>{{
      datasetId
        ? "正在为选定的数据集添加样本"
        : "选中已标注的图片，即可加入或新建数据集"
    }}</span
    ><button
      :disabled="!completedOnPage.length || busy"
      @click="selectedIds = completedOnPage.map((row) => row.id)"
    >
      选择本页已标注样本
    </button>
  </div>
  <div v-if="selectedIds.length && auth.engineer" class="toolbar">
    <span>已选 {{ selectedIds.length }} 个样本</span
    ><button @click="selectedIds = []" :disabled="busy">取消选择</button
    ><template v-if="missingAnnotation"
      ><span class="tone-warn">所选样本尚未完成标注</span
      ><button @click="open(missingAnnotation, true)">
        先完成标注
      </button></template
    ><select v-model="datasetId" aria-label="目标数据集">
      <option value="">选择草稿数据集</option>
      <option v-for="d in datasets" :key="d.id" :value="d.id">
        {{ displayName(d.name) }} / V{{ d.version }}
      </option></select
    ><button
      class="primary"
      @click="addItems"
      :disabled="busy || !datasetId || !!missingAnnotation"
    >
      加入数据集
    </button>
    <button
      @click="openDatasetCreation"
      :disabled="busy || !!missingAnnotation"
    >
      新建数据集并加入
    </button>
  </div>
  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!selectedRows.length"
    :hint="
      tab === 'tasks'
        ? '点击“创建任务”开始采样。'
        : tab === 'datasets'
          ? '创建数据集后，从样本库选择已完成标注的样本加入。'
          : tab === 'review'
            ? '当前没有待审核样本。'
            : tab === 'annotation'
              ? '当前筛选下没有待处理图片。可切换“全部标注进度”查看，或先导入图片。'
              : '可导入图片，或前往检测工作台采样。'
    "
    @retry="list.load"
    ><div
      v-if="gallery && ['samples', 'review', 'annotation'].includes(tab)"
      class="sample-gallery"
      :class="{ 'annotation-library': tab === 'annotation' }"
    >
      <article
        v-for="(r, i) in selectedRows"
        :key="r.id"
        class="sample-tile"
        :class="{ selected: selectedIds.includes(r.id) }"
      >
        <div class="sample-tile-top">
          <span class="mono">{{
            String(
              (list.page.value - 1) * list.pageSize.value + i + 1,
            ).padStart(3, "0")
          }}</span
          ><label v-if="tab === 'samples' && auth.engineer"
            ><input
              type="checkbox"
              v-model="selectedIds"
              :value="r.id"
              :aria-label="`选择 ${displayName(r.name)}`"
            />选择</label
          ><span
            v-if="tab === 'annotation'"
            class="tag"
            :class="{ ok: annotationReady(r) }"
            >{{ annotationReady(r) ? "已完成标注" : "待标注" }}</span
          ><Status v-else :value="r.status" />
        </div>
        <button
          class="sample-image-button"
          @click="open(r, tab === 'annotation')"
          :aria-label="`${tab === 'annotation' ? '标注' : '查看'} ${displayName(r.name)}`"
        >
          <AssetThumbnail :assets="assets(r)" :alt="displayName(r.name)" /><span
            class="sample-open"
            >{{
              tab === "annotation"
                ? "开始标注"
                : tab === "review"
                  ? "审核样本"
                  : "查看图像"
            }}</span
          >
        </button>
        <div class="sample-caption">
          <strong>{{ displayName(r.name) }}</strong>
          <span
            v-if="tab === 'samples'"
            class="sample-annotation-state"
            :class="{ complete: annotationReady(r) }"
            >{{ annotationReady(r) ? "✓ 已完成标注" : "待标注"
            }}<button
              v-if="auth.engineer && !annotationReady(r)"
              class="text-button"
              @click="open(r, true)"
            >
              去标注 →
            </button></span
          >
          <div>
            <span
              class="tag"
              :class="{ simulated: r.source === 'SIMULATION' }"
              >{{ chinese(r.source) }}</span
            ><small class="mono">{{ r.id.slice(-8) }}</small>
          </div>
          <small
            >{{ new Date(r.createdAt).toLocaleString()
            }}{{ r.hard ? " · 困难样本" : "" }}</small
          >
        </div>
      </article>
    </div>
    <div v-else class="panel table-wrap">
      <table>
        <thead>
          <tr>
            <th v-if="tab === 'samples' && auth.engineer"></th>
            <!-- 三个接口（/tasks、/samples、/datasets）的白名单都允许 name、status、createdAt -->
            <SortableTh
              field="name"
              :label="
                tab === 'tasks'
                  ? '任务'
                  : tab === 'datasets'
                    ? '数据集 / 版本'
                    : '样本'
              "
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <th>
              {{
                tab === "tasks"
                  ? "目标 / 已采集"
                  : tab === "datasets"
                    ? "样本数"
                    : "来源"
              }}
            </th>
            <SortableTh
              field="status"
              label="状态"
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <!-- 质量那一栏的表头是「质量报告」而不是日期，按时间排会误导，所以不挂排序 -->
            <SortableTh
              v-if="tab !== 'quality'"
              field="createdAt"
              label="创建时间"
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <th v-else>质量报告</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in selectedRows" :key="r.id">
            <td v-if="tab === 'samples' && auth.engineer">
              <input
                type="checkbox"
                v-model="selectedIds"
                :value="r.id"
                :aria-label="`选择 ${displayName(r.name)}`"
              />
            </td>
            <td>
              <strong>{{ displayName(r.name) }}</strong
              ><small v-if="tab === 'tasks' && r.plan"
                >{{
                  (r.plan as InspectionPlan).rules.product ||
                  (r.plan as InspectionPlan).name
                }}
                · V{{ (r.plan as InspectionPlan).version }}</small
              ><small class="mono"
                >{{ r.id.slice(-10) }} {{ r.version ? `/ V${r.version}` : "" }}
                {{ r.hard ? "· 困难样本" : "" }}</small
              >
            </td>
            <td v-if="tab === 'tasks'" class="mono">
              {{ text(r, "target") }} / {{ counts(r, "samples") }}
            </td>
            <td v-else-if="tab === 'datasets'" class="mono">
              {{ counts(r, "items") }}
            </td>
            <td v-else>
              <span
                class="tag"
                :class="{ simulated: r.source === 'SIMULATION' }"
                >{{ chinese(r.source) }}</span
              >
            </td>
            <td>
              <span v-if="tab === 'annotation'" class="tag">{{
                annotationReady(r) ? "已完成标注" : "待标注"
              }}</span
              ><Status v-else :value="r.status" />
            </td>
            <td v-if="tab === 'quality'">
              <InfoFields :value="r.quality" :fields="['status']" />
            </td>
            <td v-else>{{ new Date(r.createdAt).toLocaleString() }}</td>
            <td v-if="tab === 'datasets'">
              <button @click="open(r)" class="table-action">详情</button
              ><button
                v-if="r.status !== 'FROZEN' && auth.admin"
                @click="action(r.id, 'freeze')"
                class="table-action"
                :disabled="busy"
              >
                冻结</button
              ><button
                v-else
                @click="action(r.id, 'clone')"
                class="table-action"
                :disabled="busy"
              >
                创建新版本
              </button>
            </td>
            <td v-else-if="tab === 'tasks'">
              <RouterLink
                :to="{ name: 'workbench' }"
                @click="tasks.selected = r.id"
                >开始采样</RouterLink
              >
            </td>
            <td v-else>
              <button
                @click="open(r, tab === 'annotation')"
                class="table-action"
              >
                {{
                  tab === "annotation"
                    ? "开始标注"
                    : tab === "review"
                      ? "审核"
                      : "查看"
                }}
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
    v-if="createOpen"
    :title="isDatasetCreation ? '创建数据集' : '创建采样任务'"
    @close="createOpen = false"
    ><form @submit.prevent="create(!isDatasetCreation)">
      <label>名称<input v-model="name" required maxlength="120" /></label
      ><label v-if="!isDatasetCreation"
        >关联检查方案<select v-model="taskPlanId">
          <option value="">暂不关联（独立采样）</option>
          <option v-for="plan in plans" :key="plan.id" :value="plan.id">
            {{ plan.rules.product }} · {{ plan.name }} / V{{ plan.version }}
          </option>
        </select></label
      ><label v-if="isDatasetCreation"
        >版本<input type="number" min="1" v-model.number="version" /></label
      ><label v-else
        >目标样本数<input type="number" min="1" v-model.number="target"
      /></label>
      <div class="form-actions">
        <button class="primary" :disabled="busy">
          {{
            !isDatasetCreation
              ? "创建并开始采样"
              : selectedIds.length
                ? `创建并加入 ${selectedIds.length} 张样本`
                : "创建数据集"
          }}</button
        ><button
          v-if="!isDatasetCreation"
          type="button"
          :disabled="busy"
          @click="create(false)"
        >
          仅创建
        </button>
      </div>
    </form></Drawer
  ><Drawer
    v-if="sample"
    :wide="true"
    :class="{ 'annotation-dialog': annotating }"
    :title="displayName(sample.name)"
    @close="sample = null"
    ><div class="toolbar">
      <span
        class="tag"
        :class="{ simulated: sample.source === 'SIMULATION' }"
        >{{ chinese(sample.source) }}</span
      ><button v-if="auth.engineer" @click="annotating = !annotating">
        {{ annotating ? "图像详情" : "进入标注" }}</button
      ><template v-if="annotating"
        ><button
          :disabled="list.items.value[0]?.id === sample.id"
          @click="adjacent(-1)"
        >
          上一张</button
        ><button
          :disabled="list.items.value.at(-1)?.id === sample.id"
          @click="adjacent(1)"
        >
          下一张
        </button></template
      >
    </div>
    <AnnotationEditor
      v-if="annotating"
      :sample="sample"
      @saved="saveAnnotation"
    />
    <div v-else class="sample-review-workspace">
      <div>
        <ImageViewer
          compact
          :assets="sample.assets"
          :boxes="sample.annotations[0]?.boxes"
        />
        <p class="note">
          {{ sample.hard ? "困难样本" : "标准样本" }} · 标注版本
          {{ sample.annotations[0]?.version ?? "暂无" }}
        </p>
        <details class="section-space">
          <summary>样本原始信息</summary>
          <pre>{{
            JSON.stringify(
              { metadata: sample.metadata, quality: sample.quality },
              null,
              2,
            )
          }}</pre>
        </details>
      </div>
      <section v-if="auth.admin" class="review-panel">
        <h3>样本审核</h3>
        <label
          >结论<select v-model="reviewVerdict">
            <option value="ACCEPT">接纳样本</option>
            <option value="REJECT">拒绝样本</option>
            <option value="NEEDS_WORK">待补充</option>
          </select></label
        ><label class="check-row"
          ><input type="checkbox" v-model="sample.hard" />困难样本</label
        ><label>备注<textarea v-model="reviewNote" rows="2" /></label>
        <div class="form-actions">
          <button
            v-if="tab === 'review'"
            @click="review(true)"
            class="primary"
            :disabled="busy"
          >
            保存并审核下一张</button
          ><button
            @click="review(false)"
            :class="{ primary: tab !== 'review' }"
            :disabled="busy"
          >
            保存审核
          </button>
        </div>
        <details class="section-space">
          <summary>原始文件与下载</summary>
          <div v-for="a in sample.assets" :key="a.id" class="list-line">
            <div>
              <b>{{ chinese(a.kind) }}</b
              ><small class="mono">{{ a.sha256 }}</small>
            </div>
            <button
              @click="
                download(`/assets/${a.id}/content`, `${a.id}.raw`).catch(
                  notices.error,
                )
              "
            >
              下载
            </button>
          </div>
        </details>
      </section>
      <section v-else class="review-panel">
        <h3>样本状态：{{ chinese(sample.status) }}</h3>
        <p>审核接纳与退回由管理员处理。现场反馈请在对应结果中提交复核意见。</p>
        <RouterLink
          v-if="auth.engineer"
          to="/data/annotation"
          @click="sample = null"
          >继续标注</RouterLink
        >
      </section>
    </div></Drawer
  ><Drawer
    v-if="dataset"
    :title="`${displayName(dataset.name)} / V${dataset.version}`"
    @close="dataset = null"
    ><Status :value="dataset.status" />
    <div class="dataset-summary">
      <div>
        <strong>{{ datasetItems }}</strong
        ><span>张已标注样本</span>
      </div>
      <div>
        <strong>{{
          Object.entries(datasetQuality?.sourceCounts ?? {})
            .filter(([source]) => source !== "SIMULATION")
            .reduce((sum, [, count]) => sum + count, 0)
        }}</strong
        ><span>张真实样本</span>
      </div>
    </div>
    <p class="note">
      {{
        dataset.status === "FROZEN"
          ? "当前版本已锁定，训练将使用这批样本与标注。"
          : "先加入至少两张已标注样本，再锁定版本用于训练。"
      }}
    </p>
    <div class="form-actions">
      <RouterLink
        v-if="dataset.status !== 'FROZEN'"
        class="button-link"
        :to="{
          name: 'data',
          params: { tab: 'samples' },
          query: { datasetId: dataset.id, annotation: 'complete' },
        }"
        @click="dataset = null"
        >添加已标注样本</RouterLink
      ><button
        v-if="dataset.status !== 'FROZEN' && auth.admin"
        class="primary"
        :disabled="busy || datasetItems < 2"
        @click="action(dataset.id, 'freeze')"
      >
        锁定版本用于训练</button
      ><RouterLink
        v-else-if="datasetItems >= 2"
        class="button-link primary"
        :to="{
          name: 'models',
          params: { tab: 'training' },
          query: { datasetId: dataset.id, create: '1' },
        }"
        >用此数据集训练 →</RouterLink
      >
    </div>
    <div v-if="datasetQuality" class="dataset-class-list">
      <span v-for="(count, label) in datasetQuality.classes" :key="label"
        >{{ label }} <b>{{ count }}</b></span
      >
    </div>

    <div class="toolbar">
      <button
        :disabled="dataset.status !== 'FROZEN' || busy"
        @click="action(dataset.id, 'export')"
      >
        导出数据集</button
      ><button @click="action(dataset.id, 'clone')" :disabled="busy">
        创建新版本
      </button>
    </div>
    <InfoFields
      :value="dataset"
      :fields="['name', 'version', 'status', 'createdAt']"
    />
    <details>
      <summary>版本与样本数据</summary>
      <pre>{{ JSON.stringify(dataset, null, 2) }}</pre>
    </details>
  </Drawer>
</template>
<style scoped>
.data-next-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  font-size: 12px;
  color: var(--muted);
  margin: 14px 0;
  flex-wrap: wrap;
}
.sample-annotation-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--muted);
  margin-top: 8px;
}
.sample-annotation-state.complete {
  color: var(--forest);
}
.sample-annotation-state button {
  font-size: 11px;
  padding: 0;
}
.dataset-summary {
  display: flex;
  gap: 40px;
  padding: 22px 0;
}
.dataset-summary > div {
  display: grid;
  gap: 8px;
}
.dataset-summary strong {
  font-size: 32px;
}
.dataset-summary span {
  font-size: 12px;
  color: var(--muted);
}
.dataset-class-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 22px 0;
}
.dataset-class-list > span {
  font-size: 12px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  padding: 6px 10px;
}
.dataset-class-list b {
  margin-left: 8px;
}
</style>
