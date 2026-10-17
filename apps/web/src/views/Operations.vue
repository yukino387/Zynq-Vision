<script setup lang="ts">
import { chinese, displayName, errorMessage } from "@vision/shared";
import { ref, computed, onMounted, watch } from "vue";
import type { Inspection } from "../types";
import { post } from "../api";
import { useAuthStore } from "../stores/auth";
import { useDeviceStore } from "../stores/devices";
import { useTaskStore } from "../stores/tasks";
import { useInspectionStore } from "../stores/inspections";
import { useNotificationStore } from "../stores/notifications";
import type { Preview } from "../stores/devices";
import Sparkline from "../components/Sparkline.vue";
import ImageViewer from "../components/ImageViewer.vue";
import Status from "../components/Status.vue";

const auth = useAuthStore(),
  devices = useDeviceStore(),
  tasks = useTaskStore(),
  inspections = useInspectionStore(),
  notices = useNotificationStore(),
  busy = ref(false),
  connecting = ref(false);
const clientId = crypto.randomUUID();
let sequence = 0;
const device = computed(() => devices.current),
  preview = computed(() =>
    device.value?.connectionState === "ONLINE"
      ? devices.previews[device.value.id]
      : null,
  );
const queue = computed(() => inspections.items);
const currentTask = computed(() =>
  tasks.items.find((task) => task.id === tasks.selected),
);
const taskPlan = computed(() => currentTask.value?.plan);
const inspecting = computed(
  () => device.value?.reportedState.inspectionEnabled === true,
);
const frames = ref<Preview[]>([]),
  held = ref<Preview | null>(null);
let lastFilmstripAt = 0;
watch(
  () => device.value?.id,
  () => {
    frames.value = [];
    held.value = null;
    lastFilmstripAt = 0;
  },
);
watch(preview, (frame) => {
  if (!frame || Date.now() - lastFilmstripAt < 1000) return;
  lastFilmstripAt = Date.now();
  frames.value = [...frames.value, frame].slice(-8);
});
const shown = computed(() => held.value ?? preview.value);
const detections = computed(() => shown.value?.detections ?? null);
const latency = computed(() =>
  devices.history.map((h) =>
    h.inferenceUs === null ? null : h.inferenceUs / 1000,
  ),
);
const metric = (v: number | null | undefined) =>
  v == null ? "—" : (v / 1000).toFixed(2);
/** 采样按钮为什么点不了，要说出来而不是只把它变灰。 */
const captureBlocked = computed(() => {
  if (!device.value) return "没有选中设备。";
  if (device.value.connectionState !== "ONLINE")
    return `设备当前${chinese(device.value.connectionState)}，无法采样。`;
  if (!device.value.capabilities.capture) return "该设备不支持采集。";
  if (device.value.runtimeState === "READY")
    return "检测已暂停，请先开始检测。";
  if (!preview.value) return "正在等待设备画面…";
  return "";
});
async function load() {
  try {
    await inspections.load("?pageSize=5");
  } catch (e) {
    notices.error(e);
  }
}
onMounted(load);
watch(
  () => devices.recent[0],
  (event) => {
    if (event?.type === "device.inspection.completed") void load();
  },
);
async function capture() {
  if (!device.value) return;
  busy.value = true;
  try {
    await post<{ inspections: Inspection[] }>("/samples/capture", {
      deviceId: device.value.id,
      taskId: tasks.selected || undefined,
      clientId,
      localSequence: ++sequence,
      idempotencyKey: crypto.randomUUID(),
    });
    // 采样后留在工作台：新的一行落到「最近检测」顶部，不把操作工从实时画面上带走。
    notices.add("样本与检测记录已保存");
    await load();
    await tasks.load();
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function connect() {
  if (!device.value) return;
  connecting.value = true;
  try {
    await post(`/devices/${device.value.id}/connect`);
    await devices.snapshot();
    notices.add("设备已连接");
  } catch (e) {
    notices.error(e);
  } finally {
    connecting.value = false;
  }
}
async function control(start: boolean) {
  if (!device.value) return;
  connecting.value = true;
  try {
    if (start && device.value.type === "ZYNQ")
      await post(`/devices/${device.value.id}/commands`, {
        type: "CAMERA_ONLY",
        value: 0,
      });
    await post(`/devices/${device.value.id}/commands`, {
      type: start ? "START_INSPECTION" : "STOP_INSPECTION",
    });
    await devices.snapshot();
    notices.add(start ? "检测已开始" : "检测已暂停");
  } catch (e) {
    notices.error(e);
  } finally {
    connecting.value = false;
  }
}
</script>
<template>
  <div class="page-heading instrument-heading">
    <div>
      <span class="workspace-index">现场使用 / 采样与反馈</span>
      <h1>现场工作台<span class="heading-period">.</span></h1>
    </div>
    <div class="heading-actions">
      <Status :value="device?.connectionState" /><span
        v-if="auth.engineer"
        class="mono instrument-id"
        >{{ device?.type ?? "无设备" }}</span
      >
    </div>
  </div>
  <section class="field-task-context">
    <div>
      <label
        >当前采样任务<select v-model="tasks.selected" aria-label="现场采样任务">
          <option value="">选择任务，查看产品与摆放要求</option>
          <option v-for="task in tasks.items" :key="task.id" :value="task.id">
            {{ displayName(task.name) }} · {{ task._count.samples }}/{{
              task.target
            }}
            张
          </option>
        </select></label
      >
      <p v-if="!currentTask" class="note">
        先选任务，再按指引采样。独立采样也可保存，后续由管理员整理。
      </p>
      <template v-else
        ><b>{{ taskPlan?.rules.product || "独立采样任务" }}</b
        ><span v-if="taskPlan">
          · {{ taskPlan.name }} / V{{ taskPlan.version }}</span
        >
        <p class="field-instructions">
          {{
            taskPlan?.rules.instructions ||
            "该任务还没有摆放指引，请向管理员确认采集标准。"
          }}
        </p>
        <small>{{ taskPlan?.rules.conditions }}</small></template
      >
    </div>
    <aside>
      <b>{{
        auth.admin ? "管理现场" : auth.engineer ? "技术维护" : "我的职责"
      }}</b>
      <p>
        {{
          auth.engineer
            ? "连接设备、核对实际运行模型与现场结果；正式发布由管理员批准。"
            : "按要求摆放和采样；结果有疑问时提交复核意见。方案、训练和发布由管理员负责。"
        }}
      </p>
      <span v-if="taskPlan" class="note"
        >任务方案是采样依据，未代表设备已激活此方案。</span
      >
    </aside>
  </section>
  <div class="device-control console-controls">
    <label
      >检测设备<select v-model="devices.selected" aria-label="当前设备">
        <option v-for="d in devices.devices" :key="d.id" :value="d.id">
          {{ displayName(d.name) }}
        </option>
      </select></label
    >
    <span v-if="device?.source === 'SIMULATION'" class="tag simulated"
      >模拟设备</span
    >
    <div class="control-actions" v-if="auth.engineer">
      <button
        v-if="device?.connectionState !== 'ONLINE'"
        class="primary"
        :disabled="connecting || !device"
        @click="connect"
      >
        {{ connecting ? "连接中…" : "连接设备" }}
      </button>
      <template v-else
        ><button
          v-if="!inspecting"
          class="primary"
          :disabled="connecting"
          @click="control(true)"
        >
          开始检测</button
        ><button v-else :disabled="connecting" @click="control(false)">
          暂停检测</button
        ><RouterLink :to="{ name: 'diagnostics' }" class="text-button"
          >设备设置</RouterLink
        ></template
      >
    </div>
    <span v-else-if="device?.connectionState !== 'ONLINE'" class="muted"
      >请联系管理员或维护人员连接设备</span
    >
  </div>
  <details v-if="device?.error" class="error-box device-error">
    <summary>
      {{
        errorMessage(
          /No matching UDP|timeout|timed out/i.test(device.error)
            ? "DEVICE_TIMEOUT"
            : "COMMAND_REJECTED",
          device.error,
        )
      }}
    </summary>
    <pre>{{ device.error }}</pre>
  </details>
  <div class="capture-bar console-capture field-capture">
    <div class="capture-task">
      <b>保存到：{{ currentTask?.name || "独立采样" }}</b
      ><small v-if="currentTask"
        >已采 {{ currentTask._count.samples }} /
        {{ currentTask.target }} 张</small
      >
    </div>
    <span class="muted capture-hint">{{
      captureBlocked || (held ? "采样保存设备当前实时帧" : "保存图像与检测记录")
    }}</span
    ><button
      class="primary capture"
      :class="{ busy }"
      @click="capture"
      :disabled="busy || connecting || !!captureBlocked"
      :title="captureBlocked"
    >
      {{ busy ? "处理中…" : held ? "采样实时帧" : "采样当前帧" }}
    </button>
  </div>
  <div class="vision-workspace">
    <section class="vision-canvas">
      <div class="canvas-title">
        <span
          ><i class="signal-dot" :class="{ live: !!preview && !held }"></i
          >{{ held ? "帧回看" : "实时图像" }}</span
        ><span class="mono"
          >{{ shown ? `${shown.width} × ${shown.height}` : "等待图像源"
          }}<span v-if="shown"> / #{{ shown.frameId }}</span></span
        >
      </div>
      <ImageViewer
        compact
        :jpeg="shown?.jpeg"
        :boxes="inspecting ? shown?.detections : undefined"
        :width="shown?.width"
        :height="shown?.height"
      />
      <div class="canvas-footer">
        <span>{{
          device?.connectionState !== "ONLINE"
            ? "选择设备并连接以接收画面"
            : held
              ? "正在查看缓存在此页面的历史帧"
              : "设备连续采集"
        }}</span
        ><button v-if="held" class="return-live" @click="held = null">
          返回实时画面</button
        ><time class="mono">{{
          shown ? new Date(shown.receivedAt).toLocaleTimeString() : "—"
        }}</time>
      </div>
    </section>
    <aside class="result-inspector">
      <div class="inspector-title">
        <span>结果检查器</span><span class="mono">02</span>
      </div>
      <div
        class="live-verdict"
        :class="{
          candidate: inspecting && detections?.length,
          clear: inspecting && preview && detections?.length === 0,
        }"
      >
        <span class="verdict-caption">{{
          held ? "回看帧 · 候选检测" : "当前帧 · 候选检测"
        }}</span>
        <strong>{{
          !shown
            ? "等待图像"
            : device?.reportedState.inspectionEnabled === undefined
              ? "等待检测状态"
              : !inspecting
                ? "检测暂停"
                : detections === null
                  ? "仅图像"
                  : detections.length
                    ? "待复核"
                    : "未检出目标"
        }}</strong>
        <span>{{
          !shown
            ? "等待设备返回完整帧"
            : !inspecting
              ? "开始检测后显示候选结果"
              : detections === null
                ? "本帧没有推理输出"
                : detections.length
                  ? `${detections.length} 处候选目标 · 需人工确认`
                  : "本帧没有候选目标"
        }}</span>
      </div>
      <div class="inspector-section">
        <h3>
          检出目标
          <span class="mono">{{
            String(detections?.length ?? 0).padStart(2, "0")
          }}</span>
        </h3>
        <div class="detection-list">
          <div
            v-for="(box, i) in detections ?? []"
            :key="i"
            class="detection-item"
          >
            <span class="target-number">{{
              String(i + 1).padStart(2, "0")
            }}</span>
            <div>
              <b>{{ displayName(box.label) }}</b
              ><small class="mono"
                >{{ Math.round(box.x1) }},{{ Math.round(box.y1) }} →
                {{ Math.round(box.x2) }},{{ Math.round(box.y2) }}</small
              >
            </div>
            <strong class="mono"
              >{{ (box.confidence * 100).toFixed(1) }}<small>%</small></strong
            >
          </div>
          <p v-if="!detections?.length" class="inspector-empty">
            {{ shown ? "暂无候选目标" : "等待检测数据" }}
          </p>
        </div>
      </div>
      <div class="inspector-section model-readout">
        <p class="note">
          候选目标不等于合格判定。当前尚未应用已验证的通用方案规则，现场结果需要复核。
        </p>
        <h3>运行模型</h3>
        <b class="mono">{{
          device?.reportedState.modelVersion ?? "版本未上报"
        }}</b
        ><small
          >{{ chinese(device?.runtimeState) }} ·
          {{ chinese(device?.syncState) }}</small
        >
      </div>
      <div v-if="auth.engineer" class="inspector-section telemetry-trend">
        <h3>推理耗时趋势 <span>ms</span></h3>
        <Sparkline :values="latency" label="推理耗时" unit=" ms" />
      </div>
    </aside>
    <details v-if="auth.engineer" class="field-technical">
      <summary>维护信息：采集、推理与传输耗时</summary>
      <div class="device-telemetry">
        <header>
          <span>{{
            device?.connectionState === "ONLINE"
              ? "设备遥测"
              : "末次遥测 · 当前设备未连接"
          }}</span
          ><time class="mono">{{
            device?.telemetry?.receivedAt
              ? new Date(device.telemetry.receivedAt).toLocaleTimeString()
              : "等待上报"
          }}</time>
        </header>
        <div>
          <small>帧率</small
          ><strong
            >{{ device?.telemetry?.fps?.toFixed(2) ?? "—" }}<em>FPS</em></strong
          >
        </div>
        <div>
          <small>推理耗时</small
          ><strong
            >{{ metric(device?.telemetry?.inferenceUs) }}<em>ms</em></strong
          >
        </div>
        <div>
          <small>采集</small
          ><strong
            >{{ metric(device?.telemetry?.captureUs) }}<em>ms</em></strong
          >
        </div>
        <div>
          <small>预处理</small
          ><strong
            >{{ metric(device?.telemetry?.conversionUs) }}<em>ms</em></strong
          >
        </div>
        <div>
          <small>传输</small
          ><strong
            >{{ metric(device?.telemetry?.transferUs) }}<em>ms</em></strong
          >
        </div>
        <div>
          <small>错误码</small
          ><strong :class="{ 'tone-crit': device?.telemetry?.errorCode }">{{
            device?.telemetry?.errorCode ?? "—"
          }}</strong>
        </div>
      </div>
    </details>
    <section v-if="auth.engineer" class="frame-filmstrip">
      <div class="filmstrip-label">
        <b>连续帧</b><small>每秒留取 · 最近 8 帧</small
        ><button v-if="held" @click="held = null">实时</button>
      </div>
      <div class="filmstrip-track">
        <button
          v-for="frame in frames"
          :key="frame.frameId"
          class="frame-thumb"
          :class="{ selected: held?.frameId === frame.frameId }"
          @click="held = frame"
          :aria-label="`回看帧 ${frame.frameId}`"
        >
          <img
            :src="`data:image/jpeg;base64,${frame.jpeg}`"
            alt="检测帧缩略图"
          /><span
            ><i
              :class="
                frame.detections === null
                  ? 'unclassified'
                  : frame.detections.length
                    ? 'has-target'
                    : 'no-target'
              "
            ></i
            >#{{ frame.frameId }}</span
          >
        </button>
        <div v-if="!frames.length" class="filmstrip-empty">
          完整帧到达后在此连续排列
        </div>
      </div>
    </section>
  </div>
  <section class="panel section-space">
    <div class="panel-head">
      <h3>最近检测</h3>

      <RouterLink
        :to="{ name: 'records', params: { tab: 'all' } }"
        style="font-size: 11px; margin-left: auto"
        >全部记录</RouterLink
      >
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>检测编号</th>
            <th>时间</th>
            <th>来源</th>
            <th>模型</th>
            <th>结果</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in queue" :key="i.id">
            <td class="mono">{{ i.id.slice(-10) }}</td>
            <td>{{ new Date(i.createdAt).toLocaleTimeString() }}</td>
            <td>
              <span
                class="tag"
                :class="{ simulated: i.source === 'SIMULATION' }"
                >{{ chinese(i.source) }}</span
              >
            </td>
            <td class="mono" :class="{ muted: !i.modelVersion }">
              {{ i.modelVersion ?? "未上报" }}
            </td>
            <td><Status chip :value="i.result" /></td>
            <td>
              <RouterLink
                class="table-action"
                :to="{ name: 'inspection', params: { id: i.id } }"
                >查看</RouterLink
              >
            </td>
          </tr>
          <tr v-if="!queue.length">
            <td colspan="6" class="empty">暂无已保存检测</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
