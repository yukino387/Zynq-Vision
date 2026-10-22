<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import type { Named } from "../types";
import { useDeviceStore } from "../stores/devices";
import { useList } from "../composables/useList";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import Pager from "../components/Pager.vue";
import Drawer from "../components/Drawer.vue";
const route = useRoute(),
  devices = useDeviceStore();
const tab = computed(() =>
  String(route.params.tab || route.meta.defaultTab || "overview"),
);
const endpoint = computed(() =>
  tab.value === "deployments" ? "/firmware-deployments" : "/firmware",
);
const list = useList<Named>(endpoint),
  detail = ref<Named | null>(null);
watch(tab, () => {
  detail.value = null;
});
const state = computed(() => devices.current?.terminal?.state);
const file = (row: Named) =>
  row as Named & {
    version: string;
    size: number;
    imageSize: number;
    sha256: string;
    notes?: string | null;
    asset?: { originalName: string };
    segments?: unknown[];
  };
const release = (row: Named) =>
  row as Named & {
    firmware: ReturnType<typeof file>;
    device?: { name: string };
    deviceId: string;
    progress: number;
    error?: string | null;
    receipt?: unknown;
    previousVersion?: string | null;
  };
const currentFile = computed(() =>
  !detail.value
    ? null
    : tab.value === "deployments"
      ? release(detail.value).firmware
      : file(detail.value),
);
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>
        {{
          route.meta.tabs?.find((t) => t.tab === tab)?.label || route.meta.title
        }}
      </h1>
      <p>
        {{
          tab === "overview"
            ? "查看当前 Linux 终端的运行方式与更新能力。"
            : "旧裸机系统的固件与发布证据，仅供查询。"
        }}
      </p>
    </div>
  </div>
  <section
    v-if="tab === 'overview'"
    class="panel update-overview"
    aria-label="终端更新能力"
  >
    <div class="toolbar">
      <strong>Linux 独立检测终端</strong
      ><span class="tag">应用 OTA 尚未接入</span>
    </div>
    <p>
      作业和配套模型通过平台在线领取；界面、检测服务和系统镜像尚不支持网页升级。
    </p>
    <label
      >检测终端<UiSelect v-model="devices.selected">
        <option v-if="!devices.devices.length" value="">暂无设备</option>
        <option
          v-for="device in devices.devices"
          :key="device.id"
          :value="device.id"
        >
          {{ device.name }}
        </option>
      </UiSelect></label
    >
    <p v-if="devices.current">
      <Status :value="devices.current.connectionState" /> ·
      {{
        devices.current.executionMode === "LINUX_TERMINAL"
          ? "状态来自板端心跳"
          : "模拟设备"
      }}
    </p>
    <p v-if="state">
      当前模型：{{ state.model?.version || "未下发" }} · 当前产品：{{
        state.product?.name || "未分配"
      }}
      · 待上传 {{ state.pendingSync }}
    </p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>更新内容</th>
            <th>当前能力</th>
            <th>操作位置</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>作业与配套模型</td>
            <td>支持在线领取、校验并启用</td>
            <td>平台创建批次，板端“平台”页领取</td>
          </tr>
          <tr>
            <td>界面、检测与管理程序</td>
            <td>网页 OTA 未接入</td>
            <td>由维护人员更新板端程序</td>
          </tr>
          <tr>
            <td>Linux 内核、系统镜像、FPGA 配置</td>
            <td>网页 OTA 未接入</td>
            <td>由维护人员更新匹配的系统镜像</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="toolbar">
      <RouterLink to="/production" class="text-button">进入检测作业</RouterLink
      ><RouterLink to="/diagnostics/registry" class="text-button"
        >查看终端状态</RouterLink
      >
    </div>
    <p class="note">
      旧固件档案中的 A/B 槽位和 Golden 回滚属于裸机应用，不适用于当前 Linux
      系统。
    </p>
  </section>
  <template v-else>
    <p class="note archive-note">
      此页仅保留历史资料，已移除固件上传、部署及回滚入口。历史“已生效”表示当时的裸机发布结果，不代表当前
      Linux 版本。
    </p>
    <form class="toolbar" @submit.prevent="list.filter">
      <input
        v-model="list.search.value"
        placeholder="搜索旧固件或发布记录"
        aria-label="搜索旧固件"
      /><button :disabled="list.loading.value">筛选</button
      ><button type="button" :disabled="list.loading.value" @click="list.load">
        刷新</button
      ><span class="right">{{ list.total.value }} 条档案</span>
    </form>
    <AsyncState
      :loading="list.loading.value"
      :error="list.error.value"
      :empty="!list.items.value.length"
      hint="暂无旧裸机固件档案。当前 Linux 终端请使用检测作业流程。"
      @retry="list.load"
    >
      <div class="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>版本</th>
              <th>{{ tab === "deployments" ? "设备" : "名称" }}</th>
              <th>{{ tab === "deployments" ? "历史状态" : "大小" }}</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in list.items.value" :key="row.id">
              <td>
                {{
                  tab === "deployments"
                    ? release(row).firmware.version
                    : file(row).version
                }}
              </td>
              <td>
                {{
                  tab === "deployments"
                    ? release(row).device?.name || release(row).deviceId
                    : row.name
                }}
              </td>
              <td>
                <Status v-if="tab === 'deployments'" :value="row.status" /><span
                  v-else
                  >{{ (file(row).size / 1024).toFixed(1) }} KiB</span
                >
              </td>
              <td>{{ new Date(row.createdAt).toLocaleString() }}</td>
              <td>
                <button class="table-action" @click="detail = row">
                  查看档案
                </button>
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
  </template>
  <Drawer v-if="detail" title="旧裸机固件档案" wide @close="detail = null">
    <p>此档案仅记录旧系统制品与当时的发布结果。</p>
    <dl>
      <dt>版本</dt>
      <dd>{{ currentFile?.version }}</dd>
      <dt>名称</dt>
      <dd>{{ currentFile?.name }}</dd>
      <dt>大小</dt>
      <dd>{{ currentFile?.size }} B</dd>
      <dt>SHA-256</dt>
      <dd class="mono">{{ currentFile?.sha256 }}</dd>
      <dt>文件</dt>
      <dd>{{ currentFile?.asset?.originalName || "尚未选择文件" }}</dd>
      <dt>备注</dt>
      <dd>{{ currentFile?.notes || "未填写说明" }}</dd>
    </dl>
    <template v-if="tab === 'deployments'"
      ><h3>历史执行证据</h3>
      <p>{{ release(detail).error || "无历史错误信息" }}</p>
      <pre>{{ JSON.stringify(release(detail).receipt || {}, null, 2) }}</pre>
    </template>
  </Drawer>
</template>
<style scoped>
.update-overview {
  padding: 1rem;
}
.update-overview p {
  margin: 1rem 0;
}
.update-overview label {
  display: grid;
  gap: 0.5rem;
  max-width: 32rem;
  margin: 1rem 0;
}
.archive-note {
  padding: 1rem;
}
dl {
  display: grid;
  grid-template-columns: 6rem minmax(0, 1fr);
  gap: 0.8rem;
}
dd {
  margin: 0;
  overflow-wrap: anywhere;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
