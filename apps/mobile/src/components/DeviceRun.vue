<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { chinese, displayName, terminalActivity } from "@vision/shared";
import { liveDevice, refreshDevices } from "../live";
import { request, session, notify, uid } from "../state";

const state = computed(() => liveDevice.value?.terminal?.state);
const online = computed(
  () =>
    session.online &&
    session.serverAvailable &&
    liveDevice.value?.connectionState === "ONLINE",
);
const activity = computed(() =>
  terminalActivity(state.value ?? null, online.value),
);
const counts = computed(() =>
  state.value?.productionRunId ? state.value.runCounts : state.value?.counts,
);
const canControl = computed(() =>
  ["ADMIN", "ENGINEER", "OPERATOR"].includes(session.user?.role ?? ""),
);
const busy = ref(""),
  pendingCheck = ref("");
watch(
  () => liveDevice.value?.id,
  (id) => {
    pendingCheck.value = id
      ? uni.getStorageSync(`vision.check.${id}`) || ""
      : "";
  },
  { immediate: true },
);
const checkBlocked = computed(() =>
  online.value && (pendingCheck.value || state.value?.pendingRequestId)
    ? ""
    : activity.value.checkBlocked,
);
async function control(
  action: "START_INSPECTION" | "STOP_INSPECTION" | "CHECK_ONE",
) {
  const id = liveDevice.value?.id;
  if (!id || busy.value || !canControl.value || !online.value) return;
  busy.value = action;
  try {
    if (action === "CHECK_ONE") {
      pendingCheck.value ||= state.value?.pendingRequestId || uid();
      uni.setStorageSync(`vision.check.${id}`, pendingCheck.value);
      await request(
        `/devices/${id}/check`,
        "POST",
        { requestId: pendingCheck.value },
        20000,
      );
      uni.removeStorageSync(`vision.check.${id}`);
      pendingCheck.value = "";
    } else {
      await request(`/devices/${id}/commands`, "POST", { type: action });
    }
    await refreshDevices();
    uni.showToast({
      title:
        action === "CHECK_ONE"
          ? "检查已保存"
          : action === "START_INSPECTION"
            ? "已开始检测"
            : "已停止检测",
      icon: "success",
    });
  } catch (error) {
    notify(error);
  } finally {
    busy.value = "";
  }
}
</script>

<template>
  <view v-if="liveDevice?.executionMode === 'LINUX_TERMINAL'" class="run-card">
    <view class="row">
      <text class="product">{{
        displayName(
          state?.product?.product || state?.product?.name || "未分配产品",
        )
      }}</text>
      <text
        class="run-status"
        :class="{ running: online && state?.production }"
        >{{ online ? (state?.production ? "检测中" : "已停止") : "离线" }}</text
      >
    </view>
    <text class="activity">{{ activity.label }}</text>
    <view v-if="counts" class="counts">
      <view
        ><text class="number">{{
          state?.productionRunId ? state.runTotal : state?.total
        }}</text
        ><text>{{ state?.productionRunId ? "本批次" : "累计" }}</text></view
      >
      <view
        ><text class="number pass">{{ counts.PASS }}</text
        ><text>合格</text></view
      >
      <view
        ><text class="number fail">{{ counts.FAIL }}</text
        ><text>不合格</text></view
      >
      <view
        ><text class="number">{{ counts.REVIEW + counts.ERROR }}</text
        ><text>待处理</text></view
      >
    </view>
    <view v-if="state?.last" class="last-result">
      <text>最近一件</text><text>{{ chinese(state.last.result) }}</text>
    </view>
    <view v-if="canControl" class="run-actions">
      <button
        :class="state?.production ? 'stop' : 'primary'"
        :loading="busy === 'START_INSPECTION' || busy === 'STOP_INSPECTION'"
        :disabled="
          !!busy || !online || (!state?.production && !!activity.startBlocked)
        "
        @click="
          control(state?.production ? 'STOP_INSPECTION' : 'START_INSPECTION')
        "
      >
        {{ state?.production ? "停止检测" : "开始检测" }}
      </button>
      <button
        :loading="busy === 'CHECK_ONE'"
        :disabled="!!busy || !!checkBlocked"
        @click="control('CHECK_ONE')"
      >
        {{
          pendingCheck || state?.pendingRequestId ? "核对上次检查" : "检查一件"
        }}
      </button>
    </view>
    <text v-if="state?.pendingSync" class="sync-note"
      >{{ state.pendingSync }} 条记录待上传</text
    >
  </view>
</template>

<style scoped>
.run-card {
  background: white;
  color: #17343e;
  border: 1px solid #e4ecef;
  border-radius: 18px;
  padding: 18px;
  margin: 16px 0;
}
.product {
  font-size: 17px;
  font-weight: 650;
}
.run-status {
  flex-shrink: 0;
  font-size: 12px;
  color: #637d87;
}
.run-status.running,
.pass {
  color: #087f82;
}
.activity {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  color: #637d87;
}
.counts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: 18px 0;
  gap: 6px;
}
.counts > view {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: #637d87;
}
.number {
  color: #17343e;
  font-size: 25px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.number.pass {
  color: #087f82;
}
.number.fail {
  color: #c74b45;
}
.last-result {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 10px 0;
  border-top: 1px solid #edf1f3;
}
.run-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
.run-actions button {
  flex: 1;
  padding: 12px 8px;
  font-size: 14px;
}
.stop {
  background: #fff0ed;
  color: #b34134;
}
.sync-note {
  display: block;
  margin-top: 12px;
  font-size: 12px;
  color: #94651f;
}
</style>
