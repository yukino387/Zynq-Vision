<script setup lang="ts">
withDefaults(
  defineProps<{
    loading?: boolean;
    error?: string;
    empty?: boolean;
    /** 骨架屏行数；接近一屏可见的行数即可 */
    rows?: number;
    /** 空态下说明"为什么空、下一步做什么"，只写「暂无记录」等于没说 */
    hint?: string;
  }>(),
  { rows: 6 },
);
defineEmits<{ retry: [] }>();
</script>
<template>
  <div v-if="loading" class="skeleton" role="status" aria-label="正在读取">
    <span v-for="i in rows" :key="i"></span>
  </div>
  <div v-else-if="error" class="error-box" role="alert">
    {{ error }} <button @click="$emit('retry')">重试</button>
  </div>
  <div v-else-if="empty" class="empty">
    <b>暂无记录</b>
    <p v-if="hint" class="muted">{{ hint }}</p>
  </div>
  <slot v-else />
</template>
