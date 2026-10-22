<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

interface Item {
  label: string;
  count: number;
}

const props = withDefaults(
  defineProps<{
    items: Item[];
    unit?: string;
    emptyText?: string;
  }>(),
  { unit: "", emptyText: "暂无数据" },
);

const max = computed(() =>
  Math.max(1, ...props.items.map((item) => item.count)),
);
const shown = ref(false);
onMounted(() => requestAnimationFrame(() => (shown.value = true)));
</script>

<template>
  <div v-if="items.length" class="rank">
    <div
      v-for="item in items"
      :key="item.label"
      class="rank-row"
      :title="`${item.label} ${item.count}${unit}`"
    >
      <span class="rank-label">{{ item.label }}</span>
      <span class="rank-track" aria-hidden="true">
        <i
          :style="{ width: shown ? `${(item.count / max) * 100}%` : '0%' }"
        ></i>
      </span>
      <span class="rank-value mono">{{ item.count }}{{ unit }}</span>
    </div>
  </div>
  <p v-else class="rank-empty">{{ emptyText }}</p>
</template>

<style scoped>
.rank {
  display: grid;
  gap: 9px;
}
.rank-row {
  display: grid;
  grid-template-columns: minmax(64px, 120px) 1fr auto;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}
.rank-label {
  overflow: hidden;
  color: var(--ink-2);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rank-track {
  display: block;
  height: 7px;
  overflow: hidden;
  border-radius: 4px;
  background: var(--surface-2);
}
.rank-track i {
  display: block;
  height: 100%;
  border-radius: 0 4px 4px 0;
  background: var(--forest);
  transition: width 420ms var(--lui-ease, ease);
}
.rank-value {
  min-width: 36px;
  color: var(--ink-2);
  text-align: right;
}
.rank-empty {
  display: grid;
  place-items: center;
  min-height: 120px;
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
</style>
