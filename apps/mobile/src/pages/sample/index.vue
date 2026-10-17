<script setup lang="ts">
import { chinese, displayName } from "@vision/shared";
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { request, session, notify } from "../../state";
interface Sample {
  id: string;
  name: string;
  source: string;
  status: string;
  hard: boolean;
  assets: { id: string; kind: string }[];
  metadata: unknown;
  quality: { status: string } | null;
}
const sample = ref<Sample | null>(null),
  image = ref(""),
  error = ref(""),
  verdict = ref("ACCEPT"),
  note = ref(""),
  hard = ref(false),
  busy = ref(false);
onLoad(async (options) => {
  try {
    sample.value = await request(`/samples/${String(options?.id ?? "")}`);
    hard.value = sample.value!.hard;
    const asset = sample.value!.assets.find((a) => a.kind === "PREVIEW");
    if (asset) {
      const result = await uni.downloadFile({
        url: `${session.server}/api/assets/${asset.id}/content`,
        header: { authorization: `Bearer ${session.token}` },
      });
      if (result.statusCode === 200) image.value = result.tempFilePath;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});
function setHard(e: unknown) {
  hard.value = (e as { detail: { value: boolean } }).detail.value;
}
async function review() {
  if (!sample.value) return;
  busy.value = true;
  try {
    await request(`/samples/${sample.value.id}/review`, "POST", {
      verdict: verdict.value,
      note: note.value,
      hard: hard.value,
    });
    sample.value = await request(`/samples/${sample.value.id}`);
    uni.showToast({ title: "审核已保存", icon: "success" });
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <view class="page"
    ><view v-if="error" class="error">{{ error }}</view
    ><template v-if="sample"
      ><text class="eyebrow">样本来源： {{ chinese(sample.source) }}</text
      ><text class="title">样本与审核</text
      ><text class="subtitle">{{ displayName(sample.name) }}</text
      ><image v-if="image" :src="image" mode="widthFix" class="image" /><view
        class="card"
        style="margin-top: 20px"
        ><view class="row"
          ><text>审核状态</text
          ><text class="status">{{ chinese(sample.status) }}</text></view
        ><text class="note"
          >质量提示：{{ chinese(sample.quality?.status ?? "不可用") }}</text
        ></view
      ><view class="review-options"
        ><text
          v-for="v in [
            { key: 'ACCEPT', label: '接纳' },
            { key: 'REJECT', label: '拒绝' },
            { key: 'NEEDS_WORK', label: '待补充' },
          ]"
          :key="v.key"
          :class="{ selected: verdict === v.key }"
          @click="verdict = v.key"
          >{{ v.label }}</text
        ></view
      ><view class="field row"
        ><text>困难样本</text
        ><switch :checked="hard" color="#1f4d3a" @change="setHard" /></view
      ><textarea
        v-model="note"
        placeholder="采样审核备注"
        maxlength="2000"
      /><button
        class="primary"
        style="margin-top: 18px"
        @click="review"
        :disabled="busy"
        :loading="busy"
      >
        保存样本审核
      </button></template
    ><view v-else-if="!error" class="empty">读取样本…</view></view
  >
</template>
