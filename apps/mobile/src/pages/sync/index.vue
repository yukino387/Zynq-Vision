<script setup lang="ts">
import { chinese, statusTone } from "@vision/shared";
import { computed, ref } from "vue";
import { queue, syncQueue, updateNote } from "../../queue";
import { session } from "../../state";
const pending = computed(
    () => queue.items.filter((i) => i.status !== "SYNCED").length,
  ),
  failed = computed(
    () => queue.items.filter((i) => i.status === "FAILED").length,
  ),
  editing = ref(""),
  note = ref("");
function save() {
  updateNote(editing.value, note.value);
  editing.value = "";
}
</script>

<template>
  <view class="page">
    <view class="head-row">
      <view>
        <text class="eyebrow">离线优先 / QUEUE</text>
        <text class="title">同步队列</text>
      </view>
      <text class="mono total">{{ queue.items.length }}</text>
    </view>
    <text class="subtitle"
      >手机原图先保存在本机；网络恢复后在这里补传，不会丢失。</text
    >

    <view class="status-card">
      <view class="status-copy">
        <text class="status" :class="session.online ? 'ok' : 'warn'"
          >● {{ session.online ? "网络可用" : "离线模式" }}</text
        >
        <text class="status-note"
          >{{ pending }} 个待同步 · {{ failed }} 个失败 · 可安全退出</text
        >
      </view>
      <button
        class="primary sync-button"
        :loading="queue.syncing"
        :disabled="queue.syncing || !session.token || !pending"
        @click="syncQueue(true)"
      >
        {{ queue.syncing ? "同步中…" : "同步全部" }}
      </button>
    </view>

    <view v-if="!queue.items.length" class="empty">
      <text>暂无本地样本</text>
      <text class="hint">离线采样会先存在本机，联网后在这里补传。</text>
    </view>

    <view
      v-for="item in [...queue.items].reverse()"
      :key="item.id"
      class="card queue-item"
    >
      <view class="row">
        <text class="status" :class="statusTone(item.status)">{{
          chinese(item.status)
        }}</text>
        <text class="mono time">{{
          new Date(item.capturedAt).toLocaleTimeString()
        }}</text>
      </view>
      <view class="item-meta">
        <text class="mono">手机样本 / {{ item.id.slice(-8) }}</text>
        <text class="mono">重试 {{ item.attempts }}</text>
      </view>
      <text class="list-caption"
        >{{ item.serverId ? `服务器记录 ${item.serverId.slice(-8)}` : "等待服务器确认" }}<text
          v-if="item.captureSetClientId"
        >
          · 采样组 {{ item.captureSetClientId.slice(-6) }}</text
        ></text
      >
      <text v-if="item.error" class="error inline">{{ item.error }}</text>
      <text class="note">{{ item.metadata.note || "无备注" }}</text>
      <view class="item-actions">
        <button
          v-if="item.serverId"
          @click="
            uni.navigateTo({ url: `/pages/sample/index?id=${item.serverId}` })
          "
        >
          查看样本
        </button>
        <button
          v-if="item.status !== 'SYNCED'"
          @click="
            editing = item.id;
            note = String(item.metadata.note ?? '');
          "
        >
          编辑备注
        </button>
      </view>
      <text
        v-if="item.server && item.server !== session.server"
        class="list-caption server-note"
        >该样本属于 {{ item.server }}，切回该服务器后再同步。</text
      >
    </view>

    <view v-if="editing" class="card">
      <textarea v-model="note" placeholder="采样备注" maxlength="2000" />
      <button class="primary" style="margin-top: 15px" @click="save">
        保存到本机
      </button>
    </view>
  </view>
</template>

<style scoped>
.head-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}
.head-row .title {
  margin-bottom: 0;
}
.total {
  font-size: 26px;
  color: #4d5b3f;
  line-height: 1;
  padding-bottom: 4px;
}
.status-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #f7f6ee;
  border-top: 1px solid #b7bda9;
  border-bottom: 1px solid #b7bda9;
  padding: 14px;
  margin-bottom: 14px;
}
.status-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.status-copy .status {
  font-size: 12px;
}
.status-copy .status.ok {
  color: #3d6b4b;
}
.status-copy .status.warn {
  color: #8f5f00;
}
.status-note {
  font-size: 10px;
  color: #6b775e;
}
.sync-button {
  min-width: 96px;
  min-height: 42px;
  font-size: 12px;
  border-radius: 2px;
  white-space: nowrap;
}
.queue-item {
  padding: 14px;
}
.time {
  font-size: 10px;
  color: #6b775e;
}
.item-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 7px;
  font-size: 10px;
  color: #6b775e;
}
.queue-item .note {
  margin: 6px 0 0;
}
.item-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.item-actions button {
  flex: 1;
  min-height: 38px;
  font-size: 11px;
}
.error.inline {
  display: block;
  margin-top: 8px;
}
.server-note {
  display: block;
  margin-top: 6px;
  color: #8f5f00;
}
</style>
