<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import QRCode from "qrcode";
import { chinese, displayName } from "@vision/shared";
import type { Named } from "../types";
import { api, post, download } from "../api";
import { useNotificationStore } from "../stores/notifications";
import { useList } from "../composables/useList";
import { useDeviceStore } from "../stores/devices";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import SortableTh from "../components/SortableTh.vue";
import Pager from "../components/Pager.vue";
import Icon from "../components/Icon.vue";

interface HealthDevice {
  id: string;
  source: string;
  network: string;
  runtime: string;
}
interface Health {
  server?: { status?: string; uptimeSeconds?: number; version?: string };
  database?: {
    engine?: string;
    journalMode?: string;
    pages?: number;
    sizeBytes?: number;
    latestMigration?: string;
  };
  storage?: {
    status?: string;
    groups?: { kind: string; _count: number; _sum?: { size?: number } }[];
    freeBytes?: number;
    exportsBytes?: number;
  };
  websocket?: { path?: string; clients?: number };
  pendingJobs?: number;
  errors?: { id: string; type: string; error: string }[];
  devices?: HealthDevice[];
  network?: {
    address: string;
    url: string;
    interfaceName: string;
    mobile: boolean;
  }[];
}

const route = useRoute(),
  devices = useDeviceStore(),
  notices = useNotificationStore(),
  tab = computed(() =>
    String(route.params.tab || route.meta.defaultTab || "health"),
  ),
  endpoint = computed(() =>
    tab.value === "audit" ? "/audit" : "/system/jobs",
  ),
  list = useList<Named>(endpoint),
  health = ref<Health | null>(null),
  error = ref(""),
  loading = ref(false),
  busy = ref(false),
  qr = ref(""),
  pairing = ref<unknown>(null),
  serverUrl = ref(location.origin),
  serverAddressEdited = ref(false),
  stationId = ref(""),
  qrType = ref("SERVER"),
  deviceId = ref(""),
  stations = ref<Named[]>([]);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    health.value = await api<Health>("/system");
    if (
      !serverAddressEdited.value &&
      /^(localhost|127\..*|0\.0\.0\.0|\[::1\])$/i.test(location.hostname)
    )
      serverUrl.value =
        health.value.network?.find((entry) => entry.mobile)?.url ?? "";
    stations.value = (await api<{ items: Named[] }>("/stations")).items;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
watch(
  tab,
  () => {
    if (["health", "pairing"].includes(tab.value)) void load();
  },
  { immediate: true },
);

const pairingTypes = [
  { value: "SERVER", label: "连接服务器（一次性码）", icon: "network" },
  { value: "STATION", label: "工位快捷选择", icon: "device" },
  { value: "DEVICE", label: "设备快捷选择", icon: "pairing" },
];
const mobileAddresses = computed(
  () => health.value?.network?.filter((entry) => entry.mobile) ?? [],
);
watch([serverUrl, qrType, stationId, deviceId], () => {
  qr.value = "";
  pairing.value = null;
});
async function pair() {
  if (busy.value) return;
  busy.value = true;
  try {
    const url = new URL(serverUrl.value.trim());
    if (
      !/^https?:$/.test(url.protocol) ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    )
      throw new Error(
        "请输入完整服务器地址，例如 http://192.168.1.100:3000，不要附加页面路径",
      );
    if (
      /^(localhost|.*\.localhost|127\..*|0\..*|\[::1\]|\[::\])$/i.test(
        url.hostname,
      )
    )
      throw new Error(
        "手机不能连接电脑的 localhost 地址，请选择下方 WLAN 地址后重新生成二维码",
      );
    const address = url.origin;
    if (qrType.value === "SERVER") {
      pairing.value = await post("/system/pairing", {
        stationId: stationId.value || undefined,
        serverUrl: address,
      });
    } else if (qrType.value === "STATION") {
      const station = stations.value.find((s) => s.id === stationId.value);
      if (!station) throw new Error("请选择工位");
      const attached = station.devices as { id: string }[];
      pairing.value = {
        type: "STATION",
        protocolVersion: 1,
        serverUrl: address,
        stationId: station.id,
        code: station.code,
        defaultDeviceId: attached[0]?.id ?? null,
      };
    } else {
      if (!deviceId.value) throw new Error("请选择设备");
      const device = await api<{
        id: string;
        serialNumber: string;
        stationId: string | null;
      }>(`/devices/${deviceId.value}`);
      pairing.value = {
        type: "DEVICE",
        protocolVersion: 1,
        serverUrl: address,
        deviceId: device.id,
        serialNumber: device.serialNumber,
        stationId: device.stationId,
      };
    }
    qr.value = await QRCode.toDataURL(JSON.stringify(pairing.value), {
      width: 280,
      margin: 2,
      color: { dark: "#1d2129", light: "#ffffff" },
    });
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}

function formatBytes(value: number | undefined) {
  if (value === undefined || value === null || Number.isNaN(value))
    return "未上报";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024,
    unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit++;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unit]}`;
}
function formatUptime(seconds: number | undefined) {
  if (seconds === undefined) return "未上报";
  const days = Math.floor(seconds / 86400),
    hours = Math.floor((seconds % 86400) / 3600),
    minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days} 天 ${hours} 小时`;
  if (hours) return `${hours} 小时 ${minutes} 分`;
  return `${Math.max(1, minutes)} 分钟`;
}

const pendingJobs = computed(() => health.value?.pendingJobs ?? 0);
const networks = computed(() => health.value?.network ?? []);
const recentErrors = computed(() => health.value?.errors ?? []);
const healthDevices = computed(() =>
  (health.value?.devices ?? [])
    .filter((d) => d.source !== "SIMULATION")
    .map((d) => ({
      ...d,
      name:
        devices.devices.find((item) => item.id === d.id)?.name ??
        `设备 ${d.id.slice(-6)}`,
    })),
);
const healthCards = computed(() => {
  const value = health.value;
  if (!value) return [];
  const groups = value.storage?.groups ?? [];
  return [
    {
      key: "server",
      icon: "server",
      label: "服务进程",
      status: value.server?.status ?? "UNKNOWN",
      value: `运行 ${formatUptime(value.server?.uptimeSeconds)}`,
      detail: `版本 ${value.server?.version ?? "未上报"}`,
    },
    {
      key: "database",
      icon: "database",
      label: "数据库",
      status: "READY",
      value: formatBytes(value.database?.sizeBytes),
      detail: `${value.database?.engine ?? "SQLite"} · ${value.database?.journalMode ?? "日志模式未上报"} · ${value.database?.pages ?? "未上报"} 页`,
    },
    {
      key: "storage",
      icon: "storage",
      label: "文件存储",
      status: value.storage?.status ?? "UNKNOWN",
      value: `剩余 ${formatBytes(value.storage?.freeBytes)}`,
      detail: `${groups.length} 类资产 · 导出 ${formatBytes(value.storage?.exportsBytes)}`,
    },
    {
      key: "websocket",
      icon: "network",
      label: "实时连接",
      status: "READY",
      value: `${value.websocket?.clients ?? 0} 个连接`,
      detail: value.websocket?.path ?? "/ws",
    },
  ];
});
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>
        <Icon
          :name="
            tab === 'pairing'
              ? 'pairing'
              : tab === 'jobs'
                ? 'jobs'
                : tab === 'audit'
                  ? 'audit'
                  : 'activity'
          "
          :size="22"
        />
        {{
          route.meta.tabs?.find((t) => t.tab === tab)?.label ?? route.meta.title
        }}
      </h1>
      <p v-if="tab === 'health'" class="mono">
        {{ health ? chinese(health.server?.status) : "读取中" }} ·
        数据与存储实时状态
      </p>
      <p v-else-if="tab === 'pairing'">
        为移动采样端生成服务器连接码，或工位/设备快捷选择码
      </p>
      <p v-else>
        {{ tab === "audit" ? "管理员操作留痕" : "后台异步任务与导出" }}
      </p>
    </div>
    <button
      v-if="tab === 'health'"
      :class="{ busy: loading }"
      :disabled="loading"
      @click="load"
    >
      <Icon name="refresh" :size="16" /> 刷新状态
    </button>
  </div>

  <AsyncState
    v-if="tab === 'health'"
    :loading="loading"
    :error="error"
    @retry="load"
  >
    <div class="health-grid">
      <article v-for="card in healthCards" :key="card.key" class="health-card">
        <div class="health-icon"><Icon :name="card.icon" :size="22" /></div>
        <div class="health-body">
          <div class="health-title">
            <span>{{ card.label }}</span
            ><Status :value="card.status" />
          </div>
          <strong>{{ card.value }}</strong>
          <small>{{ card.detail }}</small>
        </div>
      </article>
    </div>

    <div class="health-columns">
      <section class="panel">
        <div class="panel-head">
          <h3><Icon name="network" /> 网络地址</h3>
          <span class="tag">{{ networks.length }} 个</span>
        </div>
        <div class="panel-body">
          <div
            v-for="network in networks"
            :key="network.address"
            class="health-row"
          >
            <Icon name="external" :size="16" />
            <span class="mono name">{{ network.address }}</span>
            <a :href="network.url" target="_blank" rel="noreferrer">{{
              network.url
            }}</a>
          </div>
          <div v-if="!networks.length" class="note">暂无可用网络地址</div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head">
          <h3><Icon name="device" /> 设备与队列</h3>
          <span class="tag" :class="{ warn: pendingJobs > 0 }"
            >{{ pendingJobs }} 待同步</span
          >
        </div>
        <div class="panel-body">
          <div
            v-for="device in healthDevices"
            :key="device.id"
            class="health-row"
          >
            <Icon name="device" :size="16" />
            <span class="name">{{ displayName(device.name) }}</span>
            <Status :value="device.runtime" chip />
            <Status :value="device.network" />
          </div>
          <div v-if="!healthDevices.length" class="note">
            还没有已注册的真实设备
          </div>
        </div>
      </section>
    </div>

    <section class="panel section-space">
      <div class="panel-head">
        <h3><Icon name="alert" /> 最近任务错误</h3>
        <span class="tag" :class="{ crit: recentErrors.length }"
          >{{ recentErrors.length }} 条</span
        >
      </div>
      <div class="panel-body">
        <div v-if="!recentErrors.length" class="note">暂无任务错误</div>
        <div v-for="item in recentErrors" :key="item.id" class="error-box">
          <Icon name="alert" :size="15" /> {{ chinese(item.type) }}：{{
            item.error
          }}
        </div>
      </div>
    </section>
  </AsyncState>

  <section v-else-if="tab === 'pairing'" class="panel">
    <div class="panel-head">
      <h3><Icon name="pairing" /> 连接移动采样端</h3>
      <div class="panel-head-actions row-actions">
        <span class="tag">{{
          qrType === "SERVER" ? "一次性 · 5 分钟有效" : "快捷选择 · 不代替登录"
        }}</span>
        <button
          class="primary"
          :class="{ busy }"
          :disabled="busy"
          @click="pair"
        >
          <Icon name="pairing" :size="16" /> 生成二维码
        </button>
      </div>
    </div>
    <div class="panel-body">
      <div class="pairing-switch">
        <button
          v-for="type in pairingTypes"
          :key="type.value"
          :class="{ active: qrType === type.value }"
          @click="qrType = type.value"
        >
          <Icon :name="type.icon" :size="20" />
          <span>{{ type.label }}</span>
        </button>
      </div>
      <div class="two-columns">
        <div>
          <label v-if="qrType === 'DEVICE'"
            >设备<UiSelect v-model="deviceId">
              <option value="">选择设备</option>
              <option v-for="d in devices.devices" :key="d.id" :value="d.id">
                {{ displayName(d.name) }}
              </option>
            </UiSelect></label
          >
          <label
            >服务器地址<input
              v-model="serverUrl"
              @input="serverAddressEdited = true"
              type="url"
              placeholder="http://服务器地址:3000"
          /></label>
          <div class="row-actions">
            <button
              v-for="address in mobileAddresses"
              :key="address.url"
              class="table-action"
              @click="
                serverAddressEdited = true;
                serverUrl = address.url;
              "
            >
              {{ address.interfaceName }} · {{ address.url }}
            </button>
            <button class="table-action" :disabled="loading" @click="load">
              刷新网络地址
            </button>
          </div>
          <p class="note">
            电脑连接手机热点时，选择 WLAN 地址。localhost
            指向手机自己；切换热点后请刷新地址并重新生成二维码。
          </p>
          <label v-if="qrType !== 'DEVICE'"
            >关联工位<UiSelect v-model="stationId">
              <option value="">未指定</option>
              <option v-for="s in stations" :key="s.id" :value="s.id">
                {{ displayName(s.name) }}
              </option>
            </UiSelect></label
          >
          <p class="note">
            {{
              qrType === "SERVER"
                ? "一次性码 5 分钟内有效；扫码后手机仍需用现场账号登录。"
                : "快捷选择码只预设工位/设备，不代替登录；二维码已包含当前服务器地址。"
            }}
          </p>
          <a :href="`${serverUrl}/mobile/`" target="_blank" rel="noreferrer"
            ><Icon name="external" :size="15" /> 打开移动端</a
          >
        </div>
        <div v-if="qr">
          <img :src="qr" alt="配对二维码" width="280" />
          <details>
            <summary>手动配对内容</summary>
            <textarea
              :value="JSON.stringify(pairing)"
              rows="5"
              readonly
              style="width: 100%"
            />
          </details>
        </div>
        <div v-else class="pairing-placeholder">
          <Icon name="pairing" :size="40" />
          <span>选择类型并生成二维码</span>
        </div>
      </div>
    </div>
  </section>

  <template v-else>
    <div class="panel">
      <div class="panel-head">
        <h3>
          <Icon :name="tab === 'audit' ? 'audit' : 'jobs'" />
          {{ tab === "audit" ? "操作记录" : "任务记录" }}
        </h3>
        <div class="panel-head-actions row-actions">
          <span class="mono">{{ list.total.value }} 条</span>
          <button
            class="table-action"
            :class="{ busy: list.loading.value }"
            :disabled="list.loading.value"
            @click="list.load"
          >
            <Icon name="refresh" :size="14" /> 刷新
          </button>
        </div>
      </div>
      <AsyncState
        :loading="list.loading.value"
        :error="list.error.value"
        :empty="!list.items.value.length"
        @retry="list.load"
      >
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{{ tab === "audit" ? "操作" : "操作 / 任务" }}</th>
                <th>{{ tab === "audit" ? "对象" : "对象编号" }}</th>
                <th>状态</th>
                <!-- 用户/审计/任务队列三个接口的白名单交集只有 createdAt -->
                <SortableTh
                  field="createdAt"
                  label="时间"
                  :active="list.sort.value"
                  :order="list.order.value"
                  @sort="list.sortBy"
                />
                <th>输出</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in list.items.value" :key="r.id">
                <td>
                  <strong>{{ chinese(r.action ?? r.type) }}</strong>
                  <small class="mono">{{ r.username ?? r.id }}</small>
                </td>
                <td>
                  {{ r.entityId ?? "平台操作"
                  }}<small v-if="r.requestId" class="mono"
                    >请求编号：{{ r.requestId }}</small
                  >
                </td>
                <td>
                  <Status
                    :value="
                      String(
                        r.result ??
                          r.status ??
                          (r.disabled ? 'DISABLED' : 'READY'),
                      )
                    "
                  />
                </td>
                <td>{{ new Date(r.createdAt).toLocaleString() }}</td>
                <td class="action-cell">
                  <div class="row-actions">
                    <button
                      v-if="
                        r.type === 'DATASET_EXPORT' && r.status === 'COMPLETED'
                      "
                      @click="
                        download(
                          `/system/jobs/${r.id}/content`,
                          `dataset-${r.id}.zip`,
                        ).catch(notices.error)
                      "
                      class="table-action"
                    >
                      <Icon name="download" :size="14" /> 下载导出
                    </button>
                  </div>
                  <small v-if="r.error" class="danger">{{ r.error }}</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </AsyncState>
    </div>
    <Pager
      :page="list.page.value"
      :total="list.total.value"
      :page-size="list.pageSize.value"
      @update:page="
        (pg) => {
          list.page.value = pg;
          list.load();
        }
      "
      @update:page-size="list.setPageSize"
    />
  </template>
</template>

<style scoped>
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
.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 16px;
}
.health-card {
  display: flex;
  gap: 16px;
  padding: 18px 20px;
  background: var(--surface);
  border: 1px solid var(--line);
  min-width: 0;
}
.health-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  background: var(--surface-2);
  color: var(--forest);
  flex: none;
}
.health-body {
  min-width: 0;
  display: grid;
  gap: 4px;
}
.health-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
}
.health-body strong {
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.health-body small {
  color: var(--muted);
}
.health-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.health-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}
.health-row:last-child {
  border-bottom: 0;
}
.health-row .icon {
  color: var(--muted);
}
.health-row .name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.health-row a {
  font-family: var(--mono);
  font-size: 12px;
}
.error-box {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pairing-switch {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 20px;
}
.pairing-switch button {
  display: grid;
  place-items: center;
  gap: 7px;
  padding: 14px 8px;
}
.pairing-switch button.active {
  border-color: var(--forest);
  background: color-mix(in srgb, var(--forest) 9%, var(--surface));
  color: var(--forest);
}
.pairing-placeholder {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 220px;
  color: var(--muted);
  border: 1px dashed var(--line);
}
@media (max-width: 900px) {
  .health-columns {
    grid-template-columns: 1fr;
  }
  .pairing-switch {
    grid-template-columns: 1fr;
  }
}
</style>
