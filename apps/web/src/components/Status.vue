<script setup lang="ts">
import { chinese, statusTone } from "@vision/shared";
defineProps<{ value: string | null | undefined; chip?: boolean }>();
</script>
<template>
  <span v-if="chip" class="tag" :class="statusTone(value)">{{
    chinese(value)
  }}</span>
  <span v-else class="status" :class="statusTone(value)"
    ><span aria-hidden="true">●</span> {{ chinese(value) }}</span
  >
</template>
