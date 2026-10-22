<script setup lang="ts">
import { chinese, statusTone } from "@vision/shared";
defineProps<{
  value: string | null | undefined;
  chip?: boolean;
  label?: string;
}>();
</script>
<template>
  <span v-if="chip" class="tag" :class="statusTone(value)">{{
    label ?? chinese(value)
  }}</span>
  <span v-else class="status" :class="statusTone(value)"
    ><span class="status-dot" aria-hidden="true"></span>
    {{ label ?? chinese(value) }}</span
  >
</template>
<style scoped>
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  vertical-align: middle;
}
</style>
