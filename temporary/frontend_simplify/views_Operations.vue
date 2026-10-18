<script setup lang="ts">
import { chinese, displayName } from "@vision/shared";
import { ref, computed, onMounted, watch } from "vue";
import type { Inspection } from "../types";
import { post } from "../api";
import { useAuthStore } from "../stores/auth";
import { useDeviceStore } from "../stores/devices";
import { useTaskStore } from "../stores/tasks";
import { useInspectionStore } from "../stores/inspections";
import { useNotificationStore } from "../stores/notifications";
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
const inspecting = computed(
  () => device.value?.reportedState.inspectionEnabled === true,
);
const detections = computed(() => preview.value?.detections ?? null);
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
  <div class="page-heading">
    <div>
      <h1>检测工作台</h1>
    </div>
  </div>
  <div class="device-control panel">
    <label
      >检测设备<select v-model="devices.selected" aria-label="当前设备">
        <option v-for="d in devices.devices" :key="d.id" :value="d.id">
          {{ displayName(d.name) }}
        </option>
      </select></label
    >
    <Status :value="device?.connectionState" />
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
      >请联系工程师连接设备</span
    >
  </div>
  <p v-if="device?.error" class="error-box">{{ device.error }}</p>
  <section
    v-if="device?.connectionState !== 'ONLINE'"
    class="panel connection-empty"
  >
    <h2>尚未连接设备</h2>
    <p>
      {{
        auth.engineer
          ? "选择检测设备并点击上方“连接设备”，即可查看实时画面。"
          : "请联系工程师连接设备，然后开始采样。"
      }}
    </p>
  </section>
  <div v-else class="workbench">
    <section class="panel">
      <div class="panel-head">
        <h3>实时画面</h3>
        <span v-if="device?.source === 'SIMULATION'" class="tag simulated"
          >模拟设备</span
        >
      </div>
      <ImageViewer
        :jpeg="preview?.jpeg"
        :boxes="inspecting ? preview?.detections : undefined"
      />
      <!-- 主操作贴着画面、做成整宽大按钮：操作工的全部工作就是反复按它。 -->
      <div class="capture-bar">
        <label class="capture-task"
          >采样任务<select v-model="tasks.selected" aria-label="关联采样任务">
            <option value="">独立采样</option>
            <option v-for="t in tasks.items" :key="t.id" :value="t.id">
              {{ displayName(t.name) }}
            </option>
          </select></label
        >
        <button
          class="primary capture"
          :class="{ busy }"
          @click="capture"
          :disabled="busy || connecting || !!captureBlocked"
          :title="captureBlocked"
        >
          {{ busy ? "处理中…" : "采样当前帧" }}
        </button>
      </div>
      <div class="panel-head" style="border-top: 1px solid var(--line)">
        <span v-if="captureBlocked" class="muted">{{ captureBlocked }}</span>
        <span class="mono" style="font-size: 11px">
          帧 {{ preview?.frameId ?? "—" }}
          <span class="muted"
            >/
            {{
              preview
                ? new Date(preview.receivedAt).toLocaleTimeString()
                : "等待数据"
            }}</span
          >
        </span>
      </div>
    </section>

    <div>
      <!-- 判定优先：这一帧怎么样，先给结论再给依据 -->
      <div class="verdict" :class="{ warn: detections?.length }">
        <div class="word">
          {{
            !preview
              ? "等待设备画面"
              : !inspecting
                ? device?.runtimeState === "READY"
                  ? "检测已暂停"
                  : "仅预览"
                : detections === null
                  ? "仅图像"
                  : detections.length
                    ? "疑似缺陷"
                    : "未发现缺陷"
          }}
        </div>
        <p class="say">
          {{
            !preview
              ? "设备连接后，画面会显示在左侧。"
              : !inspecting
                ? "点击开始检测以继续。"
                : detections === null
                  ? "当前帧没有推理输出，只提供图像。"
                  : detections.length
                    ? `检出 ${detections.length} 处候选，需人工确认。`
                    : "本帧未检出候选缺陷。"
          }}
        </p>
      </div>

      <section
        v-if="preview && inspecting && detections?.length"
        class="panel section-space"
      >
        <div class="panel-head">
          <h3>检出目标</h3>
          <span class="inline-count">{{ detections?.length ?? 0 }} 项</span>
        </div>
        <div class="panel-body">
          <div v-if="!detections?.length" class="note" style="padding: 8px 0">
            本帧没有检出目标。
          </div>
          <div
            v-for="(box, i) in detections ?? []"
            :key="i"
            class="result-line"
          >
            <div>
              <small>目标 {{ String(i + 1).padStart(2, "0") }}</small>
              <p>{{ displayName(box.label) }}</p>
            </div>
            <span class="mono">{{ (box.confidence * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </section>
    </div>
  </div>

  <section class="panel section-space">
    <div class="panel-head">
      <h3>最近检测</h3>

      <RouterLink
        :to="{ name: 'records' }"
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
