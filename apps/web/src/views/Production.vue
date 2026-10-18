<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type {
  InspectionBatch,
  BatchSummary,
  Inspection,
  Page,
  Model,
} from "@vision/contracts";
import { api, post, download, errorText, RequestError } from "../api";
import { useDeviceStore } from "../stores/devices";
import { useTaskStore } from "../stores/tasks";
import { useAuthStore } from "../stores/auth";
import ImageViewer from "../components/ImageViewer.vue";
import InspectionDetail from "../components/InspectionDetail.vue";
import Status from "../components/Status.vue";
import Drawer from "../components/Drawer.vue";

const devices = useDeviceStore(),
  tasks = useTaskStore(),
  auth = useAuthStore();
const batches = ref<InspectionBatch[]>([]),
  selected = ref(""),
  summary = ref<BatchSummary | null>(null),
  records = ref<Inspection[]>([]);
const busy = ref(false),
  loading = ref(false),
  error = ref(""),
  message = ref(""),
  creating = ref(false),
  closing = ref(false);
const name = ref(""),
  target = ref(100),
  confidence = ref(0.7),
  qualityGate = ref(true),
  detail = ref<Inspection | null>(null);
const now = ref(Date.now());
const execution = ref<"HOST" | "TERMINAL">("HOST"),
  modelId = ref("");
const models = ref<Model[]>([]);
const connectionEditing = ref(false),
  connectionServer = ref("");
const connectionAddresses = ref<
  { url: string; interfaceName: string; address: string }[]
>([]);
const batch = computed(() =>
  batches.value.find((b) => b.id === selected.value),
);
const preview = computed(() =>
  devices.current ? devices.previews[devices.current.id] : null,
);
const stale = computed(
  () =>
    !preview.value || now.value - Date.parse(preview.value.receivedAt) > 3000,
);
const currentTask = computed(() =>
  tasks.items.find((t) => t.id === tasks.selected),
);
const blocked = computed(() =>
  pendingCheck.value
    ? ""
    : !batch.value
      ? "请选择或新建作业批次"
      : batch.value.status !== "OPEN"
        ? "批次已结束"
        : batch.value.execution === "TERMINAL"
          ? "请在板端终端执行检查，记录联网后同步到此处"
          : devices.current?.id !== batch.value.deviceId
            ? "请选择批次对应的设备"
            : devices.current?.connectionState !== "ONLINE"
              ? "设备未连接"
              : stale.value
                ? "正在等待有效的实时画面"
                : "",
);
const latest = computed(() => records.value[0]);
let timer: ReturnType<typeof setInterval> | undefined,
  revision = 0;
const pendingCheck = ref<{
  batchId: string;
  idempotencyKey: string;
  clientId: string;
  localSequence: number;
} | null>(null);
let batchRevision = 0;
const clientId = crypto.randomUUID();
let sequence = 0;
const pendingKey = "vision.production.pending";
try {
  const saved = JSON.parse(sessionStorage.getItem(pendingKey) ?? "null");
  if (
    saved &&
    typeof saved.batchId === "string" &&
    typeof saved.idempotencyKey === "string" &&
    typeof saved.clientId === "string" &&
    Number.isInteger(saved.localSequence)
  )
    pendingCheck.value = saved;
} catch {
  sessionStorage.removeItem(pendingKey);
}
async function loadBatches() {
  const current = ++batchRevision;
  const deviceId = devices.current?.id;
  let recovering: InspectionBatch | null = null;
  if (pendingCheck.value) {
    recovering = await api<InspectionBatch>(
      `/batches/${encodeURIComponent(pendingCheck.value.batchId)}`,
    );
    if (current !== batchRevision) return;
    if (
      devices.devices.some((d) => d.id === recovering!.deviceId) &&
      devices.selected !== recovering.deviceId
    ) {
      devices.selected = recovering.deviceId;
      return;
    }
  }
  const list = await api<Page<InspectionBatch>>(
    `/batches?pageSize=100${deviceId ? `&deviceId=${encodeURIComponent(deviceId)}` : ""}`,
  );
  if (current !== batchRevision) return;
  batches.value = list.items;
  if (recovering && !batches.value.some((b) => b.id === recovering!.id))
    batches.value.unshift(recovering);
  if (
    pendingCheck.value &&
    batches.value.some((b) => b.id === pendingCheck.value!.batchId)
  )
    selected.value = pendingCheck.value.batchId;
  else if (!batches.value.some((b) => b.id === selected.value))
    selected.value =
      batches.value.find((b) => b.status === "OPEN")?.id ??
      batches.value[0]?.id ??
      "";
}
async function refresh() {
  const id = selected.value,
    current = ++revision;
  if (!id) {
    summary.value = null;
    records.value = [];
    return;
  }
  loading.value = true;
  try {
    const [stats, list] = await Promise.all([
      api<BatchSummary>(`/batches/${id}/summary`),
      api<Page<Inspection>>(
        `/inspections?batchId=${encodeURIComponent(id)}&pageSize=20`,
      ),
    ]);
    if (current === revision) {
      summary.value = stats;
      records.value = list.items;
    }
  } catch (e) {
    if (current === revision) error.value = errorText(e);
  } finally {
    if (current === revision) loading.value = false;
  }
}
async function create() {
  if (!devices.current || !tasks.selected || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const created = await post<InspectionBatch>("/batches", {
      name: name.value,
      deviceId: devices.current.id,
      taskId: tasks.selected,
      target: target.value,
      execution: execution.value,
      ...(execution.value === "TERMINAL" ? { modelId: modelId.value } : {}),
      acceptance: {
        confidence: confidence.value,
        qualityGate: qualityGate.value,
      },
    });
    creating.value = false;
    await loadBatches();
    selected.value = created.id;
    message.value = "批次已建立，模型、方案和判定参数已固定";
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function check() {
  if (busy.value || blocked.value) return;
  busy.value = true;
  error.value = "";
  message.value = "";
  if (!pendingCheck.value)
    pendingCheck.value = {
      batchId: selected.value,
      clientId,
      localSequence: ++sequence,
      idempotencyKey: crypto.randomUUID(),
    };
  sessionStorage.setItem(pendingKey, JSON.stringify(pendingCheck.value));
  const { batchId, ...request } = pendingCheck.value;
  try {
    await post(`/batches/${batchId}/check`, request);
    pendingCheck.value = null;
    sessionStorage.removeItem(pendingKey);
    message.value = "本件检查与证据已保存";
    await refresh();
  } catch (e) {
    if (e instanceof RequestError && e.status < 500) {
      pendingCheck.value = null;
      sessionStorage.removeItem(pendingKey);
      error.value = errorText(e);
    } else
      error.value = `${errorText(e)}。再次点击将核对同一次检查，避免重复记件。`;
  } finally {
    busy.value = false;
  }
}
async function close() {
  if (!batch.value || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await post(`/batches/${batch.value.id}/close`, { confirm: true });
    closing.value = false;
    await loadBatches();
    await refresh();
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function openRecord(id: string) {
  try {
    detail.value = await api<Inspection>(`/inspections/${id}`);
  } catch (e) {
    error.value = errorText(e);
  }
}
async function connectionFile() {
  if (!batch.value) return;
  busy.value = true;
  error.value = "";
  try {
    const credential = await post<{
      deviceId: string;
      token: string;
      expiresAt: string;
      server: string;
    }>(`/terminal/${batch.value.deviceId}/credential`, {
      confirm: true,
      server: connectionServer.value,
    });
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(credential, null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "connection.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    connectionEditing.value = false;
    message.value =
      "连接配置已下载，请放入板端状态目录。该文件包含设备凭据，重新生成会使旧凭据失效。";
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function reviewed() {
  const id = detail.value?.id;
  await refresh();
  if (id) await openRecord(id);
}
function keyboard(event: KeyboardEvent) {
  if (
    event.key === "F5" &&
    !creating.value &&
    !connectionEditing.value &&
    !closing.value &&
    !detail.value
  ) {
    event.preventDefault();
    if (!event.repeat) void check();
  }
}
watch(selected, () => {
  void refresh();
});
watch(
  () => devices.current?.id,
  () => {
    if (!busy.value)
      void loadBatches().catch((e) => (error.value = errorText(e)));
  },
);
watch(
  () => devices.recent[0],
  (event) => {
    if (
      event?.type.startsWith("batch.") ||
      event?.type === "inspection.reviewed"
    )
      void loadBatches()
        .then(refresh)
        .catch((e) => (error.value = errorText(e)));
  },
);
onMounted(async () => {
  timer = setInterval(() => (now.value = Date.now()), 500);
  window.addEventListener("keydown", keyboard);
  try {
    await tasks.load();
    if (auth.engineer) {
      connectionAddresses.value = await api("/terminal/addresses");
      connectionServer.value =
        connectionAddresses.value.find((a) => a.address.startsWith("169.254."))
          ?.url ??
        connectionAddresses.value[0]?.url ??
        "";
    }
    if (auth.engineer)
      models.value = (
        await api<Page<Model>>(
          "/models?source=IMPORT&status=APPROVED&pageSize=100",
        )
      ).items;
    await loadBatches();
  } catch (e) {
    error.value = errorText(e);
  }
});
onUnmounted(() => {
  clearInterval(timer);
  window.removeEventListener("keydown", keyboard);
});
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>检测作业</h1>
      <p>按批次检查实物，保存判定依据与处理结果</p>
    </div>
    <RouterLink :to="{ name: 'workbench' }">采样与设备画面</RouterLink>
  </div>
  <div class="toolbar">
    <label
      >设备<select
        v-model="devices.selected"
        :disabled="busy || !!pendingCheck"
      >
        <option v-for="d in devices.devices" :key="d.id" :value="d.id">
          {{ d.name }}
        </option>
      </select></label
    >
    <label
      >作业批次<select
        v-model="selected"
        :disabled="busy || !!pendingCheck"
        @change="
          message = '';
          error = '';
        "
      >
        <option value="">请选择批次</option>
        <option v-for="b in batches" :key="b.id" :value="b.id">
          {{ b.name }} · {{ b.status === "OPEN" ? "进行中" : "已结束" }}
        </option>
      </select></label
    >
    <button
      v-if="auth.engineer"
      :disabled="
        busy || !devices.current || batches.some((b) => b.status === 'OPEN')
      "
      @click="
        creating = true;
        name = '';
        error = '';
      "
    >
      新建批次
    </button>
    <button
      :disabled="busy || loading"
      @click="
        loadBatches()
          .then(refresh)
          .catch((e) => (error = errorText(e)))
      "
    >
      刷新记录
    </button>
    <button
      v-if="auth.engineer && batch?.status === 'OPEN'"
      :disabled="busy || !!pendingCheck"
      @click="closing = true"
    >
      结束批次
    </button>
    <template
      v-if="
        auth.engineer &&
        batch?.execution === 'TERMINAL' &&
        batch.status === 'OPEN'
      "
    >
      <button
        :disabled="busy"
        @click="
          download(
            `/batches/${batch.id}/package`,
            `vision-job-${batch.id}.zip`,
          ).catch((e) => (error = errorText(e)))
        "
      >
        下载板端作业包
      </button>
      <button :disabled="busy" @click="connectionEditing = true">
        生成终端连接配置
      </button>
    </template>
  </div>
  <p v-if="error" role="alert" class="error-box">{{ error }}</p>
  <p v-if="message" role="status" class="note">{{ message }}</p>
  <div v-if="summary" class="production-stats" aria-label="本批次统计">
    <div>
      <span>已检查 / 目标</span
      ><strong>{{ summary.total }} / {{ batch?.target }}</strong>
    </div>
    <div>
      <span>符合要求</span><strong>{{ summary.final.PASS }}</strong>
    </div>
    <div>
      <span>不符合要求</span><strong>{{ summary.final.FAIL }}</strong>
    </div>
    <div>
      <span>待处理</span><strong>{{ summary.pending }}</strong>
    </div>
    <div>
      <span>已判定件合格率</span
      ><strong>{{
        summary.passRate === null
          ? "—"
          : `${(summary.passRate * 100).toFixed(1)}%`
      }}</strong>
    </div>
  </div>
  <div class="production-grid">
    <section class="panel">
      <div class="toolbar">
        <strong>现场画面</strong
        ><Status :value="devices.current?.connectionState" /><span
          class="right"
          >{{ stale ? "画面已超时或尚未到达" : "实时" }}</span
        >
      </div>
      <button
        class="primary"
        :disabled="busy || !!blocked"
        :aria-busy="busy"
        @click="check"
      >
        {{
          busy
            ? "正在保存本件…"
            : pendingCheck
              ? "核对上次检查"
              : "检查一件 · F5"
        }}
      </button>
      <ImageViewer
        compact
        operator
        :jpeg="preview?.jpeg"
        :boxes="stale ? [] : preview?.detections"
        :width="preview?.width"
        :height="preview?.height"
        :region="batch?.snapshot.rules.region"
      />
      <p class="note">
        {{
          preview
            ? `画面 #${preview.frameId} · ${new Date(preview.receivedAt).toLocaleTimeString()}`
            : "连接设备并开启检测后接收画面"
        }}。检查将取得一张新的完整帧。
      </p>
      <p class="note">
        {{ blocked || "每次触发保存一件，连续视频帧不自动累计。" }}
      </p>
    </section>
    <section class="panel" aria-live="polite">
      <h2>最近一件</h2>
      <template v-if="latest"
        ><Status :value="latest.result" />
        <p>{{ latest.reason }}</p>
        <table v-if="latest.metadata?.decision?.findings.length">
          <thead>
            <tr>
              <th>检查项</th>
              <th>要求</th>
              <th>确认</th>
              <th>待确认</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in latest.metadata.decision.findings" :key="f.classId">
              <td>{{ f.label }}</td>
              <td>{{ f.min === f.max ? f.min : `${f.min}–${f.max}` }}</td>
              <td>{{ f.count }}</td>
              <td>{{ f.uncertain }}</td>
            </tr>
          </tbody>
        </table>
        <button @click="openRecord(latest.id)">查看本件证据与复核</button>
      </template>
      <p v-else class="note">本批次尚未检查实物。</p>
      <template v-if="batch"
        ><hr />
        <h3>本批次执行条件</h3>
        <p>
          {{ batch.snapshot.planName }} · 版本 {{ batch.snapshot.planVersion }}
        </p>
        <p>{{ batch.snapshot.rules.instructions }}</p>
        <p>{{ batch.snapshot.rules.conditions }}</p>
        <p class="note">
          模型 {{ batch.snapshot.modelVersion }} · 判定阈值
          {{ batch.snapshot.acceptance.confidence }} ·
          {{
            batch.snapshot.acceptance.qualityGate
              ? "检查图像质量"
              : "不以图像质量拦截判定"
          }}
        </p></template
      >
    </section>
  </div>
  <section class="panel table-wrap">
    <div class="toolbar">
      <h2>本批次最近记录</h2>
      <span class="right">机器原判与人工结论分别保留</span>
    </div>
    <table>
      <thead>
        <tr>
          <th>时间</th>
          <th>机器判定</th>
          <th>人工结论</th>
          <th>原因</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="record in records" :key="record.id">
          <td>{{ new Date(record.createdAt).toLocaleTimeString() }}</td>
          <td><Status :value="record.result" /></td>
          <td>
            <Status
              v-if="record.reviewResult"
              :value="record.reviewResult"
            /><span v-else>—</span>
          </td>
          <td>{{ record.reason }}</td>
          <td><button @click="openRecord(record.id)">查看与复核</button></td>
        </tr>
        <tr v-if="!records.length">
          <td colspan="5">暂无作业记录</td>
        </tr>
      </tbody>
    </table>
  </section>
  <Drawer
    v-if="creating"
    title="新建作业批次"
    @close="!busy && (creating = false)"
    ><form @submit.prevent="create">
      <p class="note">
        建立后固定当前模型、方案及判定条件。同一设备同时只执行一个批次。
      </p>
      <label
        >批次名称<input
          v-model="name"
          required
          maxlength="120"
          placeholder="例如：包装核对 · 上午批次" /></label
      ><label
        >使用任务<select v-model="tasks.selected" required>
          <option value="" disabled>选择已有检查方案的任务</option>
          <option
            v-for="task in tasks.items.filter((t) => t.planId)"
            :key="task.id"
            :value="task.id"
          >
            {{ task.name }}
          </option>
        </select></label
      >
      <p v-if="currentTask?.plan" class="note">
        {{ currentTask.plan.rules.instructions }}
      </p>
      <label
        >执行位置<select v-model="execution">
          <option value="HOST">平台采集检查</option>
          <option value="TERMINAL">板端独立检测终端</option>
        </select></label
      >
      <label v-if="execution === 'TERMINAL'"
        >执行模型<select v-model="modelId" required>
          <option value="" disabled>选择已批准的真实板卡模型</option>
          <option v-for="model in models" :key="model.id" :value="model.id">
            {{ model.name }} · {{ model.version }}
          </option>
        </select></label
      >
      <label
        >目标件数<input
          v-model.number="target"
          type="number"
          min="1"
          max="10000000"
          required /></label
      ><label
        >确认目标的置信度<input
          v-model.number="confidence"
          type="number"
          min="0.35"
          max="0.99"
          step="0.01"
          required /></label
      ><label class="check-row"
        ><input
          v-model="qualityGate"
          type="checkbox"
        />图像质量异常时转人工复核</label
      >
      <p v-if="error" role="alert" class="error-box">{{ error }}</p>
      <button class="primary" :disabled="busy || !tasks.selected">
        {{ busy ? "建立中…" : "建立批次" }}
      </button>
    </form></Drawer
  >
  <Drawer
    v-if="closing"
    title="结束作业批次"
    @close="!busy && (closing = false)"
    ><p>结束“{{ batch?.name }}”后不能继续记件，已有证据和待复核记录保留。</p>
    <p v-if="summary?.pending">
      仍有 {{ summary.pending }} 件待处理，可在结束后继续复核。
    </p>
    <button class="primary" :disabled="busy" @click="close">
      确认结束批次
    </button></Drawer
  >
  <Drawer v-if="detail" title="单件证据与复核" wide @close="detail = null"
    ><InspectionDetail :key="detail.id" :inspection="detail" @saved="reviewed"
  /></Drawer>
  <Drawer
    v-if="connectionEditing"
    title="终端连接配置"
    @close="!busy && (connectionEditing = false)"
    ><form @submit.prevent="connectionFile">
      <p>
        选择板卡能访问的电脑网卡地址。生成后旧设备凭据失效，新凭据有效期为 30
        天。
      </p>
      <label
        >平台服务地址<input
          v-model="connectionServer"
          type="url"
          required
          list="terminal-addresses"
          placeholder="http://电脑网卡地址:3000" /></label
      ><datalist id="terminal-addresses">
        <option
          v-for="address in connectionAddresses"
          :key="address.url"
          :value="address.url"
        >
          {{ address.interfaceName }}
        </option>
      </datalist>
      <p class="note">
        下载文件包含设备凭据，请保存到板端状态目录，避免公开分享。
      </p>
      <p v-if="error" role="alert" class="error-box">{{ error }}</p>
      <button class="primary" :disabled="busy">生成新凭据并下载</button>
    </form></Drawer
  >
</template>

<style scoped>
.production-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}
.production-stats div {
  display: grid;
  gap: 0.4rem;
}
.production-stats strong {
  font-size: 1.5rem;
  font-variant-numeric: tabular-nums;
}
.production-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
  gap: 1rem;
  margin: 1rem 0;
}
.production-grid .panel {
  min-width: 0;
  padding: 1rem;
}
.production-grid :deep(.image-stage) {
  height: min(42vh, 416px);
  min-height: 260px;
  aspect-ratio: auto;
}
label {
  display: grid;
  gap: 0.4rem;
}
form {
  display: grid;
  gap: 1rem;
}
@media (max-width: 850px) {
  .production-grid {
    grid-template-columns: 1fr;
  }
  .production-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
