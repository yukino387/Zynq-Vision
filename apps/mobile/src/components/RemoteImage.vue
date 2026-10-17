<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { session } from "../state";

const props = defineProps<{
  assetId?: string;
  mode?: "aspectFill" | "aspectFit" | "widthFix";
  label?: string;
}>();
const source = ref(""),
  failed = ref(false),
  loading = ref(false);
/** 同一张证据在列表与详情间复用，避免重复下载。 */
const cache = new Map<string, string>();

async function load() {
  if (!props.assetId || !session.token) return;
  const hit = cache.get(props.assetId);
  if (hit) {
    source.value = hit;
    failed.value = false;
    return;
  }
  loading.value = true;
  failed.value = false;
  try {
    const result = await uni.downloadFile({
      url: `${session.server}/api/assets/${props.assetId}/content`,
      header: { authorization: `Bearer ${session.token}` },
    });
    if (result.statusCode === 200 && result.tempFilePath) {
      cache.set(props.assetId, result.tempFilePath);
      source.value = result.tempFilePath;
    } else {
      failed.value = true;
    }
  } catch {
    failed.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => props.assetId, load);
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
      <text>{{ failed ? (label ?? "图像不可用") : "图像加载中…" }}</text>
    </view>
  </view>
</template>

<style scoped>
.remote-image {
  position: relative;
  width: 100%;
  height: 100%;
  background: #dcded5;
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
  color: #6b775e;
  font-size: 10px;
  text-align: center;
  padding: 6px;
}
</style>
