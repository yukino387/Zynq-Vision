<script setup lang="ts">
import InfoFields from "../components/InfoFields.vue";
import { chinese, displayName, fieldLabel } from "@vision/shared";
import { ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import QRCode from "qrcode";
import type { Named } from "../types";
import { api, post, download } from "../api";
import { useNotificationStore } from "../stores/notifications";
import { useList } from "../composables/useList";
import { useDeviceStore } from "../stores/devices";
import Drawer from "../components/Drawer.vue";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import SortableTh from "../components/SortableTh.vue";
import Pager from "../components/Pager.vue";
const route = useRoute(),
  devices = useDeviceStore(),
  notices = useNotificationStore(),
  tab = computed(() =>
    String(route.params.tab || route.meta.defaultTab || "health"),
  );
const endpoint = computed(() =>
    tab.value === "users"
      ? "/users"
      : tab.value === "audit"
        ? "/audit"
        : "/system/jobs",
  ),
  list = useList<Named>(endpoint),
  health = ref<Record<string, unknown> | null>(null),
  error = ref(""),
  loading = ref(false),
  form = ref(false),
  name = ref(""),
  username = ref(""),
  password = ref(""),
  role = ref("OPERATOR"),
  busy = ref(false),
  qr = ref(""),
  pairing = ref<unknown>(null),
  serverUrl = ref(location.origin),
  stationId = ref(""),
  qrType = ref("SERVER"),
  deviceId = ref(""),
  stations = ref<Named[]>([]);
async function load() {
  loading.value = true;
  error.value = "";
  try {
    health.value = await api("/system");
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
async function create() {
  busy.value = true;
  try {
    await post("/users", {
      name: name.value,
      username: username.value,
      password: password.value,
      role: role.value,
    });
    password.value = "";
    form.value = false;
    await list.load();
    notices.add("用户已创建");
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function pair() {
  busy.value = true;
  try {
    if (qrType.value === "SERVER") {
      pairing.value = await post("/system/pairing", {
        stationId: stationId.value || undefined,
        serverUrl: serverUrl.value,
      });
    } else if (qrType.value === "STATION") {
      const station = stations.value.find((s) => s.id === stationId.value);
      if (!station) throw new Error("请选择工位");
      const attached = station.devices as { id: string }[];
      pairing.value = {
        type: "STATION",
        protocolVersion: 1,
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
const networks = computed(
  () => (health.value?.network ?? []) as { address: string; url: string }[],
);
const recentErrors = computed(
  () =>
    (health.value?.errors ?? []) as {
      id: string;
      type: string;
      error: string;
    }[],
);
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
    <button
      @click="
        load();
        list.load();
      "
    >
      刷新状态
    </button>
  </div>
  <AsyncState
    v-if="tab === 'health'"
    :loading="loading"
    :error="error"
    @retry="load"
    ><div class="two-columns">
      <section
        v-for="key in ['server', 'database', 'storage', 'websocket']"
        :key="key"
        class="panel"
      >
        <div class="panel-head">
          <h3>{{ fieldLabel(key) }}</h3>
        </div>
        <div class="panel-body">
          <InfoFields :value="health?.[key]" />
        </div>
      </section>
    </div>
    <section class="panel section-space">
      <div class="panel-head">
        <h3>网络与队列</h3>
        <span class="mono">{{ health?.pendingJobs }} 待同步</span>
      </div>
      <div class="panel-body">
        <div
          v-for="(network, index) in networks"
          :key="index"
          class="list-line"
        >
          <span>{{ network.address }}</span
          ><a :href="network.url" target="_blank" rel="noreferrer">{{
            network.url
          }}</a>
        </div>
        <div v-if="!networks.length" class="note">暂无可用网络地址</div>
        <h3>最近任务错误</h3>
        <div v-if="!recentErrors.length" class="note">暂无任务错误</div>
        <div v-for="item in recentErrors" :key="item.id" class="error-box">
          {{ chinese(item.type) }}：{{ item.error }}
        </div>
      </div>
    </section></AsyncState
  >
  <section v-else-if="tab === 'pairing'" class="panel">
    <div class="panel-head">
      <h3>连接移动采样端</h3>
      <span class="tag">{{
        qrType === "SERVER" ? "有效期 5 分钟" : "工位与设备"
      }}</span>
    </div>
    <div class="panel-body">
      <div class="two-columns">
        <div>
          <label
            >二维码类型<select v-model="qrType">
              <option value="SERVER">服务器配对</option>
              <option value="STATION">工位配对</option>
              <option value="DEVICE">设备配对</option>
            </select></label
          >
          <label v-if="qrType === 'DEVICE'"
            >设备<select v-model="deviceId">
              <option value="">选择设备</option>
              <option v-for="d in devices.devices" :key="d.id" :value="d.id">
                {{ displayName(d.name) }}
              </option>
            </select></label
          >
          <label
            >服务器地址<input
              v-model="serverUrl"
              type="url"
              placeholder="http://服务器地址:3000" /></label
          ><label
            >关联工位<select v-model="stationId">
              <option value="">未指定</option>
              <option v-for="s in stations" :key="s.id" :value="s.id">
                {{ displayName(s.name) }}
              </option>
            </select></label
          ><button class="primary" @click="pair" :disabled="busy">
            生成二维码
          </button>
          <p class="note">使用移动端扫描二维码完成配对。</p>
          <a :href="`${serverUrl}/mobile/`" target="_blank" rel="noreferrer"
            >打开移动端</a
          >
        </div>
        <div v-if="qr">
          <img :src="qr" alt="一次性服务器配对二维码" width="280" />
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
      </div>
    </div>
  </section>
  <template v-else
    ><div class="toolbar">
      <input
        v-if="tab === 'users'"
        v-model="list.search.value"
        placeholder="搜索用户"
      /><button @click="list.filter">刷新列表</button
      ><button v-if="tab === 'users'" class="primary" @click="form = true">
        创建用户</button
      ><span class="right inline-count">{{ list.total.value }} 条记录</span>
    </div>
    <AsyncState
      :loading="list.loading.value"
      :error="list.error.value"
      :empty="!list.items.value.length"
      @retry="list.load"
      ><div class="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ tab === "users" ? "用户" : "操作 / 任务" }}</th>
              <th>{{ tab === "users" ? "角色" : "对象编号" }}</th>
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
                <strong>{{
                  r.name ? displayName(r.name) : chinese(r.action ?? r.type)
                }}</strong
                ><small class="mono">{{ r.username ?? r.id }}</small>
              </td>
              <td>
                {{ r.role ? chinese(r.role) : r.entityId
                }}<small class="mono">{{ r.requestId }}</small>
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
              <td>
                <button
                  v-if="r.type === 'DATASET_EXPORT' && r.status === 'COMPLETED'"
                  @click="
                    download(
                      `/system/jobs/${r.id}/content`,
                      `dataset-${r.id}.zip`,
                    ).catch(notices.error)
                  "
                  class="table-action"
                >
                  下载导出</button
                ><small v-if="r.error" class="danger">{{ r.error }}</small>
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
        (pg) => {
          list.page.value = pg;
          list.load();
        }
      "
      @update:page-size="list.setPageSize" /></template
  ><Drawer v-if="form" title="创建用户" @close="form = false"
    ><form @submit.prevent="create">
      <label>姓名<input v-model="name" required /></label
      ><label>用户名<input v-model="username" required /></label
      ><label
        >密码（至少 12 位）<input
          v-model="password"
          type="password"
          minlength="12"
          required
          autocomplete="new-password" /></label
      ><label
        >角色<select v-model="role">
          <option value="ADMIN">{{ chinese("ADMIN") }}</option>
          <option value="ENGINEER">{{ chinese("ENGINEER") }}</option>
          <option value="OPERATOR">{{ chinese("OPERATOR") }}</option>
        </select></label
      ><button class="primary" :disabled="busy">创建用户</button>
    </form></Drawer
  >
</template>
