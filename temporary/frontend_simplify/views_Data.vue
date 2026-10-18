<script setup lang="ts">
import InfoFields from "../components/InfoFields.vue";
import { chinese, displayName } from "@vision/shared";
import { ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import type { Named, Sample } from "../types";
import { useList } from "../composables/useList";
import { api, post, download } from "../api";
import { useNotificationStore } from "../stores/notifications";
import { useAuthStore } from "../stores/auth";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import SortableTh from "../components/SortableTh.vue";
import Pager from "../components/Pager.vue";
import Drawer from "../components/Drawer.vue";
import ImageViewer from "../components/ImageViewer.vue";
import AnnotationEditor from "../components/AnnotationEditor.vue";
const route = useRoute(),
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
watch(
  tab,
  () => {
    list.reviewed.value = tab.value === "review" ? "false" : "";
    list.status.value = "";
    list.filter();
  },
  { immediate: true },
);
const selectedRows = computed(() => list.items.value);
const text = (row: Named, key: string) =>
  row[key] === null || row[key] === undefined
    ? "—"
    : typeof row[key] === "object"
      ? JSON.stringify(row[key])
      : String(row[key]);
const counts = (r: Named, k: string) =>
  String((r._count as Record<string, number> | undefined)?.[k] ?? 0);
async function create() {
  busy.value = true;
  try {
    await post(endpoint.value, {
      name: name.value,
      ...(tab.value === "datasets"
        ? { version: version.value }
        : { target: target.value }),
    });
    createOpen.value = false;
    name.value = "";
    await list.load();
    notices.add("记录已创建");
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
      await api<{ items: Named[] }>("/datasets?status=DRAFT")
    ).items;
  } catch (e) {
    notices.error(e);
  }
}
async function addItems() {
  if (!datasetId.value) return;
  busy.value = true;
  try {
    await post(`/datasets/${datasetId.value}/items`, {
      sampleIds: selectedIds.value,
    });
    selectedIds.value = [];
    notices.add("已加入数据集，标注版本已记录");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function upload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  busy.value = true;
  try {
    const form = new FormData();
    form.append(
      "metadata",
      JSON.stringify({
        source: "IMPORT",
        clientId: crypto.randomUUID(),
        idempotencyKey: crypto.randomUUID(),
        localSequence: 0,
        capturedAt: new Date().toISOString(),
      }),
    );
    form.append("file", file);
    await api("/samples/upload", { method: "POST", body: form });
    await list.load();
    notices.add("原图已导入");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function review() {
  if (!sample.value) return;
  busy.value = true;
  try {
    await post(`/samples/${sample.value.id}/review`, {
      verdict: reviewVerdict.value,
      note: reviewNote.value,
      hard: sample.value.hard,
    });
    sample.value = await api(`/samples/${sample.value.id}`);
    await list.load();
    notices.add("样本审核已保存");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function saveAnnotation() {
  if (sample.value) sample.value = await api(`/samples/${sample.value.id}`);
  await list.load();
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
        >导入图片<input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style="display: none"
          @change="upload"
          :disabled="busy" /></label
      ><button
        v-if="auth.engineer && ['tasks', 'datasets'].includes(tab)"
        class="primary"
        @click="createOpen = true"
      >
        {{ tab === "tasks" ? "创建任务" : "创建数据集" }}
      </button>
    </div>
  </div>
  <form class="toolbar" @submit.prevent="list.filter">
    <input v-model="list.search.value" placeholder="搜索名称…" /><select
      v-model="list.source.value"
      v-if="!['tasks', 'datasets'].includes(tab)"
    >
      <option value="">全部来源</option>
      <option value="BOARD">{{ chinese("BOARD") }}</option>
      <option value="MOBILE">{{ chinese("MOBILE") }}</option>
      <option value="IMPORT">{{ chinese("IMPORT") }}</option>
      <option value="SIMULATION">{{ chinese("SIMULATION") }}</option></select
    ><select v-model="list.status.value">
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
    ><span class="right inline-count">{{ list.total.value }} 条记录</span>
  </form>
  <div v-if="selectedIds.length && auth.engineer" class="toolbar">
    <span>已选 {{ selectedIds.length }} 个样本</span
    ><button @click="selectDataset">加入数据集</button
    ><select v-if="datasets.length" v-model="datasetId">
      <option value="">选择草稿数据集</option>
      <option v-for="d in datasets" :key="d.id" :value="d.id">
        {{ displayName(d.name) }} / V{{ d.version }}
      </option></select
    ><button
      v-if="datasetId"
      class="primary"
      @click="addItems"
      :disabled="busy"
    >
      确认加入
    </button>
  </div>
  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!selectedRows.length"
    :hint="
      tab === 'review'
        ? '没有待审核的样本。采样后样本会先落到这里，审核通过才能进数据集。'
        : '还没有样本。用「导入图片」上传，或到移动端做一次板端采样。'
    "
    @retry="list.load"
    ><div class="panel table-wrap">
      <table>
        <thead>
          <tr>
            <th v-if="!['tasks', 'datasets'].includes(tab)"></th>
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
            <td v-if="!['tasks', 'datasets'].includes(tab)">
              <input
                type="checkbox"
                v-model="selectedIds"
                :value="r.id"
                :aria-label="`选择 ${r.name}`"
              />
            </td>
            <td>
              <strong>{{ displayName(r.name) }}</strong
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
            <td><Status :value="r.status" /></td>
            <td v-if="tab === 'quality'">
              <InfoFields :value="r.quality" :fields="['status']" />
            </td>
            <td v-else>{{ new Date(r.createdAt).toLocaleString() }}</td>
            <td v-if="tab === 'datasets'">
              <button @click="open(r)" class="table-action">详情</button
              ><button
                v-if="r.status !== 'FROZEN'"
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
              <RouterLink :to="{ name: 'workbench' }">进入采样</RouterLink>
            </td>
            <td v-else>
              <button
                @click="open(r, tab === 'annotation')"
                class="table-action"
              >
                {{ tab === "annotation" ? "标注" : "查看" }}
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
    :title="tab === 'tasks' ? '创建采样任务' : '创建数据集'"
    @close="createOpen = false"
    ><form @submit.prevent="create">
      <label>名称<input v-model="name" required maxlength="120" /></label
      ><label v-if="tab === 'datasets'"
        >版本<input type="number" min="1" v-model.number="version" /></label
      ><label v-else
        >目标样本数<input
          type="number"
          min="1"
          v-model.number="target" /></label
      ><button class="primary" :disabled="busy">创建</button>
    </form></Drawer
  ><Drawer
    v-if="sample"
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
        ><button @click="adjacent(-1)">上一张</button
        ><button @click="adjacent(1)">下一张</button></template
      >
    </div>
    <AnnotationEditor
      v-if="annotating"
      :sample="sample"
      @saved="saveAnnotation"
    /><template v-else
      ><ImageViewer
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
      <h3>样本审核</h3>
      <label
        >结论<select v-model="reviewVerdict">
          <option value="ACCEPT">接纳样本</option>
          <option value="REJECT">拒绝样本</option>
          <option value="NEEDS_WORK">待补充</option>
        </select></label
      ><label class="check-row"
        ><input type="checkbox" v-model="sample.hard" />困难样本</label
      ><label>备注<textarea v-model="reviewNote" rows="2" /></label
      ><button @click="review" class="primary" :disabled="busy">
        保存样本审核
      </button>
      <h3 class="section-space">资产证据</h3>
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
      <RouterLink :to="{ name: 'records' }"
        >前往检测记录审核</RouterLink
      ></template
    ></Drawer
  ><Drawer
    v-if="dataset"
    :title="`${displayName(dataset.name)} / V${dataset.version}`"
    @close="dataset = null"
    ><Status :value="dataset.status" />

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
