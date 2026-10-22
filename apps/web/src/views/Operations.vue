<script setup lang="ts">
import {
  chinese,
  displayName,
  errorMessage,
  terminalActivity,
  deviceSyncText,
} from "@vision/shared";
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { Inspection } from "../types";
import { post } from "../api";
import { useAuthStore } from "../stores/auth";
import { useDeviceStore } from "../stores/devices";
import { useInspectionStore } from "../stores/inspections";
import { useNotificationStore } from "../stores/notifications";
import type { Preview } from "../stores/devices";
import Sparkline from "../components/Sparkline.vue";
import ImageViewer from "../components/ImageViewer.vue";
import Status from "../components/Status.vue";
import Icon from "../components/Icon.vue";
import { useProductStore } from "../stores/product";
import ProductApplication from "../components/ProductApplication.vue";
import MqttStatus from "../components/MqttStatus.vue";
const workflow = useProductStore();
const route = useRoute(),
  router = useRouter(),
  productSetup = ref(false);
import { UiButton, UiSelect, UiCard, UiBadge, UiTable } from "../components/ui";

const auth = useAuthStore(),
  devices = useDeviceStore(),
  inspections = useInspectionStore(),
  notices = useNotificationStore(),
  busy = ref(false),
  connecting = ref(false);
watch(
  () => route.query.setup,
  (setup) => {
    if (setup === "1" && auth.engineer) {
      if (typeof route.query.deviceId === "string")
        devices.selected = route.query.deviceId;
      productSetup.value = true;
    }
  },
  { immediate: true },
);
function prepareProduct() {
  workflow.select(terminalState.value?.product?.id || workflow.id);
  productSetup.value = true;
}
function closeProductSetup() {
  productSetup.value = false;
  void router.replace({
    query: {
      ...route.query,
      setup: undefined,
      planId: undefined,
      modelId: undefined,
      deviceId: undefined,
    },
  });
}
const clientId = crypto.randomUUID();
let sequence = 0;
const device = computed(() => devices.current),
  terminalState = computed(() => device.value?.terminal?.state ?? null),
  preview = computed(() =>
    device.value?.connectionState === "ONLINE"
      ? devices.previews[device.value.id]
      : null,
  );
const queue = computed(() => inspections.items);
const activity = computed(() =>
  terminalActivity(
    terminalState.value,
    device.value?.connectionState === "ONLINE",
  ),
);
const checkRequest = ref("");
const last = computed(() => terminalState.value?.last);
const localCounts = computed(() =>
  terminalState.value?.productionRunId
    ? terminalState.value.runCounts
    : terminalState.value?.counts,
);
const inspecting = computed(() => terminalState.value?.production === true);
const frames = ref<Preview[]>([]),
  held = ref<Preview | null>(null);
let lastFilmstripAt = 0;
watch(
  () => device.value?.id,
  (id, previous) => {
    if (previous) devices.unwatchPreview(previous);
    if (id) devices.watchPreview(id);
    checkRequest.value = sessionStorage.getItem(`vision.check.${id}`) || "";
    frames.value = [];
    held.value = null;
    lastFilmstripAt = 0;
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  const id = device.value?.id;
  if (id) devices.unwatchPreview(id);
});
watch(preview, (frame) => {
  if (!frame || Date.now() - lastFilmstripAt < 1000) return;
  lastFilmstripAt = Date.now();
  frames.value = [...frames.value, frame].slice(-8);
});
watch(
  [
    () => terminalState.value?.product?.id,
    () => terminalState.value?.product?.version,
    () => terminalState.value?.model?.id,
  ],
  () => {
    frames.value = [];
    held.value = null;
    lastFilmstripAt = 0;
  },
);
const shown = computed(() => held.value ?? preview.value);
const previewProduct = computed(() => {
  const product = terminalState.value?.product;
  return product &&
    shown.value?.planId === product.id &&
    shown.value.planVersion === product.version
    ? product
    : null;
});
const positionedRegions = computed(() =>
  (previewProduct.value?.checks ?? []).flatMap((check) =>
    check.region ? [{ ...check.region, label: check.label }] : [],
  ),
);
const detections = computed(() => shown.value?.detections ?? null);
const latency = computed(() =>
  devices.history.map((h) =>
    h.inferenceUs === null ? null : h.inferenceUs / 1000,
  ),
);
const metric = (v: number | null | undefined) =>
  v == null ? "未上报" : (v / 1000).toFixed(2);
/** 采样按钮为什么点不了，要说出来而不是只把它变灰。 */
const captureBlocked = computed(() => {
  if (!device.value) return "没有选中设备。";
  if (device.value.connectionState !== "ONLINE")
    return `设备当前${chinese(device.value.connectionState)}，无法采样。`;
  if (!device.value.capabilities.capture) return "该设备不支持采集。";
  if (!preview.value) return "正在等待设备画面…";
  return "";
});
const checkBlocked = computed(() => {
  if (device.value?.connectionState !== "ONLINE") return "设备未连接";
  return checkRequest.value || terminalState.value?.pendingRequestId
    ? ""
    : activity.value.checkBlocked;
});
async function load() {
  try {
    const id = device.value?.id;
    await inspections.load(
      `?pageSize=5&realOnly=true${id ? `&deviceId=${encodeURIComponent(id)}` : ""}`,
    );
  } catch (e) {
    notices.error(e);
  }
}
onMounted(load);
onMounted(() => {
  if (auth.engineer) void workflow.load().catch(notices.error);
});
watch(
  () => devices.recent[0],
  (event) => {
    if (event?.type === "device.inspection.completed") void load();
  },
);
watch(() => device.value?.id, load);
async function capture() {
  if (!device.value) return;
  busy.value = true;
  try {
    await post<{ inspections: Inspection[] }>("/samples/capture", {
      deviceId: device.value.id,
      planId:
        (auth.engineer ? workflow.current?.id : undefined) ||
        terminalState.value?.product?.id,
      clientId,
      localSequence: ++sequence,
      idempotencyKey: crypto.randomUUID(),
    });
    notices.add("训练样本已保存，可在样本库标注；不计入检测件数");
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
    await post(`/devices/${device.value.id}/commands`, {
      type: start ? "START_INSPECTION" : "STOP_INSPECTION",
    });
    await devices.snapshot();
    notices.add(start ? "自动检测已开始" : "自动检测已停止");
  } catch (e) {
    notices.error(e);
  } finally {
    connecting.value = false;
  }
}
async function checkOne() {
  if (!device.value) return;
  busy.value = true;
  try {
    const key = `vision.check.${device.value.id}`;
    checkRequest.value ||=
      terminalState.value?.pendingRequestId || crypto.randomUUID();
    sessionStorage.setItem(key, checkRequest.value);
    await post(`/devices/${device.value.id}/check`, {
      requestId: checkRequest.value,
    });
    sessionStorage.removeItem(key);
    checkRequest.value = "";
    await devices.snapshot();
    notices.add("补检记录已提交，联网后会自动同步");
    await load();
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="page-heading instrument-heading workbench-heading">
    <div>
      <h1><Icon name="activity" :size="22" />现场工作台</h1>
      <p class="mono">
        {{ device ? displayName(device.name) : "（无设备）"
        }}<template
          v-if="auth.engineer && device?.executionMode !== 'LINUX_TERMINAL'"
        >
          · {{ device?.protocolVersion ?? "协议版本未上报" }}</template
        >
      </p>
    </div>
    <div class="heading-actions">
      <MqttStatus
        v-if="auth.engineer && device"
        compact
        :device-id="device.id"
      />
      <Status :value="device?.connectionState" />
      <Status v-if="device" chip :value="device.runtimeState" />
    </div>
  </div>

  <section class="workbench-toolbar">
    <div class="toolbar-field product-info-badge">
      <span class="field-label">当前产品方案</span>
      <b class="product-name"
        >{{
          terminalState?.product?.product ||
          terminalState?.product?.name ||
          "未分配"
        }}<template v-if="terminalState?.product">
          / V{{ terminalState.product.version }}</template
        ></b
      >
      <UiButton
        v-if="auth.engineer && terminalState?.product && !productSetup"
        variant="text"
        size="sm"
        @click="prepareProduct"
        >更换产品</UiButton
      >
    </div>
    <div class="toolbar-field device-field">
      <span class="field-label">检测设备</span>
      <UiSelect v-model="devices.selected" aria-label="当前设备" size="md">
        <option v-if="!devices.devices.length" value="">暂无设备</option>
        <option v-for="d in devices.devices" :key="d.id" :value="d.id">
          {{ displayName(d.name) }}
        </option>
      </UiSelect>
    </div>
    <div class="toolbar-end">
      <div class="toolbar-actions" v-if="device">
        <UiButton
          v-if="
            device.connectionState !== 'ONLINE' &&
            auth.engineer &&
            device.executionMode !== 'LINUX_TERMINAL'
          "
          variant="primary"
          icon="network"
          :disabled="connecting"
          :loading="connecting"
          @click="connect"
        >
          {{ connecting ? "连接中…" : "连接设备" }}
        </UiButton>
        <span
          v-else-if="device.connectionState !== 'ONLINE'"
          class="muted toolbar-hint"
          >等待设备心跳，请检查供电和网线</span
        >
        <template v-else-if="!productSetup">
          <UiButton
            v-if="
              auth.engineer &&
              (!terminalState?.model || !terminalState?.product)
            "
            variant="primary"
            @click="prepareProduct"
            >选择产品并开始</UiButton
          >
          <UiButton
            v-else
            :variant="inspecting ? 'secondary' : 'primary'"
            :icon="inspecting ? 'pause' : 'play'"
            :disabled="
              connecting || busy || (!inspecting && !!activity.startBlocked)
            "
            :title="inspecting ? '' : activity.startBlocked"
            :loading="connecting"
            @click="control(!inspecting)"
          >
            {{ inspecting ? "停止检测" : "开始检测" }}
          </UiButton>
        </template>
      </div>
      <details
        class="secondary-actions"
        :open="!!(checkRequest || terminalState?.pendingRequestId)"
      >
        <summary>
          {{
            checkRequest || terminalState?.pendingRequestId
              ? "核对上次检查"
              : "采样与补检"
          }}
        </summary>
        <div class="toolbar-capture">
          <span class="note"
            >留样归属：{{
              (auth.engineer ? workflow.current?.rules.product : undefined) ||
              terminalState?.product?.product ||
              terminalState?.product?.name ||
              "请先在产品配置中选择产品"
            }}（只保存训练图片，不计件）</span
          >
          <span v-if="captureBlocked" class="muted capture-hint">{{
            captureBlocked
          }}</span>
          <UiButton
            variant="secondary"
            icon="activity"
            :loading="busy"
            @click="checkOne"
            :disabled="busy || connecting || !!checkBlocked"
            :title="checkBlocked || '停止自动检测后补检一件'"
          >
            {{
              checkRequest || terminalState?.pendingRequestId
                ? "核对上次检查"
                : "检查一件"
            }}
          </UiButton>
          <UiButton
            variant="secondary"
            icon="camera"
            :loading="busy"
            @click="capture"
            :disabled="busy || connecting || !!captureBlocked"
            :title="captureBlocked"
          >
            {{ busy ? "处理中…" : "留样" }}
          </UiButton>
          <UiButton
            v-if="auth.engineer"
            variant="ghost"
            size="sm"
            icon="device"
            :to="{ name: 'diagnostics' }"
            >设备设置</UiButton
          >
        </div>
      </details>
    </div>
  </section>

  <ProductApplication
    v-if="productSetup && auth.engineer"
    inline
    @started="closeProductSetup"
    @cancel="closeProductSetup"
  />
  <section
    v-if="!productSetup"
    class="panel section-space"
    aria-label="当前检测步骤"
  >
    <div class="panel-body">
      <strong>{{ activity.label }}</strong>
      <p>{{ activity.hint }}</p>
      <UiButton
        v-if="
          auth.engineer && (!terminalState?.model || !terminalState?.product)
        "
        variant="text"
        @click="prepareProduct"
        >配置检测产品</UiButton
      >
    </div>
  </section>
  <details v-if="device?.error" class="error-box device-error-banner">
    <summary>
      <Icon name="alert" :size="15" />
      当前检测故障：{{
        device.executionMode === "LINUX_TERMINAL"
          ? device.error
          : errorMessage(
              /No matching UDP|timeout|timed out/i.test(device.error)
                ? "DEVICE_TIMEOUT"
                : "COMMAND_REJECTED",
              device.error,
            )
      }}
    </summary>
    <p v-if="terminalState">
      最近上报：{{ new Date(terminalState.receivedAt).toLocaleString() }} ·
      <RouterLink :to="{ name: 'diagnostics' }">查看设备故障</RouterLink>
    </p>
    <pre v-if="auth.engineer">{{ device.error }}</pre>
    <p v-else class="note">请联系维护人员处理。</p>
  </details>
  <details v-if="terminalState?.syncError" class="section-space">
    <summary>
      记录上传受阻 · 全机 {{ terminalState.pendingSync }} 条等待同步
    </summary>
    <p>
      本机保存的记录会继续自动重试上传。最近上报：{{
        new Date(terminalState.receivedAt).toLocaleString()
      }}。
    </p>
    <pre>{{ terminalState.syncError }}</pre>
    <RouterLink v-if="auth.engineer" :to="{ name: 'diagnostics' }"
      >检查设备与平台连接</RouterLink
    >
  </details>

  <div class="workbench-grid">
    <div class="workbench-stage">
      <section class="vision-canvas">
        <div class="canvas-title">
          <span
            ><i class="signal-dot" :class="{ live: !!preview && !held }"></i
            >{{ held ? "帧回看" : "实时图像" }}</span
          ><span v-if="auth.engineer" class="mono"
            >{{ shown ? `${shown.width} × ${shown.height}` : "等待图像源"
            }}<span v-if="shown"> · 图像帧 {{ shown.frameId }}</span></span
          >
        </div>
        <ImageViewer
          compact
          :operator="!auth.engineer"
          :jpeg="shown?.jpeg"
          :boxes="shown?.detections ?? undefined"
          :width="shown?.width"
          :height="shown?.height"
          :region="previewProduct?.region"
          :regions="positionedRegions"
          :postprocess="shown?.postprocess"
        />
        <div class="canvas-footer">
          <span>{{
            device?.connectionState !== "ONLINE"
              ? "选择设备并连接以接收画面"
              : held
                ? "正在查看缓存在此页面的历史帧"
                : "设备连续采集"
          }}</span
          ><UiButton
            v-if="held"
            variant="primary"
            size="sm"
            icon="refresh"
            @click="held = null"
          >
            返回实时画面 </UiButton
          ><time v-if="auth.engineer && shown" class="mono">{{
            new Date(shown.receivedAt).toLocaleTimeString()
          }}</time>
        </div>
      </section>

      <section v-if="auth.engineer" class="frame-filmstrip">
        <div class="filmstrip-head">
          <b>连续帧</b><small>每秒留取 · 最近 8 帧</small
          ><UiButton
            v-if="held"
            variant="secondary"
            size="sm"
            @click="held = null"
          >
            返回实时
          </UiButton>
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
              >图像帧 {{ frame.frameId }}</span
            >
          </button>
          <div v-if="!frames.length" class="filmstrip-empty">
            完整帧到达后在此连续排列
          </div>
        </div>
      </section>

      <details v-if="auth.engineer" class="field-technical">
        <summary>
          <Icon name="chart" :size="14" /> 维护信息：采集、推理与传输耗时
        </summary>
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
              >{{ device?.telemetry?.fps?.toFixed(2) ?? "未上报"
              }}<em v-if="device?.telemetry?.fps != null">帧/秒</em></strong
            >
          </div>
          <div>
            <small>推理耗时</small
            ><strong
              >{{ metric(device?.telemetry?.inferenceUs)
              }}<em v-if="device?.telemetry?.inferenceUs != null"
                >毫秒</em
              ></strong
            >
          </div>
          <div>
            <small>采集</small
            ><strong
              >{{ metric(device?.telemetry?.captureUs)
              }}<em v-if="device?.telemetry?.captureUs != null"
                >毫秒</em
              ></strong
            >
          </div>
          <div>
            <small>预处理</small
            ><strong
              >{{ metric(device?.telemetry?.conversionUs)
              }}<em v-if="device?.telemetry?.conversionUs != null"
                >毫秒</em
              ></strong
            >
          </div>
          <div>
            <small>传输</small
            ><strong
              >{{ metric(device?.telemetry?.transferUs)
              }}<em v-if="device?.telemetry?.transferUs != null"
                >毫秒</em
              ></strong
            >
          </div>
          <div>
            <small>错误码</small
            ><strong :class="{ 'tone-crit': device?.telemetry?.errorCode }">{{
              device?.telemetry?.errorCode == null
                ? "未上报"
                : device.telemetry.errorCode === 0
                  ? "无故障"
                  : `故障码 ${device.telemetry.errorCode}`
            }}</strong>
          </div>
        </div>
      </details>
    </div>

    <aside class="result-inspector workbench-side">
      <div class="live-verdict">
        <span class="verdict-caption"
          >{{
            last?.productionRunId &&
            last.productionRunId !== terminalState?.productionRunId
              ? "最近历史批次单件"
              : terminalState?.productionRunId
                ? "本批次最近保存单件"
                : "最近单件/补检"
          }}
          · 机器原判<template v-if="last">
            · 第 {{ last.sequence }} 件</template
          ></span
        >
        <strong>{{ last ? chinese(last.result) : "尚未完成单件" }}</strong>
        <span>{{ last?.reason || activity.hint }}</span>
        <p v-for="finding in last?.findings || []" :key="finding.classId">
          {{ finding.label }}：确认 {{ finding.count }}，待确认
          {{ finding.uncertain }}，要求 {{ finding.min }}–{{ finding.max }} ·
          {{ chinese(finding.result) }}
        </p>
      </div>

      <section v-if="terminalState" class="side-card runtime-card">
        <div class="side-card-title">
          <span><Icon name="device" :size="15" /> 设备运行状态</span>
          <span>{{ activity.label }}</span>
        </div>
        <p class="mono runtime-line">
          模型：{{ terminalState.model?.version || "未下发" }}
        </p>
        <p class="mono runtime-line">
          产品：{{
            terminalState.product?.product ||
            terminalState.product?.name ||
            "未分配"
          }}
        </p>
        <p class="mono runtime-line">
          {{ activity.label }} ·
          {{ terminalState.productionRunId ? "本批次" : "本机累计" }}
          {{
            terminalState.productionRunId
              ? terminalState.runTotal
              : terminalState.total
          }}
          件
        </p>
        <p class="mono runtime-line">
          全机待上传：{{ terminalState.pendingSync }} 条（含历史批次和补检） ·
          最近原判：
          {{
            terminalState.last ? chinese(terminalState.last.result) : "尚无结果"
          }}
        </p>
      </section>
      <section v-if="terminalState" class="side-card">
        <div class="side-card-title">
          {{
            terminalState.productionRunId
              ? "本批次机器原判"
              : "本机累计机器原判"
          }}
        </div>
        <p>
          合格 {{ localCounts?.PASS ?? 0 }} · 不合格
          {{ localCounts?.FAIL ?? 0 }} · 待复核 {{ localCounts?.REVIEW ?? 0 }} ·
          错误 {{ localCounts?.ERROR ?? 0 }}
        </p>
        <RouterLink
          :to="{
            name: 'production',
            query: { run: terminalState.productionRunId || undefined },
          }"
          >查看当前批次汇总与复核</RouterLink
        >
        <p class="note">
          本机原判包含待同步记录；人工处理结果见 Web 批次汇总。
        </p>
        <div
          v-if="terminalState.product?.checks?.length"
          class="task-requirements"
        >
          <b>当前方案要求</b>
          <p v-for="check in terminalState.product.checks" :key="check.classId">
            {{ check.label }}：{{
              check.min === check.max ? check.min : `${check.min}–${check.max}`
            }}
            个
            <template v-if="check.region"
              >；中心 X {{ (check.region.x * 100).toFixed(0) }}–{{
                ((check.region.x + check.region.width) * 100).toFixed(0)
              }}%，Y {{ (check.region.y * 100).toFixed(0) }}–{{
                ((check.region.y + check.region.height) * 100).toFixed(0)
              }}%</template
            >
          </p>
        </div>
        <p class="task-instructions">
          {{
            terminalState.product?.instructions ||
            "请按当前产品方案摆放，产品离开后自动保存一件。"
          }}
        </p>
      </section>
      <div class="inspector-section">
        <h3>
          当前画面目标（仅定位，不计件）
          <span class="mono">{{ `${detections?.length ?? 0} 个` }}</span>
        </h3>
        <div class="detection-list">
          <div
            v-for="(box, i) in detections ?? []"
            :key="i"
            class="detection-item"
          >
            <span class="target-number">{{
              box.trackId
                ? `跟踪 ${box.trackId}${box.trackConfirmed ? "" : "（确认中）"}`
                : `目标 ${i + 1}`
            }}</span>
            <div>
              <b>{{ displayName(box.label) }}</b
              ><small v-if="auth.engineer" class="mono"
                >位置：左上 {{ Math.round(box.x1) }},{{
                  Math.round(box.y1)
                }}；右下 {{ Math.round(box.x2) }},{{
                  Math.round(box.y2)
                }}</small
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

      <div v-if="auth.engineer" class="inspector-section model-readout">
        <p class="note">
          单件结论由当前产品方案的数量、区域与图像质量规则判定。人工复核保留机器原判。
        </p>
        <h3><Icon name="device" :size="14" /> 运行模型</h3>
        <b class="mono">{{
          device?.reportedState.modelVersion ?? "版本未上报"
        }}</b
        ><small
          >{{ chinese(device?.runtimeState) }} ·
          {{ deviceSyncText(device) }}</small
        >
      </div>

      <div v-if="auth.engineer" class="inspector-section telemetry-trend">
        <h3><Icon name="chart" :size="14" /> 推理耗时趋势 <span>ms</span></h3>
        <Sparkline :values="latency" label="推理耗时" unit=" ms" />
      </div>
    </aside>
  </div>

  <UiCard padding="none" class="recent-inspections-card">
    <template #header>
      <div class="panel-head-title">
        <Icon name="clock" :size="17" />
        <h3>最近检测</h3>
      </div>
      <div class="panel-head-actions">
        <UiBadge tone="neutral" chip class="mono"
          >{{ queue.length }} 条</UiBadge
        >
        <UiButton
          variant="outline"
          size="sm"
          :to="{ name: 'records', params: { tab: 'all' } }"
        >
          全部记录
        </UiButton>
      </div>
    </template>

    <UiTable compact hover>
      <thead>
        <tr>
          <th v-if="auth.engineer">检测编号</th>
          <th>时间</th>
          <th v-if="auth.engineer">来源</th>
          <th v-if="auth.engineer">模型</th>
          <th>平台核验 / 人工结论</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="i in queue" :key="i.id">
          <td v-if="auth.engineer" class="mono font-semibold" :title="i.id">
            {{ i.id.slice(-10) }}
          </td>
          <td class="mono">{{ new Date(i.createdAt).toLocaleTimeString() }}</td>
          <td v-if="auth.engineer">
            <UiBadge
              :tone="i.source === 'SIMULATION' ? 'warn' : 'info'"
              chip
              size="sm"
            >
              {{ chinese(i.source) }}
            </UiBadge>
          </td>
          <td
            v-if="auth.engineer"
            class="mono"
            :class="{ muted: !i.modelVersion }"
          >
            {{ i.modelVersion ?? "未上报" }}
          </td>
          <td>
            <Status chip :value="i.result" /> /
            <Status v-if="i.reviewResult" :value="i.reviewResult" /><span
              v-else
              class="text-muted"
              >未复核</span
            >
          </td>
          <td class="action-cell">
            <UiButton
              variant="text"
              size="sm"
              :to="{ name: 'inspection', params: { id: i.id } }"
            >
              查看详情
            </UiButton>
          </td>
        </tr>
        <tr v-if="!queue.length">
          <td :colspan="auth.engineer ? 6 : 3" class="empty-table-cell">
            暂无已保存检测记录
          </td>
        </tr>
      </tbody>
    </UiTable>
  </UiCard>
</template>

<style scoped>
.terminal-live {
  padding: 1rem;
}
.terminal-live p {
  margin: 0.8rem 0;
}
.terminal-preview {
  display: block;
  width: 100%;
  max-width: 640px;
  margin: 1rem auto;
  border: 1px solid var(--line);
  background: #000;
}
.page-heading h1 {
  display: flex;
  align-items: center;
  gap: 10px;
}
.page-heading h1 .icon {
  color: var(--forest);
}
.workbench-heading {
  margin-bottom: 16px;
}
.workbench-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 16px;
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  margin-bottom: 16px;
}
.toolbar-field {
  display: grid;
  gap: 6px;
  margin: 0;
  min-width: 0;
  font-size: 12px;
  color: var(--muted);
}
.toolbar-field select {
  min-width: 220px;
  padding: 7px 10px;
  color: var(--ink);
}
.toolbar-field:first-child {
  flex: 1 1 280px;
}
.toolbar-field:first-child select {
  width: 100%;
}
.device-field {
  flex: 0 1 240px;
}
.device-field select {
  width: 100%;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar-actions button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.toolbar-actions .text-button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.toolbar-hint {
  font-size: 12px;
}
.toolbar-end {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
  width: 100%;
  justify-content: space-between;
  border-top: 1px solid var(--line);
  padding-top: 14px;
}
.toolbar-capture {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.secondary-actions > summary {
  cursor: pointer;
  font-size: 13px;
}
.secondary-actions[open] .toolbar-capture {
  margin-top: 10px;
}
.toolbar-capture .capture-hint {
  display: block;
  max-width: 300px;
  font-size: 12px;
  text-align: right;
}
.toolbar-capture .capture {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 170px;
  min-height: 42px;
}
.device-error-banner {
  margin-bottom: 16px;
}
.device-error-banner summary {
  display: flex;
  align-items: center;
  gap: 7px;
}
.workbench-grid {
  display: grid;
  grid-template-columns: minmax(0, 640px) minmax(320px, 1fr);
  gap: 16px;
  align-items: start;
}
.workbench-stage {
  width: 100%;
  min-width: 0;
  display: grid;
  gap: 12px;
}
.workbench-stage .vision-canvas {
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  overflow: hidden;
}
/* 检测输入是 416×416 方形；画面区跟随 1:1，不再横向拉长。
   image-stage 在 ImageViewer 子组件内部，必须用 :deep 穿透 scoped。 */
.workbench-stage .vision-canvas :deep(.image-stage) {
  flex: none;
  width: 100%;
  height: auto;
  min-height: 0;
  max-height: none;
  aspect-ratio: 1 / 1;
}
/* 连续帧：标题独占一行，最近 8 帧在同一行内自适应，不再横向截断。 */
.frame-filmstrip {
  flex-direction: column;
  gap: 8px;
}
.filmstrip-head {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}
.filmstrip-head b {
  font-size: 11px;
  font-weight: 550;
}
.filmstrip-head small {
  font-size: 9px;
  color: #aab59d;
}
.filmstrip-head button {
  margin-left: auto;
  min-height: 24px;
  padding: 2px 9px;
  font-size: 10px;
  background: transparent;
  color: #e8eada;
  border-color: #6a765c;
}
.frame-filmstrip .filmstrip-track {
  width: 100%;
}
.frame-filmstrip .frame-thumb {
  flex: 1 1 0;
  width: auto;
  min-width: 0;
}
.workbench-side {
  display: block;
  border: 1px solid var(--line-strong);
  border-left: 1px solid var(--line-strong);
  background: var(--surface);
  border-radius: 10px;
  overflow: hidden;
}
.side-card {
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.side-card-title {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 10px;
  color: var(--muted);
}
.side-card-title > span:first-child {
  display: flex;
  align-items: center;
  gap: 6px;
}
.task-name {
  display: block;
  font-size: 14px;
}
.task-plan {
  margin: 6px 0 10px;
  font-size: 11px;
  color: var(--muted);
}
.task-plan span {
  color: var(--ink-2);
}
.task-progress {
  height: 4px;
  margin: 8px 0 4px;
  background: var(--surface-3);
  overflow: hidden;
}
.task-progress span {
  display: block;
  height: 100%;
  background: var(--forest);
}
.task-count {
  color: var(--muted);
  font-size: 10px;
}
.task-card h4 {
  margin: 14px 0 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--muted);
}
.task-instructions {
  margin: 0;
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.8;
  color: var(--ink-2);
}
.task-conditions {
  display: block;
  margin-top: 8px;
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.6;
}
.workbench-side .detection-list {
  max-height: 260px;
}
.inspector-section h3 {
  display: flex;
  align-items: center;
  gap: 6px;
}
.inspector-section h3 > span {
  margin-left: auto;
}
.recent-panel .panel-head h3 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.recent-panel .panel-head h3 .icon {
  color: var(--muted);
}
@media (min-width: 1081px) and (min-height: 760px) {
  .workbench-side {
    position: sticky;
    top: 76px;
  }
}
@media (max-width: 1080px) {
  .workbench-grid {
    grid-template-columns: 1fr;
  }
  .workbench-toolbar {
    align-items: stretch;
  }
  .toolbar-field,
  .device-field {
    flex: 1 1 100%;
    max-width: none;
  }
  .toolbar-field select {
    width: 100%;
    min-width: 0;
  }
  .toolbar-end {
    width: 100%;
    margin-left: 0;
    justify-content: space-between;
  }
  .toolbar-capture {
    width: 100%;
    justify-content: space-between;
  }
  .toolbar-capture .capture-hint {
    max-width: none;
    text-align: left;
  }
  .toolbar-capture .capture {
    flex: 1;
  }
}
</style>
