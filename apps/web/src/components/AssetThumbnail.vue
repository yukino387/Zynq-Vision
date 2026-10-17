<script setup lang="ts">
import { ref, watch, onUnmounted } from "vue";
import type { Asset } from "../types";
import { blob } from "../api";
const props = defineProps<{ assets?: Asset[]; alt?: string }>();
const image = ref(""),
  failed = ref(false);
let generation = 0;
watch(
  () => props.assets?.find((a) => a.kind === "PREVIEW")?.id,
  async (id) => {
    const attempt = ++generation;
    if (image.value) URL.revokeObjectURL(image.value);
    image.value = "";
    failed.value = false;
    if (!id) return;
    try {
      const data = await blob(`/assets/${id}/content`);
      if (attempt !== generation) return;
      image.value = URL.createObjectURL(data);
    } catch {
      if (attempt === generation) failed.value = true;
    }
  },
  { immediate: true },
);
onUnmounted(() => {
  generation++;
  if (image.value) URL.revokeObjectURL(image.value);
});
</script>
<template>
  <div class="asset-thumbnail">
    <img
      v-if="image"
      :src="image"
      :alt="alt ?? '样本图像'"
      loading="lazy"
    /><span v-else>{{ failed ? "图像读取失败" : "暂无预览" }}</span>
  </div>
</template>
