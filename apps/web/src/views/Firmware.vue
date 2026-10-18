<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { displayName } from "@vision/shared";
import type { FirmwareInfo } from "@vision/contracts";
import type { Named } from "../types";
import { api, errorText, post } from "../api";
import { useAuthStore } from "../stores/auth";
import { useDeviceStore } from "../stores/devices";
import { useNotificationStore } from "../stores/notifications";
import { useList } from "../composables/useList";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import Pager from "../components/Pager.vue";
import Drawer from "../components/Drawer.vue";
import SortableTh from "../components/SortableTh.vue";

const route = useRoute(),
  auth = useAuthStore(),
  devices = useDeviceStore(),
  notices = useNotificationStore();
const tab = computed(() =>
  String(route.params.tab || route.meta.defaultTab || "registry"),
);
const endpoint = computed(() =>
  tab.value === "deployments" ? "/firmware-deployments" : "/firmware",
);
const list = useList<Named>(endpoint);
const upload = ref(false),
  uploading = ref(false),
  file = ref<File | null>(null),
  uploadName = ref(""),
  notes = ref(""),
  detail = ref<Named | null>(null),
  deploying = ref<Named | null>(null),
  deviceId = ref(""),
  info = ref<FirmwareInfo | null>(null),
  infoError = ref(""),
  busy = ref(false);

const firmware = (row: Named) =>
  row as Named & {
    version: string;
    sha256: string;
    size: number;
    imageSize: number;
    entry: number;
    segments: unknown[];
    notes: string | null;
    _count?: { deployments: number };
    asset?: { originalName: string };
  };
const deployment = (row: Named) =>
  row as Named & {
    deviceId: string;
    previousVersion: string | null;
    previousSlot: number | null;
    progress: number;
    error: string | null;
    receipt: Record<string, unknown>;
    firmware: ReturnType<typeof firmware>;
    device?: { name: string };
  };
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
const deviceName = (row: Named) =>
  deployment(row).device?.name ??
  devices.devices.find((d) => d.id === deployment(row).deviceId)?.name ??
  deployment(row).deviceId;
const detailFirmware = computed(() =>
  !detail.value
    ? null
    : "previousVersion" in detail.value
      ? deployment(detail.value).firmware
      : firmware(detail.value),
);
const kb = (bytes: number) => `${(bytes / 1024).toFixed(1)} KiB`;
const digest = (value: string | undefined) =>
  value ? `${value.slice(0, 12)}…${value.slice(-8)}` : "—";

async function loadInfo() {
  info.value = null;
  infoError.value = "";
  if (!deviceId.value) return;
  try {
    info.value = await api<FirmwareInfo>(`/devices/${deviceId.value}/firmware`);
  } catch (error) {
    infoError.value = errorText(error);
  }
}
function openDeploy(row: Named) {
  deploying.value = row;
  deviceId.value = devices.current?.id ?? "";
}
watch(deviceId, loadInfo);
function closeDeploy() {
  deploying.value = null;
  info.value = null;
  infoError.value = "";
}
async function deploy() {
  if (!deploying.value || !deviceId.value) return;
  busy.value = true;
  try {
    await post(`/firmware/${deploying.value.id}/deploy`, {
      deviceId: deviceId.value,
    });
    closeDeploy();
    await list.load();
    notices.add("固件更新已排队；设备会在试运行成功后确认版本");
  } catch (error) {
    notices.error(error);
  } finally {
    busy.value = false;
  }
}
async function rollback(row: Named, target: "PREVIOUS" | "GOLDEN") {
  busy.value = true;
  try {
    await post(`/firmware-deployments/${row.id}/rollback`, { target });
    await list.load();
    notices.add("回滚已提交，等待设备重启确认");
  } catch (error) {
    notices.error(error);
  } finally {
    busy.value = false;
  }
}
async function send() {
  if (!file.value) return;
  uploading.value = true;
  try {
    const data = new FormData();
    data.append("file", file.value);
    if (uploadName.value.trim()) data.append("name", uploadName.value.trim());
    if (notes.value.trim()) data.append("notes", notes.value.trim());
    await api("/firmware/upload", { method: "POST", body: data });
    upload.value = false;
    file.value = null;
    uploadName.value = "";
    notes.value = "";
    await list.load();
    notices.add("固件包校验通过，已加入固件仓库");
  } catch (error) {
    notices.error(error);
  } finally {
    uploading.value = false;
  }
}
watch(
  () => devices.recent[0],
  (event) => {
    if (event && /firmware\.|job\.failed/.test(event.type)) void list.load();
  },
);
watch(tab, () => {
  detail.value = null;
  upload.value = false;
  closeDeploy();
});
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
          tab === "registry"
            ? "PS 应用固件包（camera_live ELF 段）的仓库；上传后部署到设备 QSPI 非活动槽，试运行确认后生效。"
            : "每次固件下发的阶段、回执与回滚记录；失败会自动回到上一版或 golden。"
        }}
      </p>
    </div>
    <div class="heading-actions">
      <button v-if="tab === 'registry' && auth.admin" @click="upload = true">
        上传固件包
      </button>
    </div>
  </div>

  <form class="toolbar" @submit.prevent="list.filter">
    <input v-model="list.search.value" placeholder="搜索固件版本或设备…" />
    <select v-model="list.status.value">
      <option value="">全部状态</option>
      <option
        v-for="s in [
          'READY',
          'APPROVED',
          'DOWNLOADING',
          'VERIFYING',
          'VERIFIED',
          'WRITING',
          'REBOOTING',
          'SELF_TEST',
          'ACTIVE',
          'FAILED',
          'ROLLBACK',
          'ROLLED_BACK',
        ]"
        :key="s"
        :value="s"
      >
        {{ s }}
      </option>
    </select>
    <button
      :class="{ busy: list.loading.value }"
      :disabled="list.loading.value"
    >
      筛选
    </button>
    <button
      type="button"
      :class="{ busy: list.loading.value }"
      :disabled="list.loading.value"
      @click="list.load"
    >
      刷新
    </button>
    <span v-if="!auth.admin" class="note-inline"
      >上传、部署与回滚需要管理员权限</span
    >
    <span class="right inline-count">{{ list.total.value }} 条记录</span>
  </form>

  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!list.items.value.length"
    :hint="
      tab === 'registry'
        ? '还没有固件包。用 camera/build_firmware.ps1 打出 .fw 后由管理员上传。'
        : '还没有固件更新记录。在固件仓库选择版本并部署到已连接的设备。'
    "
    @retry="list.load"
  >
    <section
      v-if="tab === 'deployments'"
      class="deployment-console"
      aria-label="固件更新记录"
    >
      <article
        v-for="row in list.items.value"
        :key="row.id"
        class="deployment-entry"
      >
        <header>
          <div>
            <span class="mono">{{ row.id.slice(-10) }}</span>
            <h3>{{ deployment(row).firmware.version }}</h3>
          </div>
          <Status chip :value="row.status" />
        </header>
        <div class="deployment-route">
          <div>
            <small>目标固件</small><b>{{ deployment(row).firmware.name }}</b
            ><span class="mono">{{
              digest(deployment(row).firmware.sha256)
            }}</span>
          </div>
          <span class="deployment-arrow">→</span>
          <div>
            <small>接收设备</small><b>{{ displayName(deviceName(row)) }}</b
            ><span class="mono">{{
              deployment(row).previousVersion
                ? `回退版本 ${deployment(row).previousVersion}`
                : "无前序版本"
            }}</span>
          </div>
        </div>
        <div class="deployment-progress">
          <Status :value="row.status" />
          <div class="bar">
            <span :style="{ width: `${deployment(row).progress ?? 0}%` }" />
          </div>
          <b class="mono">{{ deployment(row).progress ?? 0 }}%</b>
        </div>
        <p v-if="deployment(row).error" class="error-box">
          {{ deployment(row).error }}
        </p>
        <footer>
          <time class="mono">{{
            new Date(row.createdAt).toLocaleString()
          }}</time>
          <div class="row-actions">
            <button class="table-action" @click="detail = row">执行证据</button>
            <template v-if="auth.admin">
              <button
                v-if="
                  deployment(row).previousVersion &&
                  ['ACTIVE', 'FAILED'].includes(row.status ?? '')
                "
                :disabled="busy"
                class="table-action danger"
                @click="rollback(row, 'PREVIOUS')"
              >
                回滚上一版
              </button>
              <button
                v-if="['ACTIVE', 'FAILED'].includes(row.status ?? '')"
                :disabled="busy"
                class="table-action danger"
                @click="rollback(row, 'GOLDEN')"
              >
                回滚 Golden
              </button>
            </template>
          </div>
        </footer>
      </article>
    </section>
    <div v-else class="panel table-wrap">
      <table>
        <thead>
          <tr>
            <SortableTh
              v-if="tab === 'registry'"
              field="name"
              label="版本 / 名称"
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <th v-else>版本 / 名称</th>
            <th>包大小</th>
            <th>摘要</th>
            <th>部署次数</th>
            <th>状态</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in list.items.value" :key="row.id">
            <td>
              <strong class="mono">{{ firmware(row).version }}</strong
              ><small>{{ firmware(row).name }}</small>
            </td>
            <td>
              <span class="mono">{{ kb(firmware(row).size) }}</span>
              <small class="muted"
                >镜像 {{ kb(firmware(row).imageSize) }} ·
                {{ firmware(row).segments.length }} 段</small
              >
            </td>
            <td class="mono">{{ digest(firmware(row).sha256) }}</td>
            <td>{{ firmware(row)._count?.deployments ?? 0 }}</td>
            <td><Status :value="row.status" /></td>
            <td>{{ new Date(row.createdAt).toLocaleString() }}</td>
            <td class="action-cell">
              <div class="row-actions">
                <button class="table-action" @click="detail = row">详情</button>
                <button
                  v-if="auth.admin"
                  class="table-action"
                  :disabled="busy || !devices.devices.length"
                  @click="openDeploy(row)"
                >
                  部署
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </AsyncState>

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

  <Drawer v-if="upload" title="上传固件包" @close="upload = false">
    <form @submit.prevent="send">
      <label>
        固件包（.fw）
        <input
          type="file"
          accept=".fw,application/octet-stream"
          required
          @change="
            file = ($event.target as HTMLInputElement).files?.[0] ?? null
          "
        />
      </label>
      <label>
        显示名称（可选）
        <input v-model="uploadName" placeholder="默认使用包内版本号" />
      </label>
      <label>
        备注（可选）
        <textarea v-model="notes" rows="3" maxlength="500"></textarea>
      </label>
      <p class="note">
        上传时校验包头 CRC、载荷 CRC、SHA-256、入口地址和 4MiB
        槽位上限；版本号来自包内。
      </p>
      <button class="primary" :disabled="uploading || !file">
        {{ uploading ? "校验中…" : "校验并入库" }}
      </button>
    </form>
  </Drawer>

  <Drawer v-if="deploying" title="部署固件" @close="closeDeploy">
    <form @submit.prevent="deploy">
      <p class="detail-head">
        <span class="mono">{{ firmware(deploying).version }}</span>
        <span>{{ kb(firmware(deploying).size) }}</span>
        <span class="mono">{{ digest(firmware(deploying).sha256) }}</span>
      </p>
      <label>
        接收设备
        <select v-model="deviceId" required>
          <option value="">选择设备</option>
          <option v-for="d in devices.devices" :key="d.id" :value="d.id">
            {{ d.name }}{{ d.firmwareVersion ? ` · ${d.firmwareVersion}` : "" }}
          </option>
        </select>
      </label>
      <div v-if="infoError" class="error-box">{{ infoError }}</div>
      <div v-else-if="info" class="fw-slots">
        <div>
          <small>当前运行</small
          ><b class="mono">{{ info.version || "未上报" }}</b
          ><span>槽 {{ slotName(info.runningSlot) }}</span>
        </div>
        <div>
          <small>槽位</small><b class="mono">A · B · Golden</b
          ><span
            >A {{ info.slotImageSize[0] ? kb(info.slotImageSize[0]) : "空" }} ·
            B
            {{ info.slotImageSize[1] ? kb(info.slotImageSize[1]) : "空" }}</span
          >
        </div>
        <div>
          <small>试运行/确认</small
          ><b class="mono"
            >pending {{ slotName(info.pendingSlot) }} · {{ info.attempts }}/{{
              info.maxAttempts
            }}</b
          ><span
            >active {{ slotName(info.activeSlot) }} · previous
            {{ slotName(info.previousSlot) }}</span
          >
        </div>
      </div>
      <p class="note">
        更新会写入非活动槽，设备重启试运行；自检通过后才标记为
        active。失败三次自动回到上一版或 golden。
      </p>
      <button class="primary" :disabled="busy || !deviceId || !!infoError">
        {{ busy ? "提交中…" : "开始更新" }}
      </button>
    </form>
  </Drawer>

  <Drawer v-if="detail" title="固件详情" wide @close="detail = null">
    <div class="fw-detail">
      <p class="detail-head">
        <span class="mono">{{ detailFirmware?.version }}</span>
        <Status :value="detail.status" />
        <time>{{ new Date(detail.createdAt).toLocaleString() }}</time>
      </p>
      <dl>
        <dt>名称</dt>
        <dd>{{ detailFirmware?.name }}</dd>
        <dt>包大小</dt>
        <dd class="mono">{{ detailFirmware?.size }} B</dd>
        <dt>镜像大小</dt>
        <dd class="mono">{{ detailFirmware?.imageSize }} B</dd>
        <dt>入口</dt>
        <dd class="mono">0x{{ detailFirmware?.entry.toString(16) ?? "—" }}</dd>
        <dt>SHA-256</dt>
        <dd class="mono break">{{ detailFirmware?.sha256 }}</dd>
        <dt>制品文件</dt>
        <dd class="mono">{{ detailFirmware?.asset?.originalName ?? "—" }}</dd>
        <dt>备注</dt>
        <dd>{{ detailFirmware?.notes ?? "—" }}</dd>
      </dl>
      <h3>段表</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>物理地址</th>
              <th>载荷偏移</th>
              <th>大小</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(segment, index) in (detailFirmware?.segments as
                | {
                    paddr: number;
                    offset: number;
                    size: number;
                  }[]
                | undefined) ?? []"
              :key="index"
            >
              <td class="mono">0x{{ segment.paddr.toString(16) }}</td>
              <td class="mono">{{ segment.offset }}</td>
              <td class="mono">{{ segment.size }} B</td>
            </tr>
          </tbody>
        </table>
      </div>
      <template v-if="'previousVersion' in detail">
        <h3>执行证据</h3>
        <dl>
          <dt>前序版本</dt>
          <dd class="mono">{{ deployment(detail).previousVersion ?? "—" }}</dd>
          <dt>前序槽位</dt>
          <dd>{{ slotName(deployment(detail).previousSlot) }}</dd>
          <dt>错误</dt>
          <dd>{{ deployment(detail).error ?? "—" }}</dd>
        </dl>
        <pre class="mono break">{{
          JSON.stringify(deployment(detail).receipt ?? {}, null, 2)
        }}</pre>
      </template>
    </div>
  </Drawer>
</template>

<style scoped>
.note-inline {
  font-size: 11px;
  color: var(--muted);
}
.fw-slots {
  display: grid;
  gap: 10px;
  margin: 14px 0;
}
.fw-slots > div {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 12px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  background: var(--surface-2);
}
.fw-slots small {
  flex-basis: 100%;
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
.fw-slots b {
  font-weight: 600;
}
.fw-slots span {
  font-size: 11px;
  color: var(--muted);
}
.fw-detail dl {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 8px 14px;
  font-size: 12px;
}
.fw-detail dt {
  color: var(--muted);
}
.fw-detail dd {
  margin: 0;
}
.break {
  overflow-wrap: anywhere;
}
</style>
