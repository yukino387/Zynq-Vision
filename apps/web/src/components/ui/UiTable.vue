<script setup lang="ts">
export interface UiTableProps {
  compact?: boolean;
  bordered?: boolean;
  striped?: boolean;
  hover?: boolean;
}

withDefaults(defineProps<UiTableProps>(), {
  compact: false,
  bordered: true,
  striped: false,
  hover: true,
});
</script>

<template>
  <div
    class="ui-table-container"
    :class="{
      'is-bordered': bordered,
      'is-compact': compact,
      'is-striped': striped,
      'is-hover': hover,
    }"
  >
    <div class="ui-table-scroll">
      <table class="ui-table">
        <slot />
      </table>
    </div>
  </div>
</template>

<style scoped>
.ui-table-container {
  position: relative;
  background: var(--surface);
  border-radius: var(--radius, 8px);
  overflow: hidden;
  box-sizing: border-box;
}

.ui-table-container.is-bordered {
  border: 1px solid var(--line);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

.ui-table-scroll {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.ui-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink);
}

:deep(th) {
  background: var(--surface-2);
  color: var(--ink-2);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line-strong);
  white-space: nowrap;
}

:deep(td) {
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
}

.is-compact :deep(th) {
  padding: 6px 10px;
}
.is-compact :deep(td) {
  padding: 7px 10px;
}

.is-hover :deep(tbody tr:hover) {
  background-color: color-mix(in srgb, var(--surface-2) 60%, transparent);
}

.is-striped :deep(tbody tr:nth-child(even)) {
  background-color: color-mix(in srgb, var(--surface-2) 35%, transparent);
}

:deep(tbody tr:last-child td) {
  border-bottom: none;
}
</style>
