<script setup lang="ts">
import { chinese, statusTone } from "@vision/shared";
import { computed, ref } from "vue";
import { queue, syncQueue, updateNote } from "../../queue";
import { session } from "../../state";
const pending = computed(
    () => queue.items.filter((i) => i.status !== "SYNCED").length,
  ),
  editing = ref(""),
  note = ref("");
function save() {
  updateNote(editing.value, note.value);
  editing.value = "";
}
</script>
<template>
  <view class="page"
    ><text class="title">{{ pending }} 个样本待同步。</text
    ><text class="subtitle">未同步的样本将在联网后继续上传。</text
    ><view class="row" style="margin-bottom: 22px"
      ><text class="status">{{
        session.online ? "● 网络可用" : "● 离线模式"
      }}</text
      ><button
        class="primary"
        :loading="queue.syncing"
        :disabled="queue.syncing || !session.token"
        @click="syncQueue(true)"
      >
        同步全部
      </button></view
    ><view v-if="!queue.items.length" class="empty">
      <text>暂无本地样本</text>
      <text class="hint">离线采样会先存在本机，联网后在这里补传。</text>
    </view
    ><view
      v-for="item in [...queue.items].reverse()"
      :key="item.id"
      class="card"
      ><view class="row"
        ><text class="status" :class="statusTone(item.status)">{{
          chinese(item.status)
        }}</text
        ><text class="mono" style="font-size: 10px">{{
          new Date(item.capturedAt).toLocaleTimeString()
        }}</text></view
      ><text class="list-caption" style="margin-top: 15px"
        >手机样本 / {{ item.id }}<br />重试次数 {{ item.attempts }} /
        {{ item.serverId ?? "等待服务器确认" }}</text
      ><text v-if="item.captureSetClientId" class="list-caption"
        >采样组 {{ item.captureSetClientId }}</text
      ><text
        v-if="item.error"
        class="error"
        style="display: block; margin-top: 12px"
        >{{ item.error }}</text
      ><text class="note">{{ item.metadata.note || "无备注" }}</text
      ><button
        v-if="item.serverId"
        @click="
          uni.navigateTo({ url: `/pages/sample/index?id=${item.serverId}` })
        "
      >
        <text v-if="item.server && item.server !== session.server" class="note"
          >该样本属于 {{ item.server }}，切回该服务器后再同步。</text
        >
        查看样本 / 审核</button
      ><button
        v-if="item.status !== 'SYNCED'"
        @click="
          editing = item.id;
          note = String(item.metadata.note ?? '');
        "
      >
        编辑备注
      </button></view
    ><view v-if="editing" class="card">
      <textarea v-model="note" placeholder="采样备注" maxlength="2000" /><button
        class="primary"
        style="margin-top: 15px"
        @click="save"
      >
        保存到本机
      </button></view
    ></view
  >
</template>
