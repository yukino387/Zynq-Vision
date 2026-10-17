<script setup lang="ts">
import InfoFields from "../components/InfoFields.vue";
import { chinese, displayName, fieldLabel } from "@vision/shared";
import { ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import type { Named } from "../types";
import type { DeviceSnapshot, Model, ResidentModel } from "@vision/contracts";
import { api, post } from "../api";
import { useDeviceStore } from "../stores/devices";
import { useNotificationStore } from "../stores/notifications";
import { useAuthStore } from "../stores/auth";
import Status from "../components/Status.vue";
import Drawer from "../components/Drawer.vue";
import AsyncState from "../components/AsyncState.vue";
import SortableTh from "../components/SortableTh.vue";
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
  type = ref("SIMULATOR"),
  stationId = ref(""),
  stations = ref<Named[]>([]),
  command = ref("GET_STATUS"),
  fault = ref("NONE"),
  brightness = ref(0),
  targetModel = ref(""),
  targetPlan = ref(""),
  busy = ref(false);
/** 遥测是微秒，界面按毫秒显示。 */
const metric = (us: number | undefined) =>
  us === undefined ? "—" : (us / 1000).toFixed(1);
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
    rows.value = (
      await api<{ items: Named[] }>(
        tab.value === "stations" ? "/stations" : "/events",
      )
    ).items;
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
async function switchModel(entry: ResidentModel) {
  if (!selected.value) return;
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
  if (!selected.value) return;
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
  if (!selected.value) return;
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
          command.value === "FAULT"
            ? fault.value
            : command.value === "SET_BRIGHTNESS"
              ? brightness.value
              : undefined,
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
            type: type.value,
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
        {{
          route.meta.tabs?.find((t) => t.tab === tab)?.label ?? route.meta.title
        }}
      </h1>
      <p class="mono">
        {{ displayName(devices.current?.name ?? "（无设备）") }} ·
        {{ devices.current?.protocolVersion ?? "协议版本未上报" }}
      </p>
    </div>
    <div class="heading-actions">
      <button :class="{ busy: loading }" :disabled="loading" @click="load">
        刷新</button
      ><button
        class="primary"
        v-if="auth.engineer && ['registry', 'stations'].includes(tab)"
        @click="creating = true"
      >
        {{ tab === "stations" ? "创建工位" : "注册设备" }}
      </button>
    </div>
  </div>

  <details v-if="tab === 'registry'" class="advanced-metrics" open>
    <summary>查看实时运行指标</summary>
    <!-- 从工作台搬来的运行遥测：操作工不需要看，工程师需要常显。 -->
    <div class="panel section-space">
      <div class="panel-head">
        <h3>最近一帧耗时</h3>
        <Status :value="devices.current?.connectionState" />
      </div>
      <div class="cells">
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
    </div>
  </details>
  <AsyncState
    :loading="loading"
    :error="error"
    :empty="!rows.length && !devices.devices.length"
    :hint="
      tab === 'stations'
        ? '还没有工位。工位用于把设备和产品绑在一起。'
        : '还没有设备。注册设备后，它上报的遥测会显示在顶部。'
    "
    @retry="load"
    ><div v-if="tab === 'registry'" class="panel table-wrap">
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
            <th>来源</th>
            <SortableTh
              field="connectionState"
              label="网络"
              :active="devSort"
              :order="devOrder"
              @sort="sortDevices"
            />
            <SortableTh
              field="runtimeState"
              label="运行"
              :active="devSort"
              :order="devOrder"
              @sort="sortDevices"
            />
            <th>实际模型</th>
            <th>同步状态</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in deviceRows" :key="d.id">
            <td>
              <strong>{{ displayName(d.name) }}</strong
              ><small class="mono">{{ d.id.slice(-10) }}</small>
            </td>
            <td>
              <span
                class="tag"
                :class="{ simulated: d.source === 'SIMULATION' }"
                >{{ chinese(d.type) }}</span
              >
            </td>
            <td><Status :value="d.connectionState" /></td>
            <td><Status :value="d.runtimeState" /></td>
            <td class="mono">
              {{ d.reportedState.modelVersion ?? "未上报" }}
            </td>
            <td><Status :value="d.syncState" /></td>
            <td>
              <button class="table-action" @click="open(d)">控制与详情</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else-if="tab === 'debug'" class="panel">
      <div class="panel-head">
        <h3>实时事件 / 最近 30 条</h3>
        <Status :value="devices.connected ? 'ONLINE' : 'OFFLINE'" />
      </div>
      <div class="panel-body">
        <pre v-for="e in devices.recent" :key="e.sequence">{{
          JSON.stringify(e, null, 2)
        }}</pre>
        <div v-if="!devices.recent.length" class="empty">暂无事件</div>
      </div>
    </div>
    <div v-else-if="tab === 'stations'" class="panel table-wrap">
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
    <div v-else class="panel">
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
        <div v-if="!rows.length" class="empty">
          暂无设备事件
          <p class="muted">
            设备上报状态变化、采样完成或报错时会在这里留一条。设备离线期间不会有新事件。
          </p>
        </div>
      </div>
    </div></AsyncState
  ><Drawer
    v-if="selected"
    :title="displayName(selected.name)"
    @close="selected = null"
    ><div class="toolbar">
      <Status :value="selected.connectionState" /><Status
        :value="selected.runtimeState"
      /><span v-if="selected.source === 'SIMULATION'" class="tag simulated"
        >模拟设备</span
      >
    </div>
    <p class="note" v-if="selected.type === 'ZYNQ'">
      连接设备会接管图像接收，请先断开其他上位机。
    </p>
    <div class="toolbar" v-if="auth.engineer">
      <button class="primary" @click="action('connect')" :disabled="busy">
        连接设备</button
      ><button @click="action('disconnect')" :disabled="busy">断开连接</button>
    </div>
    <div class="two-columns">
      <section>
        <h3>目标版本</h3>
        <InfoFields
          :value="selected.desiredState"
          :fields="['modelVersion', 'planVersion', 'inspectionEnabled']"
        />
      </section>
      <section>
        <h3>实际版本</h3>
        <InfoFields
          :value="selected.reportedState"
          :fields="['modelVersion', 'planVersion', 'inspectionEnabled']"
        />
      </section>
    </div>
    <Status :value="selected.syncState" />
    <template v-if="residentModels.length">
      <h3 class="section-space">设备模型库</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>槽位</th>
              <th>版本</th>
              <th>摘要</th>
              <th>状态</th>
              <th></th>
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
              <td>
                <button
                  v-if="!m.active"
                  class="table-action"
                  :disabled="busy"
                  @click="switchModel(m)"
                >
                  切换
                </button>
                <button
                  class="table-action"
                  :disabled="busy || m.active || m.previous"
                  @click="removeModel(m)"
                >
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="note">
        切换会照走部署流程；制品已经在设备上时板端跳过传输直接激活。
      </p>
    </template>
    <p v-else-if="selected.capabilities.localStorage" class="note">
      设备 SD 卡上还没有已提交的模型。
    </p>
    <h3 class="section-space">设备能力</h3>
    <dl class="key-values">
      <template v-for="(value, key) in selected.capabilities" :key="key"
        ><dt>{{ fieldLabel(key) }}</dt>
        <dd>{{ value ? "支持" : "不支持" }}</dd></template
      >
    </dl>
    <template v-if="auth.engineer"
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
          <option v-if="selected.type === 'SIMULATOR'" value="FAULT">
            模拟故障
          </option>
        </select></label
      ><label v-if="command === 'SET_BRIGHTNESS'"
        >亮度<input
          v-model.number="brightness"
          type="number"
          min="-4"
          max="4" /></label
      ><label v-if="command === 'FAULT'"
        >模拟故障<select v-model="fault">
          <option
            v-for="f in [
              'NONE',
              'NETWORK_LOST',
              'DEVICE_TIMEOUT',
              'INVALID_MODEL',
              'CHECKSUM_ERROR',
              'INFERENCE_ERROR',
              'DEPLOYMENT_FAILED',
              'LOW_FPS',
              'HIGH_LATENCY',
              'QUEUE_OVERFLOW',
            ]"
            :key="f"
            :value="f"
          >
            {{ chinese(f) }}
          </option>
        </select></label
      ><button @click="action('command')" :disabled="busy">发送命令</button>
      <h3 class="section-space">设置目标版本</h3>
      <label
        >目标模型版本<select v-model="targetModel">
          <option value="">未设置</option>
          <option v-for="m in residentModels" :key="m.index" :value="m.version">
            {{ m.version }}
          </option>
        </select></label
      ><label>目标方案版本<input v-model="targetPlan" /></label
      ><button @click="action('desired')" :disabled="busy">保存目标版本</button>
    </template>
    <details class="section-space">
      <summary>原始状态 / 命令 / 事件</summary>
      <pre>{{ JSON.stringify(detail, null, 2) }}</pre>
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
          >类型<select v-model="type">
            <option value="SIMULATOR">{{ chinese("SIMULATOR") }}</option>
            <option value="ZYNQ">{{ chinese("ZYNQ") }}</option>
          </select></label
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
