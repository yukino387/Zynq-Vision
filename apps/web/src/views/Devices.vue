<script setup lang="ts">
import { chinese, displayName, fieldLabel } from "@vision/shared";
import { ref, computed, watch, toRaw } from "vue";
import { useRoute } from "vue-router";
import type { Named } from "../types";
import type {
  DeviceSnapshot,
  DeviceState,
  Model,
  ResidentModel,
} from "@vision/contracts";
import { api, post } from "../api";
import { useDeviceStore } from "../stores/devices";
import { useNotificationStore } from "../stores/notifications";
import { useAuthStore } from "../stores/auth";
import Status from "../components/Status.vue";
import Drawer from "../components/Drawer.vue";
import AsyncState from "../components/AsyncState.vue";
import SortableTh from "../components/SortableTh.vue";
import Icon from "../components/Icon.vue";
import Sparkline from "../components/Sparkline.vue";
import DistributionBar from "../components/DistributionBar.vue";
const route = useRoute(),
  devices = useDeviceStore(),
  notices = useNotificationStore(),
  auth = useAuthStore();
const tab = computed(() =>
    String(route.params.tab || route.meta.defaultTab || "registry"),
  ),
  rows = ref<Named[]>([]),
  loading = ref(false),
  error = ref(""),
  selected = ref<DeviceSnapshot | null>(null),
  detail = ref<unknown>(null),
  creating = ref(false),
  name = ref(""),
  serial = ref(""),
  stationId = ref(""),
  stations = ref<Named[]>([]),
  command = ref("GET_STATUS"),
  brightness = ref(0),
  targetModel = ref(""),
  targetPlan = ref(""),
  busy = ref(false);
/** 遥测是微秒，界面按毫秒显示。 */
const metric = (us: number | undefined) =>
  us === undefined ? "—" : (us / 1000).toFixed(1);
const legacy = (d: DeviceSnapshot | null | undefined) =>
  d?.executionMode === "BARE_METAL";
const modeName = (d: DeviceSnapshot | null | undefined) =>
  d?.executionMode === "LINUX_TERMINAL"
    ? "Linux 独立终端"
    : legacy(d)
      ? "旧裸机设备"
      : "运行环境待确认";
watch(
  () => devices.devices,
  () => {
    if (selected.value)
      selected.value =
        devices.devices.find((d) => d.id === selected.value?.id) ?? null;
  },
);
const firmware = computed(() => selected.value?.reportedState.firmware ?? null);
const slotName = (slot: number | null | undefined) =>
  slot === 0
    ? "A"
    : slot === 1
      ? "B"
      : slot === 2
        ? "Golden"
        : slot === 0xffffffff || slot == null
          ? "无"
          : `#${slot}`;
/** 趋势只保留当前选中设备最近 120 帧；切换设备时 store 会清空。 */
const fpsValues = computed(() => devices.history.map((item) => item.fps));
const inferenceValues = computed(() =>
  devices.history.map((item) =>
    item.inferenceUs === null ? null : item.inferenceUs / 1000,
  ),
);
const cycleValues = computed(() =>
  devices.history.map((item) =>
    item.cycleUs === null ? null : item.cycleUs / 1000,
  ),
);
const stageSlices = computed(() => {
  const telemetry = devices.current?.telemetry;
  if (!telemetry) return [];
  return [
    {
      label: "采集",
      value: (telemetry.captureUs ?? 0) / 1000,
      tone: "info" as const,
    },
    {
      label: "预处理",
      value: (telemetry.conversionUs ?? 0) / 1000,
      tone: "quiet" as const,
    },
    {
      label: "推理",
      value: (telemetry.inferenceUs ?? 0) / 1000,
      tone: "ok" as const,
    },
    {
      label: "传输",
      value: (telemetry.transferUs ?? 0) / 1000,
      tone: "warn" as const,
    },
  ];
});
const statusSlices = computed(() => {
  const counts: Record<string, number> = {
    ONLINE: 0,
    STALE: 0,
    OFFLINE: 0,
    UNKNOWN: 0,
  };
  for (const device of devices.devices) {
    const key = String(device.connectionState);
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return [
    { label: "在线", value: counts.ONLINE ?? 0, tone: "ok" as const },
    { label: "连接不稳", value: counts.STALE ?? 0, tone: "warn" as const },
    { label: "离线", value: counts.OFFLINE ?? 0, tone: "quiet" as const },
    { label: "未知", value: counts.UNKNOWN ?? 0, tone: "info" as const },
  ];
});
/** 模拟器只保留在服务端做自动化验证，界面不展示它的事件。 */
const debugEvents = computed(() =>
  devices.recent.filter((event) => event.source !== "SIMULATION"),
);
/** 设备表读的是 store 快照（全量、不分页），排序只能在客户端做。
 *  异常状态排前面：运维先看要处理的。 */
const devSort = ref("connectionState"),
  devOrder = ref<"asc" | "desc">("asc");
const rank: Record<string, number> = {
  OFFLINE: 0,
  FAULT: 1,
  STALE: 2,
  CONNECTING: 3,
  ONLINE: 4,
};
const deviceRows = computed(() => {
  const rows = [...devices.devices];
  const dir = devOrder.value === "asc" ? 1 : -1;
  return rows.sort((a, b) => {
    if (devSort.value === "connectionState")
      return (
        ((rank[a.connectionState] ?? 9) - (rank[b.connectionState] ?? 9)) * dir
      );
    if (devSort.value === "runtimeState")
      return String(a.runtimeState).localeCompare(String(b.runtimeState)) * dir;
    return displayName(a.name).localeCompare(displayName(b.name)) * dir;
  });
});
function sortDevices(field: string) {
  if (devSort.value === field)
    devOrder.value = devOrder.value === "asc" ? "desc" : "asc";
  else {
    devSort.value = field;
    devOrder.value = "asc";
  }
}
async function load() {
  loading.value = true;
  error.value = "";
  try {
    await devices.snapshot();
    const items = (
      await api<{ items: Named[] }>(
        tab.value === "stations" ? "/stations" : "/events",
      )
    ).items;
    rows.value =
      tab.value === "events"
        ? items.filter((item) => item.source !== "SIMULATION")
        : items;
    stations.value = (await api<{ items: Named[] }>("/stations")).items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
watch(tab, load, { immediate: true });
async function open(d: DeviceSnapshot) {
  selected.value = d;
  targetModel.value = d.desiredState.modelVersion ?? "";
  targetPlan.value = d.desiredState.planVersion ?? "";
  try {
    detail.value = await api(`/devices/${d.id}`);
  } catch (e) {
    notices.error(e);
  }
}
/** 设备 SD 模型库。板子自己维护这份清单，平台只读它。 */
const residentModels = computed(
  () => selected.value?.reportedState.models ?? [],
);
/** 详情只在打开设备时变一次；不要放在模板里，否则每次遥测重渲染都会序列化整份详情。 */
const detailText = computed(() =>
  detail.value == null ? "" : JSON.stringify(toRaw(detail.value), null, 2),
);
/** 目标和实际版本并排展示；缺字段时明确区分“未设置”和“未上报”。 */
function versionText(
  state: DeviceState | null | undefined,
  key: "modelVersion" | "planVersion" | "inspectionEnabled",
  empty: string,
) {
  const value = state?.[key];
  if (value === undefined || value === null || value === "") return empty;
  return typeof value === "boolean" ? (value ? "是" : "否") : String(value);
}
async function switchModel(entry: ResidentModel) {
  if (!selected.value || !legacy(selected.value)) return;
  busy.value = true;
  try {
    // 切换照走 Deployment：板端发现制品已在库里，就不传字节直接激活。
    const { items } = await api<{ items: Model[] }>("/models?pageSize=100");
    const match = items.find((m) => m.version === entry.version);
    if (!match) {
      notices.add(
        `设备本地模型 ${entry.version}：平台上没有同版本制品，无法按流程切换。`,
        true,
      );
      return;
    }
    await post("/deployments", {
      deviceId: selected.value.id,
      modelId: match.id,
    });
    notices.add(`已提交切换到 ${entry.version}`);
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function removeModel(entry: ResidentModel) {
  if (!selected.value || !legacy(selected.value)) return;
  busy.value = true;
  try {
    await post(`/devices/${selected.value.id}/models/delete`, {
      index: entry.index,
    });
    await devices.snapshot();
    notices.add(`已删除槽位 ${entry.index}（${entry.version}）`);
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function action(kind: string) {
  if (!selected.value || !legacy(selected.value)) return;
  busy.value = true;
  try {
    const id = selected.value.id;
    if (["connect", "disconnect"].includes(kind))
      await post(`/devices/${id}/${kind}`);
    else if (kind === "desired")
      await api(`/devices/${id}/desired`, {
        method: "PATCH",
        body: JSON.stringify({
          ...(targetModel.value ? { modelVersion: targetModel.value } : {}),
          ...(targetPlan.value ? { planVersion: targetPlan.value } : {}),
        }),
      });
    else
      await post(`/devices/${id}/commands`, {
        type: command.value,
        value:
          command.value === "SET_BRIGHTNESS" ? brightness.value : undefined,
      });
    await devices.snapshot();
    const d = devices.devices.find((d) => d.id === id);
    if (d) await open(d);
    notices.add(kind === "desired" ? "目标版本已保存" : "操作已完成");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function create() {
  busy.value = true;
  try {
    await post(
      tab.value === "stations" ? "/stations" : "/devices",
      tab.value === "stations"
        ? { name: name.value, code: serial.value }
        : {
            name: name.value,
            serialNumber: serial.value,
            type: "ZYNQ",
            stationId: stationId.value || undefined,
          },
    );
    creating.value = false;
    await load();
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>
        <Icon name="device" :size="22" />
        {{
          route.meta.tabs?.find((t) => t.tab === tab)?.label ?? route.meta.title
        }}
      </h1>
      <p class="mono">
        {{ displayName(devices.current?.name ?? "（无设备）") }} ·
        {{ modeName(devices.current) }}
      </p>
    </div>
  </div>

  <section
    v-if="tab === 'registry' && !legacy(devices.current)"
    class="panel terminal-summary"
    aria-label="Linux 终端状态"
  >
    <div class="toolbar">
      <strong>{{ modeName(devices.current) }}</strong
      ><Status :value="devices.current?.connectionState" /><RouterLink
        to="/production"
        class="text-button"
        >查看检测作业</RouterLink
      >
    </div>
    <p>
      板端自主启动、采集和检测，通过心跳上报状态，无需在网页连接 UDP 接收端。
    </p>
    <template v-if="devices.current?.terminal?.state">
      <p>
        最近上报作业：{{ devices.current.terminal.state.jobName || "未启用" }} ·
        已检查 {{ devices.current.terminal.state.total }} · 待上传
        {{ devices.current.terminal.state.pendingSync }}
      </p>
      <p>
        CPU {{ devices.current.terminal.state.cpuPercent?.toFixed(1) ?? "—" }}%
        · 内存
        {{ (devices.current.terminal.state.memoryUsed / 1048576).toFixed(1) }} /
        {{ (devices.current.terminal.state.memoryTotal / 1048576).toFixed(1) }}
        MiB
      </p>
    </template>
    <p v-else>
      尚未收到板端状态。请在板端“系统管理 →
      平台”登录管理员，按机身编号绑定此设备。
    </p>
    <p v-if="devices.current?.lastSeenAt">
      最近心跳：{{ new Date(devices.current.lastSeenAt).toLocaleString() }}
    </p>
  </section>
  <section
    v-if="tab === 'registry' && legacy(devices.current)"
    class="panel section-space telemetry-panel"
  >
    <div class="panel-head">
      <h3><Icon name="activity" /> 运行趋势</h3>
      <div class="panel-head-meta">
        <span class="mono">{{ devices.history.length }} 帧采样</span>
        <Status :value="devices.current?.connectionState" />
      </div>
    </div>
    <div class="panel-body">
      <div class="cells telemetry-cells">
        <div>
          <small>采集</small
          ><strong class="mono"
            >{{ metric(devices.current?.telemetry?.captureUs)
            }}<small class="unit">ms</small></strong
          >
        </div>
        <div>
          <small>预处理</small
          ><strong class="mono"
            >{{ metric(devices.current?.telemetry?.conversionUs)
            }}<small class="unit">ms</small></strong
          >
        </div>
        <div>
          <small>推理</small
          ><strong class="mono"
            >{{ metric(devices.current?.telemetry?.inferenceUs)
            }}<small class="unit">ms</small></strong
          >
        </div>
        <div>
          <small>传输</small
          ><strong class="mono"
            >{{ metric(devices.current?.telemetry?.transferUs)
            }}<small class="unit">ms</small></strong
          >
        </div>
        <div>
          <small>帧周期</small
          ><strong class="mono"
            >{{ metric(devices.current?.telemetry?.cycleUs)
            }}<small class="unit">ms</small></strong
          >
        </div>
        <div>
          <small>帧率</small
          ><strong class="mono"
            >{{ devices.current?.telemetry?.fps?.toFixed(2) ?? "—"
            }}<small class="unit">fps</small></strong
          >
        </div>
        <div>
          <small>错误码</small
          ><strong class="mono">{{
            devices.current?.telemetry?.errorCode ?? "未上报"
          }}</strong>
        </div>
      </div>
      <div class="chart-grid">
        <Sparkline label="帧率" :values="fpsValues" unit=" fps" :height="88" />
        <Sparkline
          label="推理耗时"
          :values="inferenceValues"
          unit=" ms"
          :height="88"
        />
        <Sparkline
          label="帧周期"
          :values="cycleValues"
          unit=" ms"
          :height="88"
        />
      </div>
      <div class="chart-grid two">
        <div class="chart-block">
          <h4><Icon name="timer" :size="15" /> 最近一帧耗时构成</h4>
          <DistributionBar :slices="stageSlices" unit=" ms" />
        </div>
        <div class="chart-block">
          <h4><Icon name="device" :size="15" /> 设备连接状态</h4>
          <DistributionBar :slices="statusSlices" />
        </div>
      </div>
      <p v-if="!devices.history.length" class="note">
        趋势数据来自实时遥测；连接设备并开始运行后开始累积。
      </p>
    </div>
  </section>
  <div v-if="tab === 'registry'" class="panel">
    <div class="panel-head">
      <h3><Icon name="device" /> 设备列表</h3>
      <div class="panel-head-actions row-actions">
        <span class="mono">{{ deviceRows.length }} 台</span>
        <button
          class="table-action"
          :class="{ busy: loading }"
          :disabled="loading"
          @click="load"
        >
          <Icon name="refresh" :size="14" /> 刷新
        </button>
        <button v-if="auth.engineer" class="primary" @click="creating = true">
          <Icon name="device" :size="14" /> 注册设备
        </button>
      </div>
    </div>
    <AsyncState
      :loading="loading"
      :error="error"
      :empty="!deviceRows.length"
      hint="还没有设备。注册 Linux 终端后，在板端登录平台并绑定设备编号。"
      @retry="load"
    >
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <SortableTh
                field="name"
                label="设备"
                :active="devSort"
                :order="devOrder"
                @sort="sortDevices"
              />
              <th class="col-type">类型</th>
              <SortableTh
                field="connectionState"
                label="网络"
                :active="devSort"
                :order="devOrder"
                @sort="sortDevices"
              />
              <SortableTh
                class="col-runtime"
                field="runtimeState"
                label="运行"
                :active="devSort"
                :order="devOrder"
                @sort="sortDevices"
              />
              <th class="col-model">实际模型</th>
              <th class="col-sync">同步状态</th>
              <th class="col-action">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in deviceRows" :key="d.id">
              <td class="device-cell">
                <strong>{{ displayName(d.name) }}</strong
                ><small class="mono">{{ d.id.slice(-10) }}</small
                ><button class="table-action mobile-only" @click="open(d)">
                  详情
                </button>
              </td>
              <td class="col-type">
                <span class="tag">{{ modeName(d) }}</span>
              </td>
              <td><Status :value="d.connectionState" /></td>
              <td class="col-runtime"><Status :value="d.runtimeState" /></td>
              <td class="mono col-model">
                {{ d.reportedState.modelVersion ?? "未上报" }}
              </td>
              <td class="col-sync"><Status :value="d.syncState" /></td>
              <td class="col-action action-cell">
                <div class="row-actions">
                  <button class="table-action" @click="open(d)">
                    状态与详情
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </AsyncState>
  </div>
  <div v-else-if="tab === 'debug'" class="panel">
    <div class="panel-head">
      <h3>实时事件 / 最近 30 条</h3>
      <Status :value="devices.connected ? 'ONLINE' : 'OFFLINE'" />
    </div>
    <div class="panel-body">
      <pre v-for="e in debugEvents" :key="e.sequence">{{
        JSON.stringify(e, null, 2)
      }}</pre>
      <div v-if="!debugEvents.length" class="empty">暂无事件</div>
    </div>
  </div>
  <div v-else-if="tab === 'stations'" class="panel">
    <div class="panel-head">
      <h3><Icon name="device" /> 工位列表</h3>
      <div class="panel-head-actions row-actions">
        <span class="mono">{{ rows.length }} 个</span>
        <button
          class="table-action"
          :class="{ busy: loading }"
          :disabled="loading"
          @click="load"
        >
          <Icon name="refresh" :size="14" /> 刷新
        </button>
        <button v-if="auth.engineer" class="primary" @click="creating = true">
          <Icon name="device" :size="14" /> 创建工位
        </button>
      </div>
    </div>
    <AsyncState
      :loading="loading"
      :error="error"
      :empty="!rows.length"
      hint="还没有工位。工位用于把设备和产品绑在一起。"
      @retry="load"
    >
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>工位名称</th>
              <th>工位代码</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rows" :key="r.id">
              <td>{{ displayName(r.name) }}</td>
              <td class="mono">{{ r.code }}</td>
              <td>{{ new Date(r.createdAt).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </AsyncState>
  </div>
  <div v-else class="panel">
    <div class="panel-head">
      <h3><Icon name="device" /> 设备事件</h3>
      <div class="panel-head-actions row-actions">
        <span class="mono">{{ rows.length }} 条</span>
        <button
          class="table-action"
          :class="{ busy: loading }"
          :disabled="loading"
          @click="load"
        >
          <Icon name="refresh" :size="14" /> 刷新
        </button>
      </div>
    </div>
    <AsyncState
      :loading="loading"
      :error="error"
      :empty="!rows.length"
      hint="设备上报状态变化、采样完成或报错时会在这里留一条。设备离线期间不会有新事件。"
      @retry="load"
    >
      <div class="panel-body">
        <div v-for="r in rows" :key="r.id" class="list-line">
          <div>
            <small class="mono"
              >{{ new Date(r.createdAt).toLocaleString() }} /
              {{ r.deviceId }}</small
            ><b>{{ chinese(r.type) }}</b>
            <details>
              <summary>事件数据</summary>
              <pre>{{ JSON.stringify(r.payload, null, 2) }}</pre>
            </details>
          </div>
        </div>
      </div>
    </AsyncState>
  </div>
  <Drawer
    v-if="selected"
    :title="displayName(selected.name)"
    @close="selected = null"
    ><div class="toolbar">
      <Status :value="selected.connectionState" /><Status
        :value="selected.runtimeState"
      /><Status :value="selected.syncState" />
    </div>
    <section v-if="!legacy(selected)" class="terminal-summary">
      <h3>{{ modeName(selected) }}</h3>
      <p>
        检查、暂停和作业切换在板端执行；平台用于分配作业、查看状态与复核证据。
      </p>
      <p>当前模型：{{ selected.reportedState.modelVersion || "未上报" }}</p>
      <p v-if="selected.terminal?.state">
        作业：{{ selected.terminal.state.jobName || "未启用" }} · 待上传
        {{ selected.terminal.state.pendingSync }}
      </p>
      <RouterLink
        to="/production"
        class="text-button"
        @click="
          devices.selected = selected.id;
          selected = null;
        "
        >进入检测作业</RouterLink
      >
    </section>
    <p class="note" v-if="legacy(selected)">
      连接设备会接管图像接收，请先断开其他上位机。
    </p>
    <div class="toolbar" v-if="auth.engineer && legacy(selected)">
      <button class="primary" @click="action('connect')" :disabled="busy">
        连接设备</button
      ><button @click="action('disconnect')" :disabled="busy">断开连接</button>
    </div>
    <section v-if="legacy(selected)" class="version-compare">
      <h3>目标版本 / 实际版本</h3>
      <div class="compare-row compare-head">
        <span>项目</span><span>目标</span><span>实际</span>
      </div>
      <div class="compare-row">
        <span>模型版本</span>
        <b class="mono">{{
          versionText(selected.desiredState, "modelVersion", "未设置")
        }}</b>
        <b class="mono">{{
          versionText(selected.reportedState, "modelVersion", "未上报")
        }}</b>
      </div>
      <div class="compare-row">
        <span>方案版本</span>
        <b class="mono">{{
          versionText(selected.desiredState, "planVersion", "未设置")
        }}</b>
        <b class="mono">{{
          versionText(selected.reportedState, "planVersion", "未上报")
        }}</b>
      </div>
      <div class="compare-row">
        <span>固件版本</span>
        <b class="mono">—</b>
        <b class="mono">{{ selected.firmwareVersion ?? "未上报" }}</b>
      </div>
      <div v-if="firmware" class="compare-row">
        <span>固件槽位</span>
        <b class="mono">—</b>
        <b class="mono"
          >运行 {{ slotName(firmware.runningSlot) }} · active
          {{ slotName(firmware.activeSlot) }} · pending
          {{ slotName(firmware.pendingSlot) }}</b
        >
      </div>
      <div v-if="firmware" class="compare-row">
        <span>试运行</span>
        <b class="mono">—</b>
        <b class="mono"
          >{{ firmware.attempts }}/{{ firmware.maxAttempts }}
          <template v-if="firmware.flags & 16"> · 待确认</template>
          <template v-else-if="firmware.flags & 8"> · 更新中</template>
          <template v-else> · 已确认</template></b
        >
      </div>
      <div class="compare-row">
        <span>检测启用</span>
        <b>{{
          versionText(selected.desiredState, "inspectionEnabled", "未设置")
        }}</b>
        <b>{{
          versionText(selected.reportedState, "inspectionEnabled", "未上报")
        }}</b>
      </div>
    </section>
    <template v-if="legacy(selected) && residentModels.length">
      <h3 class="section-space">设备模型库</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>槽位</th>
              <th>版本</th>
              <th>摘要</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in residentModels" :key="m.index">
              <td class="mono">{{ m.index }}</td>
              <td class="mono">{{ m.version }}</td>
              <td class="mono">{{ m.sha256.slice(0, 12) }}</td>
              <td>
                <span v-if="m.active" class="tag">当前</span>
                <span v-else-if="m.previous" class="tag">上一版</span>
              </td>
              <td class="action-cell">
                <div class="row-actions">
                  <button
                    v-if="!m.active"
                    class="table-action"
                    :disabled="busy"
                    @click="switchModel(m)"
                  >
                    切换
                  </button>
                  <button
                    class="table-action danger"
                    :disabled="busy || m.active || m.previous"
                    @click="removeModel(m)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="note">
        切换会照走部署流程；制品已经在设备上时板端跳过传输直接激活。
      </p>
    </template>
    <p
      v-else-if="legacy(selected) && selected.capabilities.localStorage"
      class="note"
    >
      设备 SD 卡上还没有已提交的模型。
    </p>
    <h3 class="section-space">设备能力</h3>
    <div class="capability-grid">
      <div v-for="(value, key) in selected.capabilities" :key="key">
        <span>{{ fieldLabel(key) }}</span>
        <b :class="{ off: !value }">{{ value ? "支持" : "不支持" }}</b>
      </div>
    </div>
    <template v-if="auth.engineer && legacy(selected)"
      ><h3 class="section-space">设备命令</h3>
      <label
        >控制命令<select v-model="command">
          <option value="GET_STATUS">{{ chinese("GET_STATUS") }}</option>
          <option value="START_INSPECTION">
            {{ chinese("START_INSPECTION") }}
          </option>
          <option value="STOP_INSPECTION">
            {{ chinese("STOP_INSPECTION") }}
          </option>
          <option v-if="selected.type === 'ZYNQ'" value="SET_BRIGHTNESS">
            调整亮度
          </option>
        </select></label
      ><label v-if="command === 'SET_BRIGHTNESS'"
        >亮度<input
          v-model.number="brightness"
          type="number"
          min="-4"
          max="4" /></label
      ><button @click="action('command')" :disabled="busy">发送命令</button>
      <template v-if="auth.admin">
        <h3 class="section-space">设置目标版本</h3>
        <label
          >目标模型版本<select v-model="targetModel">
            <option value="">未设置</option>
            <option
              v-for="m in residentModels"
              :key="m.index"
              :value="m.version"
            >
              {{ m.version }}
            </option>
          </select></label
        ><label>目标方案版本<input v-model="targetPlan" /></label
        ><button @click="action('desired')" :disabled="busy">
          保存目标版本
        </button>
      </template>
    </template>
    <details class="section-space">
      <summary>原始状态 / 命令 / 事件</summary>
      <pre>{{ detailText }}</pre>
    </details></Drawer
  ><Drawer
    v-if="creating"
    :title="tab === 'stations' ? '新建工位' : '注册设备'"
    @close="creating = false"
    ><form @submit.prevent="create">
      <label>名称<input v-model="name" required /></label
      ><label
        >{{ tab === "stations" ? "工位代码" : "注册序列号（本地标识）"
        }}<input v-model="serial" required /></label
      ><template v-if="tab !== 'stations'"
        ><label
          >工位<select v-model="stationId">
            <option value="">未分配</option>
            <option v-for="s in stations" :key="s.id" :value="s.id">
              {{ displayName(s.name) }}
            </option>
          </select></label
        ></template
      ><button class="primary" :disabled="busy">创建</button>
    </form></Drawer
  >
</template>
<style scoped>
.terminal-summary {
  padding: 1rem;
  margin-bottom: 1rem;
}
.terminal-summary p {
  margin: 0.6rem 0;
  overflow-wrap: anywhere;
}
.page-heading h1 {
  display: flex;
  align-items: center;
  gap: 10px;
}
.page-heading h1 .icon {
  color: var(--forest);
}
.panel-head h3 {
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel-head h3 .icon {
  color: var(--muted);
}
.panel-head-actions .primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
}
.panel-head-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: var(--muted);
}
.telemetry-panel .panel-body {
  display: grid;
  gap: 18px;
}
.telemetry-cells {
  border: 1px solid var(--line);
}
.chart-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}
.chart-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.chart-block {
  min-width: 0;
}
.chart-block h4 {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
}
.chart-block h4 .icon {
  color: var(--muted);
}
.version-compare {
  margin-top: 17px;
  border: 1px solid var(--line);
}
.version-compare h3 {
  margin: 0;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.compare-row {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  padding: 9px 14px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.compare-row:last-child {
  border-bottom: 0;
}
.compare-row > span {
  color: var(--muted);
}
.compare-row > b {
  min-width: 0;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.compare-head {
  padding-block: 7px;
  background: var(--surface-2);
  font-size: 11px;
  letter-spacing: 0.04em;
}
.compare-head > span {
  color: var(--muted);
}
.capability-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 20px;
}
.capability-grid > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.capability-grid span {
  color: var(--muted);
}
.capability-grid b {
  font-weight: 500;
}
.capability-grid b.off {
  color: var(--muted);
}
.mobile-only {
  display: none;
}
@media (max-width: 640px) {
  .mobile-only {
    display: inline-flex;
    margin-top: 7px;
  }
  .col-type,
  .col-model,
  .col-sync,
  .col-action,
  .col-runtime {
    display: none;
  }
  .device-cell {
    white-space: normal;
  }
  .compare-row {
    grid-template-columns: 64px minmax(0, 1fr) minmax(0, 1fr);
    gap: 6px;
    padding-inline: 11px;
  }
  .compare-row > b {
    font-size: 12px;
  }
  .telemetry-cells > div:last-child {
    grid-column: 1 / -1;
    border-top: 1px solid var(--line);
  }
  .chart-grid :deep(.spark svg) {
    height: 64px;
  }
}
@media (max-width: 900px) {
  .chart-grid,
  .chart-grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
