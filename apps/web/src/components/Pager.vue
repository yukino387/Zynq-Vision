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
  <div v-if="pages > 1 || total > 20" class="pager" aria-label="列表分页">
    <span class="total">共 {{ total }} 条</span>
    <label class="size">
      每页
      <UiSelect
        :model-value="pageSize"
        size="sm"
        aria-label="每页条数"
        @change="onSize"
      >
        <option v-for="s in sizes" :key="s" :value="s">{{ s }}</option>
      </UiSelect>
    </label>
    <div v-if="pages > 1" class="steps">
      <button
        aria-label="上一页"
        :disabled="page <= 1"
        @click="emit('update:page', page - 1)"
      >
        上一页</button
      ><span class="pos">第 {{ page }} 页，共 {{ pages }} 页</span
      ><button
        aria-label="下一页"
        :disabled="page >= pages"
        @click="emit('update:page', page + 1)"
      >
        下一页
      </button>
    </div>
  </div>
</template>
<style scoped>
.pager,
.steps {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.steps button,
.pos {
  white-space: nowrap;
}
</style>
