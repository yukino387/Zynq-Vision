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
  background: transparent;
  background-image: none;
  border-radius: 0;
  overflow: hidden;
  box-sizing: border-box;
}

.ui-table-container.is-bordered {
  border-top: 1px solid var(--ink);
  border-left: 1px solid var(--line);
  border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  box-shadow: none;
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
  font-size: 12px;
  line-height: 1.5;
  color: var(--ink);
}

:deep(th) {
  background: transparent;
  background-image: none;
  color: var(--muted);
  font-family: var(--mono);
  font-weight: 400;
  font-size: 8.5px;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  padding: 11px 15px;
  border-bottom: 1px solid var(--line-strong);
  white-space: nowrap;
}

:deep(td) {
  padding: 13px 15px;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
  color: var(--ink-2);
}

:deep(tbody tr) {
  transition: background-color 140ms ease;
}

.is-compact :deep(th) {
  padding: 9px 13px;
}
.is-compact :deep(td) {
  padding: 10px 13px;
}

.is-hover :deep(tbody tr:hover) {
  background-color: color-mix(in srgb, var(--surface-2) 58%, transparent);
}
.is-hover :deep(tbody tr:hover td:first-child) {
  box-shadow: inset 2px 0 0 var(--forest);
}

.is-striped :deep(tbody tr:nth-child(even)) {
  background-color: color-mix(in srgb, var(--surface-2) 28%, transparent);
}

:deep(tbody tr:last-child td) {
  border-bottom: none;
}
</style>