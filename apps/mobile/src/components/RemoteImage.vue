<script setup lang="ts">
import { ref, watch } from "vue";
import { session } from "../state";

const props = defineProps<{
  assetId?: string;
  mode?: "aspectFill" | "aspectFit" | "widthFix";
  label?: string;
}>();
const source = ref(""),
  failed = ref(false),
  loading = ref(false);
let generation = 0;

async function load() {
  const current = ++generation;
  source.value = "";
  failed.value = false;
  loading.value = false;
  if (!props.assetId || !session.token) return;
  loading.value = true;
  failed.value = false;
  try {
    const result = await uni.downloadFile({
      url: `${session.server}/api/assets/${props.assetId}/content`,
      header: { authorization: `Bearer ${session.token}` },
    });
    if (current !== generation) return;
    if (result.statusCode === 200 && result.tempFilePath) {
      source.value = result.tempFilePath;
    } else {
      failed.value = true;
    }
  } catch {
    if (current === generation) failed.value = true;
  } finally {
    if (current === generation) loading.value = false;
  }
}

watch(() => [props.assetId, session.server, session.token], load, {
  immediate: true,
});
</script>

<template>
  <view class="remote-image">
    <image
      v-if="source"
      class="image"
      :src="source"
      :mode="mode ?? 'aspectFill'"
    />
    <view v-else class="placeholder">
      <text>{{
        loading
          ? "图像加载中…"
          : (label ?? (failed ? "图像不可用" : "暂无图像"))
      }}</text>
    </view>
  </view>
</template>

<style scoped>
.remote-image {
  position: relative;
  width: 100%;
  height: 100%;
  background: #e8f0f2;
  overflow: hidden;
}
.image {
  width: 100%;
  height: 100%;
  display: block;
}
.placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #637d87;
  font-size: 11px;
  text-align: center;
  padding: 6px;
}
</style>
