<script setup lang="ts">
import { randomUUID } from "../uuid";
import InfoFields from "../components/InfoFields.vue";
import { chinese, displayName } from "@vision/shared";
import { ref, computed, watch, nextTick, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { Named, Sample, Task } from "../types";
import type { InspectionPlan } from "@vision/contracts";
import { useList } from "../composables/useList";
import { api, post, download, errorText } from "../api";
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
import { useProductStore } from "../stores/product";
const workflow = useProductStore();
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
const editingTask = ref<Task | null>(null);
const importProgress = ref({ done: 0, total: 0 });
const sampleScope = ref("REAL"),
  annotationFilter = ref("");
const sampleTabs = ["samples", "annotation", "review", "quality"];
const sourceOptions = [
  ["REAL", "全部来源"],
  ["BOARD", "板卡采样"],
  ["MOBILE", "手机采样"],
  ["IMPORT", "导入图片"],
];
const reviewOptions = [
  ["ACCEPT", "通过"],
  ["NEEDS_WORK", "退回补充"],
  ["REJECT", "拒绝"],
];
const filterTask = ref(""),
  taskOptions = ref<Task[]>([]),
  batchNote = ref("");
const importOpen = ref(false),
  importTaskId = ref(""),
  importPlanId = ref("");
const importInput = ref<HTMLInputElement | null>(null);
const deleteRequest = ref<{
  kind: "samples" | "datasets" | "tasks";
  rows: Named[];
} | null>(null);
const advancing = ref(false);
const assignmentTaskId = ref(""),
  assignmentPlanId = ref("");
const annotationTasks = computed(() =>
  taskOptions.value.filter(
    (t) =>
      t.status === "OPEN" &&
      Array.isArray(t.plan?.rules?.classes) &&
      t.plan.rules.classes.length > 0,
  ),
);
list.pageSize.value = 50;
const assets = (row: Named) => (row.assets as Asset[] | undefined) ?? [];
const assetFilename = (asset: Asset) =>
  `${asset.id}${({ "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp" } as Record<string, string>)[asset.mimeType] ?? ".raw"}`;
const qualityFields = [
  ["width", "宽度（像素）"],
  ["height", "高度（像素）"],
  ["brightness", "平均亮度（0–255）"],
  ["contrast", "对比度"],
  ["sharpness", "清晰度"],
] as const;
const qualityValue = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value)
    ? Math.round(value * 100) / 100
    : "未检测";
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
const planSearch = ref("");
const matchingPlans = computed(() =>
  plans.value.filter((plan) =>
    `${plan.name} ${plan.rules.product} ${plan.rules.classes.join(" ")}`
      .toLowerCase()
      .includes(planSearch.value.toLowerCase()),
  ),
);
const selectedPlan = computed(() =>
  plans.value.find((plan) => plan.id === taskPlanId.value),
);
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
const datasetRows = computed(
  () =>
    (dataset.value?.items ?? []) as Array<{
      sampleId: string;
      needsUpdate: boolean;
      sample: Named & { deletedAt?: string; assets: Asset[] };
      annotationSet: { version: number };
    }>,
);
const annotationReady = (row: Named) =>
  (row.annotations as Array<{ status?: string }> | undefined)?.[0]?.status ===
  "COMPLETE";
const lastReview = (row: Named) =>
  (row.reviews as Array<{ verdict: string; note: string }> | undefined)?.[0];
const annotationLabel = (row: Named) => {
  const annotations = row.annotations as
    Array<{ status?: string; boxes?: unknown[] }> | undefined;
  const latest = annotations?.[0];
  if (latest?.status === "DRAFT") return "标注草稿 · 待完成";
  if (!latest || latest.status !== "COMPLETE") return "待标注";
  return latest.boxes?.length
    ? `已标注 ${latest.boxes.length} 项`
    : "已确认无对象";
};
const annotationPosition = computed(() => {
  const index = list.items.value.findIndex(
    (row) => row.id === sample.value?.id,
  );
  return index < 0
    ? 0
    : (list.page.value - 1) * list.pageSize.value + index + 1;
});
const annotationTotal = computed(() => list.total.value);
const datasetReady = computed(() => {
  const items = datasetRows.value;
  return (
    items.length > 0 &&
    items.every(
      (item) =>
        item.sample.status === "REVIEWED" &&
        !item.sample.deletedAt &&
        !item.needsUpdate,
    )
  );
});
const datasetPending = computed(() => {
  const items = datasetRows.value;
  return items.filter(
    (item) =>
      item.sample.status !== "REVIEWED" ||
      item.sample.deletedAt ||
      item.needsUpdate,
  ).length;
});
watch(
  () => [
    list.page.value,
    list.search.value,
    list.status.value,
    list.annotation.value,
    list.source.value,
    list.realOnly.value,
    list.taskId.value,
    list.sort.value,
    list.order.value,
    list.pageSize.value,
    tab.value,
  ],
  () => {
    selectedIds.value = [];
    batchNote.value = "";
  },
);
const completedOnPage = computed(() =>
  list.items.value.filter(annotationReady),
);
let opening = 0;
watch(tab, () => {
  opening++;
  sample.value = null;
  dataset.value = null;
  createOpen.value = false;
  importOpen.value = false;
  deleteRequest.value = null;
  editingTask.value = null;
});
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
    route.query.taskId,
    route.query.open,
  ],
  () => {
    creatingDataset.value = tab.value === "datasets";
    taskPlanId.value = String(route.query.planId ?? workflow.id);
    list.planId.value = sampleTabs.includes(tab.value)
      ? String(route.query.planId ?? workflow.id)
      : "";
    if (auth.engineer)
      void api<{ items: Task[] }>("/tasks?realOnly=true&pageSize=100")
        .then((r) => {
          taskOptions.value = r.items;
        })
        .catch(notices.error);
    if (auth.engineer)
      void api<{ items: InspectionPlan[] }>("/plans?pageSize=100")
        .then((r) => {
          plans.value = r.items.filter(
            (p) =>
              Array.isArray(p.rules.classes) &&
              (p.rules as { source?: string }).source !== "SIMULATION",
          );
        })
        .catch(notices.error);
    selectedIds.value = [];
    datasetId.value = String(route.query.datasetId ?? "");
    filterTask.value = String(route.query.taskId ?? "");
    list.taskId.value = sampleTabs.includes(tab.value) ? filterTask.value : "";
    sampleScope.value = ["BOARD", "MOBILE", "IMPORT"].includes(
      String(route.query.source),
    )
      ? String(route.query.source)
      : "REAL";
    annotationFilter.value = String(
      route.query.annotation ?? (tab.value === "annotation" ? "pending" : ""),
    );
    list.realOnly.value = "true";
    list.source.value = ["BOARD", "MOBILE", "IMPORT"].includes(
      sampleScope.value,
    )
      ? sampleScope.value
      : "";
    list.annotation.value = ["tasks", "datasets"].includes(tab.value)
      ? ""
      : annotationFilter.value;
    list.reviewed.value = tab.value === "review" ? "false" : "";
    list.status.value = "";
    if (tab.value !== "quality") list.qualityStatus.value = "";
    if (
      route.query.create === "1" &&
      auth.engineer &&
      (tab.value !== "tasks" || auth.admin)
    ) {
      creatingDataset.value = tab.value === "datasets";
      createOpen.value = true;
    }
    if (datasetId.value) void selectDataset();
    if (tab.value === "datasets" && typeof route.query.open === "string")
      void api<Named>(`/datasets/${encodeURIComponent(route.query.open)}`)
        .then((row) => {
          if (tab.value === "datasets" && route.query.open === row.id)
            dataset.value = row;
        })
        .catch(notices.error);
    list.filter();
  },
  { immediate: true },
);
watch(list.planId, (id) => {
  if (!sampleTabs.includes(tab.value)) return;
  workflow.select(id);
  if (String(route.query.planId ?? "") !== id)
    void router.replace({ query: { ...route.query, planId: id || undefined } });
});
watch([sampleScope, annotationFilter, filterTask], () => {
  if (!sampleTabs.includes(tab.value)) return;
  list.realOnly.value = "true";
  list.source.value = ["BOARD", "MOBILE", "IMPORT"].includes(sampleScope.value)
    ? sampleScope.value
    : "";
  list.annotation.value = annotationFilter.value;
  list.taskId.value = filterTask.value;
  list.filter();
});
watch(
  () => list.status.value,
  () => list.filter(),
);
let searchTimer: ReturnType<typeof setTimeout>;
watch(list.search, () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => list.filter(), 300);
});
onUnmounted(() => clearTimeout(searchTimer));
watch(
  () => selectedIds.value.length,
  (count, previous) => {
    if (count > 0 && previous === 0) void selectDataset();
  },
);
const selectedRows = computed(() => list.items.value);
const checkedRows = computed(() =>
  list.items.value.filter((row) => selectedIds.value.includes(row.id)),
);
const allChecked = computed(
  () =>
    !!list.items.value.length &&
    checkedRows.value.length === list.items.value.length,
);
function resetFilters() {
  list.search.value = "";
  list.status.value = "";
  list.qualityStatus.value = "";
  sampleScope.value = "REAL";
  annotationFilter.value = tab.value === "annotation" ? "pending" : "";
  filterTask.value = "";
  list.filter();
}
async function requestDelete(
  kind: "samples" | "datasets" | "tasks",
  rows: Named[],
) {
  sample.value = null;
  dataset.value = null;
  await nextTick();
  deleteRequest.value = { kind, rows: [...rows] };
}
async function deleteRows() {
  if (!deleteRequest.value || busy.value) return;
  busy.value = true;
  const { kind, rows } = deleteRequest.value;
  const failed: Named[] = [];
  for (const row of rows) {
    try {
      await api(`/${kind}/${row.id}`, {
        method: "DELETE",
        body: JSON.stringify({ confirm: true }),
      });
    } catch (e) {
      failed.push(row);
      notices.error(e);
    }
  }
  selectedIds.value = failed.map((row) => row.id);
  deleteRequest.value = failed.length ? { kind, rows: failed } : null;
  if (rows.length > failed.length)
    notices.add(
      `已删除 ${rows.length - failed.length} ${kind === "samples" ? "张图片" : kind === "tasks" ? "个采样任务" : "个数据集"}`,
    );
  try {
    if (kind === "tasks") {
      await tasks.load();
      taskOptions.value = (
        await api<{ items: Task[] }>("/tasks?realOnly=true&pageSize=100")
      ).items;
      if (!taskOptions.value.some((task) => task.id === importTaskId.value))
        importTaskId.value = "";
      if (!taskOptions.value.some((task) => task.id === assignmentTaskId.value))
        assignmentTaskId.value = "";
    }
    await reloadPage();
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function reloadPage() {
  await list.load();
  if (!list.items.value.length && list.page.value > 1 && !list.error.value) {
    list.page.value = Math.max(
      1,
      Math.ceil(list.total.value / list.pageSize.value),
    );
    await list.load();
  }
}
async function reviewRows(rows: Named[], verdict: string, note = "") {
  if (busy.value) return;
  busy.value = true;
  let saved = 0;
  const failed: string[] = [];
  for (const row of rows) {
    try {
      await post(`/samples/${row.id}/review`, {
        verdict,
        note,
        hard: Boolean(row.hard),
      });
      saved++;
    } catch (e) {
      failed.push(row.id);
      notices.error(e);
    }
  }
  selectedIds.value = failed;
  if (saved)
    notices.add(
      `已${reviewOptions.find(([value]) => value === verdict)?.[1]} ${saved} 张样本`,
    );
  await reloadPage();
  busy.value = false;
}
async function openImport() {
  const preferredTask = filterTask.value || tasks.selected;
  importPlanId.value = list.planId.value || workflow.id;
  importTaskId.value = annotationTasks.value.some((t) => t.id === preferredTask)
    ? preferredTask
    : "";
  importOpen.value = true;
}
async function assignTask(rows: Array<{ id: string }>) {
  if (!assignmentTaskId.value || busy.value) return;
  busy.value = true;
  let saved = 0;
  for (const row of rows) {
    try {
      await post(`/samples/${row.id}/task`, { taskId: assignmentTaskId.value });
      saved++;
    } catch (e) {
      notices.error(e);
    }
  }
  if (saved) notices.add(`已为 ${saved} 张图片关联采样任务，可继续标注`);
  try {
    if (sample.value) sample.value = await api(`/samples/${sample.value.id}`);
    await reloadPage();
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
const missingAnnotation = computed(() =>
  list.items.value.find(
    (row) => selectedIds.value.includes(row.id) && !annotationReady(row),
  ),
);
const text = (row: Named, key: string) =>
  row[key] === null || row[key] === undefined
    ? "未提供"
    : typeof row[key] === "object"
      ? JSON.stringify(row[key])
      : String(row[key]);
const counts = (r: Named, k: string) =>
  String((r._count as Record<string, number> | undefined)?.[k] ?? 0);
async function create(startSampling = false) {
  if (busy.value) return;
  if (
    !name.value.trim() ||
    (!isDatasetCreation.value &&
      (!Number.isInteger(target.value) || target.value < 1))
  ) {
    notices.add("请填写名称和有效的目标样本数", true);
    return;
  }
  busy.value = true;
  try {
    const isDataset = isDatasetCreation.value;
    const created = await post<Named>(isDataset ? "/datasets" : "/tasks", {
      name: name.value.trim(),
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
async function saveTask() {
  if (busy.value || !editingTask.value) return;
  busy.value = true;
  try {
    const task = editingTask.value;
    await api(`/tasks/${task.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: task.name.trim(),
        target: task.target,
        status: task.status,
      }),
    });
    await tasks.load();
    taskOptions.value = (
      await api<{ items: Task[] }>("/tasks?realOnly=true&pageSize=100")
    ).items;
    await list.load();
    editingTask.value = null;
    notices.add("采样任务已更新");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function open(row: Named, annotation = false) {
  const request = ++opening;
  const currentTab = tab.value;
  try {
    if (currentTab === "datasets") {
      const result = await api<Named>(`/datasets/${row.id}`);
      if (request !== opening || tab.value !== currentTab) return;
      dataset.value = result;
    } else {
      const result = await api<Sample>(`/samples/${row.id}`);
      if (request !== opening || tab.value !== currentTab) return;
      sample.value = result;
      annotating.value = annotation;
      reviewVerdict.value = "ACCEPT";
      reviewNote.value = "";
    }
  } catch (e) {
    notices.error(e);
  }
}
async function action(id: string, type: string) {
  if (busy.value) return;
  busy.value = true;
  try {
    if (type === "export") await post(`/datasets/${id}/export-jobs`);
    else {
      const result = await post<Named>(`/datasets/${id}/${type}`);
      if (type === "clone") dataset.value = await api(`/datasets/${result.id}`);
    }
    await list.load();
    if (dataset.value && type !== "clone")
      dataset.value = await api(`/datasets/${id}`);
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
watch(
  [() => route.query.sampleId, tab],
  ([sampleId]) => {
    if (typeof sampleId === "string" && sampleTabs.includes(tab.value))
      void open(
        { id: sampleId, name: "", createdAt: "" },
        tab.value === "annotation",
      );
  },
  { immediate: true },
);
async function selectDataset() {
  try {
    datasets.value = (
      await api<{ items: Named[] }>(
        "/datasets?status=DRAFT&realOnly=true&pageSize=100",
      )
    ).items;
  } catch (e) {
    notices.error(e);
  }
}
async function changeDatasetItem(
  sampleId: string,
  operation: "remove" | "refresh",
) {
  if (!dataset.value || busy.value) return;
  const id = dataset.value.id;
  busy.value = true;
  try {
    if (operation === "remove")
      await api(`/datasets/${id}/items/${sampleId}`, { method: "DELETE" });
    else await post(`/datasets/${id}/items`, { sampleIds: [sampleId] });
    dataset.value = await api(`/datasets/${id}`);
    await list.load();
    notices.add(
      operation === "remove"
        ? "已从数据集移除，原始图片和标注保留"
        : "已更新为最新完成的标注",
    );
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function exportFrames() {
  if (busy.value || !selectedIds.value.length) return;
  busy.value = true;
  try {
    await download(
      `/samples/export?ids=${encodeURIComponent(selectedIds.value.join(","))}`,
      `frames-${new Date().toISOString().slice(0, 10)}.zip`,
    );
    notices.add(`已导出 ${selectedIds.value.length} 张原图`);
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function addItems() {
  if (
    busy.value ||
    !datasetId.value ||
    missingAnnotation.value ||
    !selectedIds.value.length
  )
    return;
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
  const failures: Array<{ name: string; reason: string }> = [];
  try {
    for (const file of files) {
      try {
        const form = new FormData();
        form.append(
          "metadata",
          JSON.stringify({
            source: "IMPORT",
            taskId: importTaskId.value || undefined,
            planId: importPlanId.value || undefined,
            clientId: randomUUID(),
            idempotencyKey: randomUUID(),
            localSequence: 0,
            capturedAt: new Date().toISOString(),
          }),
        );
        form.append("file", file);
        await api("/samples/upload", { method: "POST", body: form });
      } catch (error) {
        failures.push({ name: file.name, reason: errorText(error) });
      }
      importProgress.value.done++;
    }
    if (files.length > failures.length) {
      sampleScope.value = "IMPORT";
      filterTask.value = importTaskId.value;
      annotationFilter.value = "";
      list.status.value = "";
      list.search.value = "";
      list.source.value = "IMPORT";
      list.realOnly.value = "true";
      list.taskId.value = importTaskId.value;
      list.annotation.value = "";
      list.page.value = 1;
      list.reviewed.value = tab.value === "review" ? "false" : "";
      list.qualityStatus.value = "";
      importOpen.value = false;
    }
    await list.load();
    const added = files.length - failures.length;
    if (added) notices.add(`已导入 ${added} 张图片，可继续标注`);
    if (failures.length)
      notices.add(
        `${failures.length} 张导入失败：${failures
          .slice(0, 3)
          .map((f) => f.name)
          .join(
            "、",
          )}${failures.length > 3 ? "…" : ""}。${failures[0]!.reason}`,
        true,
      );
  } finally {
    busy.value = false;
    importProgress.value.total = 0;
    input.value = "";
  }
}
async function review(next = false) {
  if (!sample.value || busy.value) return;
  busy.value = true;
  try {
    await post(`/samples/${sample.value.id}/review`, {
      verdict: reviewVerdict.value,
      note: reviewNote.value,
      hard: sample.value.hard,
    });
    sample.value = await api(`/samples/${sample.value.id}`);
    await reloadPage();
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
async function nextAnnotation(saved = false) {
  if (!sample.value || advancing.value) return;
  advancing.value = true;
  const id = sample.value.id;
  const index = list.items.value.findIndex((row) => row.id === id);
  const nextId = list.items.value[index + 1]?.id;
  try {
    if (saved) await list.load();
    if (list.error.value) return;
    let nextRow = list.items.value.find((row) => row.id === nextId);
    // 待标注列表保存后会收缩，最后一张后面的数据会补进当前页。
    if (!nextRow && saved && annotationFilter.value === "pending")
      nextRow =
        list.items.value[Math.max(0, index)] ??
        list.items.value.find((row) => row.id !== id);
    if (!nextRow && list.page.value * list.pageSize.value < list.total.value) {
      list.page.value++;
      await list.load();
      if (list.error.value) return;
      nextRow = list.items.value[0];
    }
    if (nextRow) await open(nextRow, true);
    else if (!saved) notices.add("已到当前筛选的最后一张");
    else {
      sample.value = null;
      if (!list.items.value.length && list.page.value > 1) await reloadPage();
      notices.add(
        list.total.value
          ? "已到当前筛选末尾，可返回列表继续选择"
          : "当前列表已全部处理，可选择产品开始训练",
      );
    }
  } catch (e) {
    notices.error(e);
  } finally {
    advancing.value = false;
  }
}
async function assignProduct() {
  if (!sample.value || !assignmentPlanId.value || busy.value) return;
  busy.value = true;
  try {
    await post(`/samples/${sample.value.id}/product`, {
      planId: assignmentPlanId.value,
    });
    sample.value = await api<Sample>(`/samples/${sample.value.id}`);
    annotating.value = true;
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function discardSample() {
  if (!sample.value || busy.value) return;
  busy.value = true;
  try {
    await post(`/samples/${sample.value.id}/review`, {
      verdict: "REJECT",
      note: "标注时弃用",
      hard: sample.value.hard,
    });
    await nextAnnotation(true);
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function saveAnnotation(next = false) {
  if (next) return nextAnnotation(true);
  try {
    if (sample.value) sample.value = await api(`/samples/${sample.value.id}`);
    await list.load();
  } catch (e) {
    notices.error(e);
  }
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
              ? "选择已完成标注的图片；训练时自动生成固定版本。"
              : tab === "samples"
                ? auth.engineer
                  ? "标注时完成图片筛选，完成后可直接用于训练。"
                  : "查看采样结果和审核状态；需要补充时按任务重新采集。"
                : tab === "tasks"
                  ? "按产品方案安排采样；工人按任务中的摆放指引完成采集。"
                  : ""
        }}
      </p>
    </div>
    <div class="heading-actions">
      <button
        v-if="tab !== 'tasks' && tab !== 'datasets'"
        :disabled="busy"
        @click="openImport"
      >
        导入图片</button
      ><button
        v-if="
          auth.engineer &&
          (tab === 'datasets' || (tab === 'tasks' && auth.admin))
        "
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
      <h2>数据集版本</h2>
    </div>
    <div class="lab-index">
      <b class="mono">{{ list.total.value }}</b
      ><span>数据集版本</span>
    </div>
    <div class="lab-flow">
      <span>整理样本</span><span>完成标注</span><span>冻结数据版本</span>
    </div>
  </section>
  <div
    v-if="['samples', 'review', 'annotation'].includes(tab)"
    class="library-view-control"
  >
    <div>
      <span class="workspace-index">{{
        tab === "annotation" ? "标注图片" : "样本图片"
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
  <section
    v-if="sampleTabs.includes(tab)"
    class="data-filters"
    aria-label="数据筛选"
  >
    <div class="filter-line">
      <span>数据来源</span>
      <div class="filter-options" role="group" aria-label="数据来源">
        <button
          v-for="[value, label] in sourceOptions"
          :key="value"
          :class="{ active: sampleScope === value }"
          :aria-pressed="sampleScope === value"
          @click="sampleScope = value!"
        >
          {{ label }}
        </button>
      </div>
    </div>
    <div class="filter-line">
      <span>标注进度</span>
      <div class="filter-options" role="group" aria-label="标注进度">
        <button
          v-for="[value, label] in [
            ['', '全部'],
            ['pending', '待标注'],
            ['complete', '已标注'],
          ]"
          :key="value"
          :class="{ active: annotationFilter === value }"
          :aria-pressed="annotationFilter === value"
          @click="annotationFilter = value!"
        >
          {{ label }}
        </button>
      </div>
      <button
        v-if="auth.engineer && ['samples', 'annotation'].includes(tab)"
        class="primary right"
        :disabled="!selectedRows.length || list.loading.value"
        @click="open(selectedRows[0]!, true)"
      >
        开始连续标注
      </button>
    </div>
  </section>
  <p
    v-if="sampleTabs.includes(tab) && workflow.current"
    class="data-next-action"
  >
    <span
      >当前只显示“{{ workflow.current.rules.product }} · V{{
        workflow.current.version
      }}”的图片与标注。</span
    >
    <RouterLink :to="{ name: 'workbench', query: { planId: workflow.id } }"
      >为此产品留样</RouterLink
    >
  </p>
  <p v-else-if="sampleTabs.includes(tab)" class="note">
    正在浏览全部产品图片。请在上方选择产品，限定本次标注与训练的数据范围。
  </p>
  <form class="toolbar" @submit.prevent="list.filter">
    <input
      v-model="list.search.value"
      type="search"
      aria-label="搜索名称"
      placeholder="搜索名称或编号…"
    />
    <UiSelect
      v-if="sampleTabs.includes(tab) && route.query.taskId"
      v-model="filterTask"
      aria-label="采样任务"
    >
      <option value="">全部采样任务</option>
      <option v-for="t in taskOptions" :key="t.id" :value="t.id">
        {{ t.name
        }}{{ t.plan ? ` · ${t.plan.rules.product}` : " · 未关联方案" }}
      </option>
    </UiSelect>
    <UiSelect
      v-if="tab === 'quality'"
      v-model="list.qualityStatus.value"
      aria-label="质量状态"
      @change="list.filter"
    >
      <option value="">全部质量</option>
      <option value="PASS">正常</option>
      <option value="WARNING">需关注</option>
    </UiSelect>
    <UiSelect
      v-model="list.status.value"
      v-if="tab !== 'annotation' && tab !== 'quality'"
      :aria-label="
        tab === 'tasks'
          ? '任务状态'
          : tab === 'datasets'
            ? '数据集状态'
            : '审核状态'
      "
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
      </option></UiSelect
    ><button
      :class="{ busy: list.loading.value }"
      :disabled="list.loading.value"
    >
      查询</button
    ><button
      type="button"
      :class="{ busy: list.loading.value }"
      :disabled="list.loading.value"
      @click="list.load"
    >
      刷新</button
    ><button
      v-if="sampleTabs.includes(tab)"
      type="button"
      @click="resetFilters"
    >
      重置筛选</button
    ><template
      v-if="gallery && ['samples', 'review', 'annotation'].includes(tab)"
      ><UiSelect
        v-model="list.sort.value"
        aria-label="排序字段"
        @change="list.filter"
      >
        <option value="createdAt">创建时间</option>
        <option value="name">名称</option>
        <option value="status">状态</option></UiSelect
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
  <div v-if="tab === 'annotation'" class="data-next-action">
    <span>完成标注即可训练；不清晰或无用的图片可直接弃用。</span
    ><RouterLink
      :to="{
        name: 'models',
        params: { tab: 'training' },
        query: { planId: list.planId.value || undefined },
      }"
      >开始训练</RouterLink
    >
  </div>
  <div
    v-if="sampleTabs.includes(tab) && auth.engineer && route.query.datasetId"
    class="data-next-action"
  >
    <label class="check-row"
      ><input
        type="checkbox"
        :checked="allChecked"
        :disabled="busy || list.loading.value"
        :indeterminate="checkedRows.length > 0 && !allChecked"
        @change="
          selectedIds = allChecked ? [] : selectedRows.map((row) => row.id)
        "
      />选择本页</label
    >
    <span>{{
      datasetId
        ? "正在为选定的数据集添加样本"
        : "选中已标注的图片，即可加入或新建数据集"
    }}</span
    ><button
      v-if="tab === 'samples'"
      :disabled="!completedOnPage.length || busy"
      @click="selectedIds = completedOnPage.map((row) => row.id)"
    >
      选择本页已标注样本
    </button>
  </div>
  <div v-if="selectedIds.length && auth.engineer" class="toolbar batch-actions">
    <span>已选 {{ selectedIds.length }} 个样本</span
    ><button @click="selectedIds = []" :disabled="busy">取消选择</button
    ><button
      v-if="sampleTabs.includes(tab)"
      :disabled="busy"
      @click="exportFrames"
    >
      导出原图</button
    ><button
      v-if="auth.admin"
      class="danger"
      :disabled="busy"
      @click="requestDelete('samples', checkedRows)"
    >
      删除所选图片
    </button>
    <button
      :disabled="busy"
      @click="reviewRows(checkedRows, 'REJECT', '标注时弃用')"
    >
      弃用所选图片
    </button>
    <details>
      <summary>高级整理</summary>
      <UiSelect v-model="assignmentTaskId" aria-label="关联到采样任务">
        <option value="">选择标注方案对应的任务</option>
        <option v-for="t in annotationTasks" :key="t.id" :value="t.id">
          {{ t.name }} · {{ t.plan?.rules.product }}
        </option>
      </UiSelect>
      <button
        :disabled="busy || !assignmentTaskId"
        @click="assignTask(checkedRows)"
      >
        关联采样任务
      </button>
      <template v-if="auth.admin"
        ><input
          v-model="batchNote"
          aria-label="批量审核备注"
          placeholder="审核备注（可选）"
          maxlength="2000"
        /><button
          v-for="[value, label] in reviewOptions"
          :key="value"
          :disabled="busy"
          @click="reviewRows(checkedRows, value!, batchNote)"
        >
          批量{{ label }}
        </button></template
      >
      <template v-if="tab === 'samples'"
        ><template v-if="missingAnnotation"
          ><span class="tone-warn">所选样本尚未完成标注</span
          ><button @click="open(missingAnnotation, true)">
            先完成标注
          </button></template
        ><UiSelect v-model="datasetId" aria-label="目标数据集">
          <option value="">选择草稿数据集</option>
          <option v-for="d in datasets" :key="d.id" :value="d.id">
            {{ displayName(d.name) }} / V{{ d.version }}
          </option></UiSelect
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
        </button></template
      >
    </details>
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
        v-for="r in selectedRows"
        :key="r.id"
        class="sample-tile"
        :class="{ selected: selectedIds.includes(r.id) }"
      >
        <div class="sample-tile-top">
          <label v-if="auth.engineer"
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
            >{{ annotationLabel(r) }}</span
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
            v-if="tab !== 'annotation'"
            class="sample-annotation-state"
            :class="{ complete: annotationReady(r) }"
            >{{ annotationLabel(r)
            }}<button
              v-if="auth.engineer"
              class="text-button"
              @click="open(r, true)"
            >
              {{ annotationReady(r) ? "编辑标注" : "去标注" }}
            </button></span
          >
          <div>
            <span
              class="tag"
              :class="{ simulated: r.source === 'SIMULATION' }"
              >{{ chinese(r.source) }}</span
            >
          </div>
          <p
            v-if="lastReview(r) && r.status === 'REVIEWED'"
            class="sample-review-note"
          >
            <b>{{ chinese(lastReview(r)!.verdict) }}</b>
            {{ lastReview(r)!.note || "无备注" }}
          </p>
          <small>{{ new Date(r.createdAt).toLocaleString() }}</small>
          <div class="sample-quick-actions row-actions">
            <template v-if="auth.admin && tab === 'review'"
              ><button
                v-for="[value, label] in reviewOptions"
                :key="value"
                class="table-action"
                :disabled="busy"
                @click="reviewRows([r], value!)"
              >
                {{ label }}
              </button></template
            >
            <button
              v-if="auth.admin"
              class="table-action danger"
              :disabled="busy"
              @click="requestDelete('samples', [r])"
            >
              删除图片
            </button>
          </div>
        </div>
      </article>
    </div>
    <div v-else class="panel table-wrap">
      <table>
        <thead>
          <tr>
            <th v-if="sampleTabs.includes(tab) && auth.engineer"></th>
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
                    : "类型"
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
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in selectedRows" :key="r.id">
            <td v-if="sampleTabs.includes(tab) && auth.engineer">
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
              ><small v-if="tab === 'datasets'" class="mono"
                >V{{ r.version }}</small
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
                annotationLabel(r)
              }}</span
              ><Status v-else :value="r.status" />
              <small v-if="lastReview(r)"
                >{{ chinese(lastReview(r)!.verdict) }} ·
                {{ lastReview(r)!.note || "无备注" }}</small
              >
            </td>
            <td v-if="tab === 'quality'">
              <InfoFields :value="r.quality" :fields="['status']" />
            </td>
            <td v-else>{{ new Date(r.createdAt).toLocaleString() }}</td>
            <td v-if="tab === 'datasets'" class="action-cell">
              <div class="row-actions">
                <button @click="open(r)" class="table-action">详情</button
                ><button
                  v-if="r.status === 'FROZEN'"
                  @click="action(r.id, 'clone')"
                  class="table-action"
                  :disabled="busy"
                >
                  创建新版本
                </button>
                <button
                  v-if="auth.admin"
                  class="table-action danger"
                  :disabled="busy"
                  @click="requestDelete('datasets', [r])"
                >
                  删除数据集
                </button>
              </div>
            </td>
            <td v-else-if="tab === 'tasks'" class="action-cell">
              <div class="row-actions">
                <button
                  v-if="auth.admin"
                  class="table-action"
                  :disabled="busy"
                  @click="editingTask = { ...r } as unknown as Task"
                >
                  编辑任务
                </button>
                <RouterLink
                  v-if="r.status === 'OPEN'"
                  class="table-action"
                  :to="{ name: 'workbench' }"
                  @click="tasks.selected = r.id"
                  >开始采样</RouterLink
                >
                <span v-else class="muted">已完成，重新开放后可采样</span>
                <RouterLink
                  :to="{
                    name: 'data',
                    params: { tab: 'samples' },
                    query: { taskId: r.id },
                  }"
                  class="table-action"
                  >查看样本</RouterLink
                >
                <button
                  v-if="auth.admin"
                  class="table-action danger"
                  :disabled="busy"
                  @click="requestDelete('tasks', [r])"
                >
                  删除任务
                </button>
              </div>
            </td>
            <td v-else class="action-cell">
              <div class="row-actions">
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
                <button
                  v-if="auth.engineer && tab !== 'annotation'"
                  class="table-action"
                  @click="open(r, true)"
                >
                  标注
                </button>
                <template v-if="auth.admin && tab === 'review'"
                  ><button
                    v-for="[value, label] in reviewOptions"
                    :key="value"
                    class="table-action"
                    :disabled="busy"
                    @click="reviewRows([r], value!)"
                  >
                    {{ label }}
                  </button></template
                >
                <button
                  v-if="auth.admin"
                  class="table-action danger"
                  :disabled="busy"
                  @click="requestDelete('samples', [r])"
                >
                  删除图片
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
  <Drawer
    v-if="editingTask"
    title="编辑采样任务"
    @close="!busy && (editingTask = null)"
  >
    <form @submit.prevent="saveTask">
      <label
        >名称<input v-model="editingTask.name" required maxlength="120"
      /></label>
      <label
        >目标样本数<input
          v-model.number="editingTask.target"
          required
          type="number"
          min="1"
          step="1"
      /></label>
      <label
        >任务状态<UiSelect v-model="editingTask.status">
          <option value="OPEN">进行中</option>
          <option value="COMPLETED">已完成</option>
        </UiSelect></label
      >
      <div class="form-actions">
        <button class="primary" :disabled="busy">保存任务</button
        ><button type="button" :disabled="busy" @click="editingTask = null">
          取消
        </button>
      </div>
    </form>
  </Drawer>
  <Drawer
    v-if="createOpen"
    :title="isDatasetCreation ? '创建数据集' : '创建采样任务'"
    @close="createOpen = false"
    ><form @submit.prevent="create(!isDatasetCreation)">
      <label>名称<input v-model="name" required maxlength="120" /></label>
      <fieldset v-if="!isDatasetCreation" class="plan-picker">
        <legend>选择产品与检查方案</legend>
        <input
          v-model="planSearch"
          type="search"
          aria-label="搜索检查方案"
          placeholder="搜索产品、方案或类别…"
        />
        <div class="plan-options">
          <label
            v-for="plan in matchingPlans"
            :key="plan.id"
            :class="{ active: taskPlanId === plan.id }"
            ><input
              type="radio"
              v-model="taskPlanId"
              :value="plan.id"
              name="task-plan"
            /><span
              ><b
                >{{ plan.rules.product }} · {{ plan.name }} / V{{
                  plan.version
                }}</b
              ><small
                >标注类别：{{ plan.rules.classes.join("、") }}</small
              ></span
            ></label
          >
        </div>
        <label class="check-row"
          ><input
            type="radio"
            v-model="taskPlanId"
            value=""
            name="task-plan"
          />独立采样（不关联方案）</label
        >
        <p v-if="!taskPlanId" class="note">
          独立采样的图片暂不能框选标注；需要标注和训练时，请选择检查方案。
        </p>
        <p v-else-if="selectedPlan" class="note">
          {{ selectedPlan.rules.instructions }}
        </p>
        <RouterLink v-if="!plans.length" to="/plans" @click="createOpen = false"
          >先创建检查方案</RouterLink
        >
      </fieldset>
      <label v-if="isDatasetCreation"
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
    :escape-closes="!annotating"
    :title="displayName(sample.name)"
    @close="sample = null"
    ><div class="toolbar">
      <span v-if="sample.source === 'SIMULATION'" class="tag simulated"
        >模拟</span
      ><button v-if="auth.engineer" @click="annotating = !annotating">
        {{ annotating ? "图像详情" : "进入标注" }}
      </button>
      <button
        v-if="auth.admin"
        class="danger right"
        :disabled="busy"
        @click="requestDelete('samples', [sample as unknown as Named])"
      >
        删除图片
      </button>
    </div>
    <div v-if="auth.engineer && !sample.plan" class="toolbar">
      <span>先关联任务即可标注：</span
      ><UiSelect v-model="assignmentTaskId" aria-label="当前图片的采样任务">
        <option value="">选择任务与产品方案</option>
        <option v-for="t in annotationTasks" :key="t.id" :value="t.id">
          {{ t.name }} · {{ t.plan?.rules.product }}
        </option></UiSelect
      ><button :disabled="busy || !assignmentPlanId" @click="assignProduct">
        关联并启用标注
      </button>
    </div>
    <AnnotationEditor
      v-if="annotating"
      :sample="sample"
      :position="annotationPosition"
      :total="annotationTotal"
      :advancing="advancing"
      @saved="saveAnnotation"
      @skip="nextAnnotation()"
      @discard="discardSample"
    />
    <div v-else class="sample-review-workspace">
      <div>
        <section
          v-if="sample.quality && tab === 'quality'"
          class="section-space"
          aria-label="图片质量指标"
        >
          <h3>图片质量 <Status :value="sample.quality.status" /></h3>
          <dl class="key-values detail-fields">
            <template v-for="[key, label] in qualityFields" :key="key"
              ><dt>{{ label }}</dt>
              <dd>
                {{ qualityValue(sample.quality.metrics[key]) }}
              </dd></template
            >
          </dl>
          <p class="note">亮度与清晰度仅供图片质量检查，不代表产品检查结论。</p>
        </section>
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
          <summary>技术信息</summary>
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
        <div class="review-choices" role="group" aria-label="审核结论">
          <button
            v-for="[value, label] in reviewOptions"
            :key="value"
            :aria-pressed="reviewVerdict === value"
            :class="{ active: reviewVerdict === value }"
            @click="reviewVerdict = value!"
          >
            {{ label }}
          </button>
        </div>
        <label class="check-row"
          ><input type="checkbox" v-model="sample.hard" />困难样本</label
        ><label
          >审核备注<textarea
            v-model="reviewNote"
            rows="3"
            maxlength="2000"
            placeholder="填写退回原因或补充说明…"
          />
        </label>
        <p
          v-if="lastReview(sample as unknown as Named)"
          class="sample-review-note"
        >
          上次审核：{{
            chinese(lastReview(sample as unknown as Named)!.verdict)
          }}
          · {{ lastReview(sample as unknown as Named)!.note || "无备注" }}
        </p>
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
                download(`/assets/${a.id}/content`, assetFilename(a)).catch(
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
          : "先加入样本并等全部样本审核通过后再锁定版本；训练至少需要 2 张已审核样本。"
      }}
    </p>
    <p v-if="dataset.status !== 'FROZEN' && !datasetReady" class="note">
      还有 {{ datasetPending }} 张样本需要审核、更新标注或移除已删除图片。
    </p>
    <p v-if="dataset.status !== 'FROZEN' && datasetItems < 2" class="note">
      当前有 {{ datasetItems }} 张样本，至少加入 2
      张已审核样本后才能锁定用于训练。
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
        :disabled="busy || !datasetReady || datasetItems < 2"
        @click="action(dataset.id, 'freeze')"
      >
        锁定版本用于训练</button
      ><RouterLink
        v-else-if="dataset.status === 'FROZEN' && datasetItems >= 2"
        class="button-link primary"
        :to="{
          name: 'models',
          params: { tab: 'training' },
          query: { planId: workflow.id || undefined },
        }"
        >查看产品训练准备</RouterLink
      >
    </div>
    <div v-if="datasetQuality" class="dataset-class-list">
      <span v-for="(count, label) in datasetQuality.classes" :key="label"
        >{{ label }} <b>{{ count }}</b></span
      >
    </div>

    <section
      v-if="datasetRows.length"
      class="section-space"
      aria-label="数据集样本"
    >
      <h3>样本与标注版本</h3>
      <p v-if="dataset.status === 'DRAFT'" class="note">
        可移除误加的图片；重新标注后，点击“更新标注”同步此草稿的快照。
      </p>
      <div v-for="item in datasetRows" :key="item.sampleId" class="list-line">
        <div>
          <b>{{ displayName(item.sample.name) }}</b>
          <small
            >标注 V{{ item.annotationSet.version }} ·
            {{
              item.sample.deletedAt
                ? "图片已删除"
                : chinese(item.sample.status)
            }}{{
              dataset.status !== "FROZEN" && item.needsUpdate
                ? " · 标注待更新"
                : ""
            }}</small
          >
        </div>
        <div v-if="dataset.status === 'DRAFT'" class="row-actions">
          <button
            v-if="!item.sample.deletedAt"
            class="table-action"
            :disabled="busy"
            @click="changeDatasetItem(item.sampleId, 'refresh')"
          >
            更新标注
          </button>
          <button
            class="table-action danger"
            :disabled="busy"
            @click="changeDatasetItem(item.sampleId, 'remove')"
          >
            移出数据集
          </button>
        </div>
      </div>
    </section>
    <div class="toolbar">
      <button
        :disabled="dataset.status !== 'FROZEN' || busy"
        @click="action(dataset.id, 'export')"
      >
        导出数据集</button
      ><button @click="action(dataset.id, 'clone')" :disabled="busy">
        创建新版本
      </button>
      <button
        v-if="auth.admin"
        class="danger"
        :disabled="busy"
        @click="requestDelete('datasets', [dataset])"
      >
        删除数据集
      </button>
    </div>
    <InfoFields
      :value="dataset"
      :fields="['name', 'version', 'status', 'createdAt']"
    />
    <details>
      <summary>技术信息</summary>
      <pre>{{ JSON.stringify(dataset, null, 2) }}</pre>
    </details>
  </Drawer>
  <Drawer
    v-if="importOpen"
    title="导入图片"
    @close="!busy && (importOpen = false)"
  >
    <label
      >图片所属产品<UiSelect v-model="importPlanId" :disabled="busy">
        <option value="">暂不选择，标注前补选</option>
        <option v-for="p in plans" :key="p.id" :value="p.id">
          {{ p.rules.product }} · {{ p.name }}
        </option>
      </UiSelect></label
    >
    <p class="note">导入后即可标注，无需先创建采样任务。</p>
    <button class="primary" :disabled="busy" @click="importInput?.click()">
      {{
        importProgress.total
          ? `正在导入 ${importProgress.done}/${importProgress.total}`
          : "选择图片并导入（可多选）"
      }}</button
    ><input
      ref="importInput"
      type="file"
      hidden
      multiple
      accept="image/jpeg,image/png,image/webp"
      :disabled="busy"
      @change="upload"
    />
  </Drawer>
  <Drawer
    v-if="deleteRequest"
    :title="
      deleteRequest.kind === 'samples'
        ? '删除图片'
        : deleteRequest.kind === 'tasks'
          ? '删除采样任务'
          : '删除数据集'
    "
    @close="!busy && (deleteRequest = null)"
  >
    <p>
      确认删除{{
        deleteRequest.rows.length > 1
          ? `所选 ${deleteRequest.rows.length} 张图片`
          : `“${displayName(deleteRequest.rows[0]!.name)}”`
      }}？
    </p>
    <p class="note">
      {{
        deleteRequest.kind === "samples"
          ? "图片将从样本库移除；数据集已记录的样本快照会保留。"
          : deleteRequest.kind === "tasks"
            ? "任务将从任务列表和采样选项中移除，不能继续向其采样或导入图片。已有图片、标注、数据集及检测记录保留。"
            : "删除此数据集及其样本关联，原始图片保留。已用于训练、评估或正在导出的数据集不能删除。此操作不能撤销。"
      }}
    </p>
    <div class="form-actions">
      <button class="danger" :disabled="busy" @click="deleteRows">
        {{ busy ? "正在删除…" : "确认删除" }}</button
      ><button :disabled="busy" @click="deleteRequest = null">取消</button>
    </div>
  </Drawer>
</template>
<style scoped>
.plan-picker {
  border: 0;
  padding: 0;
  margin: 18px 0;
  min-width: 0;
}
.plan-picker legend {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
}
.plan-options {
  max-height: 280px;
  overflow-y: auto;
  margin: 10px 0;
  display: grid;
  gap: 8px;
}
.plan-options label {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border: 1px solid var(--line);
  padding: 12px;
  margin: 0;
  cursor: pointer;
}
.plan-options label.active {
  border-color: var(--forest);
  background: var(--surface-2);
}
.plan-options input {
  width: auto;
  margin: 3px 0 0;
  flex-shrink: 0;
}
.plan-options small {
  display: block;
  margin-top: 6px;
  color: var(--muted);
}
.data-filters {
  padding: 14px 18px;
  border: 1px solid var(--line);
  background: var(--surface);
  margin-bottom: 12px;
}
.filter-line {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.filter-line + .filter-line {
  margin-top: 12px;
}
.filter-line > span {
  color: var(--muted);
  font-size: 12px;
  min-width: 52px;
}
.filter-options,
.review-choices {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.filter-options button,
.review-choices button {
  padding: 7px 12px;
}
.filter-options button.active,
.review-choices button.active {
  background: var(--forest);
  border-color: var(--forest);
  color: var(--surface);
}
.review-choices {
  margin-bottom: 16px;
}
.sample-review-note {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
  overflow-wrap: anywhere;
  margin: 10px 0;
}
.sample-quick-actions {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}
.sample-quick-actions .danger {
  margin-left: auto;
}
.batch-actions {
  position: sticky;
  top: 8px;
  z-index: 4;
  background: var(--surface);
  box-shadow: 0 4px 16px #0001;
}
.toolbar select {
  max-width: 320px;
}
@media (max-width: 760px) {
  .filter-line {
    gap: 8px;
  }
  .filter-options {
    flex: 1;
  }
  .filter-line > .primary {
    margin-left: 0;
  }
  .batch-actions {
    position: static;
  }
  .toolbar select {
    max-width: 100%;
  }
}
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
