<script setup lang="ts">
import Icon from "../Icon.vue";

export interface UiTabItem {
  key: string;
  label: string;
  count?: number | string;
  icon?: string;
  disabled?: boolean;
}

export interface UiTabsProps {
  modelValue: string;
  items: Array<UiTabItem | string>;
  variant?: "line" | "pill" | "segment";
  size?: "sm" | "md";
}

const props = withDefaults(defineProps<UiTabsProps>(), {
  variant: "line",
  size: "md",
});

const emit = defineEmits<{
  (e: "update:modelValue", key: string): void;
  (e: "change", key: string): void;
}>();

function normalize(item: UiTabItem | string): UiTabItem {
  return typeof item === "string" ? { key: item, label: item } : item;
}

function select(key: string, disabled?: boolean) {
  if (disabled) return;
  emit("update:modelValue", key);
  emit("change", key);
}
</script>

<template>
  <div
    class="ui-tabs"
    :class="[`variant-${variant}`, `size-${size}`]"
    role="tablist"
  >
    <button
      v-for="raw in items"
      :key="normalize(raw).key"
      type="button"
      role="tab"
      class="ui-tab-item"
      :class="{
        'is-active': modelValue === normalize(raw).key,
        'is-disabled': normalize(raw).disabled,
      }"
      :aria-selected="modelValue === normalize(raw).key"
      :disabled="normalize(raw).disabled"
      @click="select(normalize(raw).key, normalize(raw).disabled)"
    >
      <Icon
        v-if="normalize(raw).icon"
        :name="normalize(raw).icon!"
        :size="size === 'sm' ? 14 : 16"
        class="ui-tab-icon"
      />
      <span class="ui-tab-label">{{ normalize(raw).label }}</span>
      <span
        v-if="normalize(raw).count !== undefined"
        class="ui-tab-count"
        :class="{ 'is-active': modelValue === normalize(raw).key }"
      >
        {{ normalize(raw).count }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.ui-tabs {
  display: inline-flex;
  align-items: center;
  position: relative;
  box-sizing: border-box;
}

.ui-tab-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  color: var(--ink-2);
  font-family: inherit;
  font-weight: 550;
  cursor: pointer;
  user-select: none;
  transition:
    background-color var(--lui-quick, 140ms) var(--lui-ease, ease),
    color var(--lui-quick, 140ms) var(--lui-ease, ease),
    box-shadow var(--lui-base, 240ms) var(--lui-ease, ease),
    border-color var(--lui-quick, 140ms) var(--lui-ease, ease),
    transform var(--lui-quick, 140ms) var(--lui-ease, ease);
  position: relative;
  white-space: nowrap;
}

.ui-tab-item:active:not(.is-disabled) {
  transform: scale(var(--lui-press, 0.985));
}

.ui-tab-item:focus-visible {
  outline: 2px solid var(--forest);
  outline-offset: 2px;
}

.ui-tab-item.is-disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 尺寸 */
.size-sm .ui-tab-item {
  font-size: 12px;
  padding: 5px 10px;
}

.size-md .ui-tab-item {
  font-size: 13px;
  padding: 8px 14px;
}

/* 变体：line (下划线指示) */
.variant-line {
  border-bottom: 1px solid var(--line);
  width: 100%;
}
.variant-line .ui-tab-item {
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.variant-line .ui-tab-item:hover:not(.is-disabled) {
  color: var(--ink);
  border-bottom-color: var(--line-strong);
}
.variant-line .ui-tab-item.is-active {
  color: var(--forest);
  border-bottom-color: var(--forest);
}

/* 变体：segment (分段控制器，工业仪表常见) */
.variant-segment {
  background: var(--surface-2);
  padding: 3px;
  border-radius: var(--radius, 8px);
  border: 1px solid var(--line);
}
.variant-segment .ui-tab-item {
  border-radius: calc(var(--radius, 8px) - 2px);
  padding: 6px 12px;
}
.variant-segment .ui-tab-item:hover:not(.is-disabled):not(.is-active) {
  color: var(--ink);
  background: color-mix(in srgb, var(--surface) 50%, transparent);
}
.variant-segment .ui-tab-item.is-active {
  background: var(--surface);
  background-image: linear-gradient(
    180deg,
    var(--lui-surface-top, var(--surface)) 0%,
    var(--surface) 100%
  );
  color: var(--forest);
  box-shadow:
    inset 0 1px 0 var(--lui-rim, transparent),
    0 1px 3px rgba(0, 0, 0, 0.08);
}

/* 变体：pill */
.variant-pill {
  gap: 6px;
}
.variant-pill .ui-tab-item {
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--surface);
}
.variant-pill .ui-tab-item:hover:not(.is-disabled) {
  border-color: var(--line-strong);
}
.variant-pill .ui-tab-item.is-active {
  background: var(--forest);
  background-image: linear-gradient(
    180deg,
    color-mix(in srgb, var(--forest) 86%, #fff) 0%,
    var(--forest) 58%
  );
  border-color: var(--forest);
  color: var(--forest-ink);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

/* 数量角标 */
.ui-tab-count {
  font-size: 11px;
  font-family: var(--mono);
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--muted);
}
.ui-tab-item.is-active .ui-tab-count {
  background: color-mix(in srgb, var(--forest) 15%, transparent);
  color: var(--forest);
}
.variant-pill .ui-tab-item.is-active .ui-tab-count {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}
</style>
