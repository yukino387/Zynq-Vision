<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  page: number;
  total: number;
  pageSize: number;
}>();
const emit = defineEmits<{
  "update:page": [number];
  "update:pageSize": [number];
}>();

const pages = computed(() =>
  Math.max(1, Math.ceil(props.total / Math.max(1, props.pageSize))),
);
const sizes = [20, 50, 100];
function onSize(event: Event) {
  emit("update:pageSize", Number((event.target as HTMLSelectElement).value));
}
</script>
<template>
  <div class="pager">
    <span class="total mono">共 {{ total }} 条</span>
    <label class="size">
      每页
      <select :value="pageSize" @change="onSize" aria-label="每页条数">
        <option v-for="s in sizes" :key="s" :value="s">{{ s }}</option>
      </select>
    </label>
    <div class="steps">
      <button
        aria-label="第一页"
        title="第一页"
        :disabled="page <= 1"
        @click="emit('update:page', 1)"
      >
        «</button
      ><button
        aria-label="上一页"
        :disabled="page <= 1"
        @click="emit('update:page', page - 1)"
      >
        ‹</button
      ><span class="mono pos">{{ page }} / {{ pages }}</span
      ><button
        aria-label="下一页"
        :disabled="page >= pages"
        @click="emit('update:page', page + 1)"
      >
        ›</button
      ><button
        aria-label="最后一页"
        title="最后一页"
        :disabled="page >= pages"
        @click="emit('update:page', pages)"
      >
        »
      </button>
    </div>
  </div>
</template>
