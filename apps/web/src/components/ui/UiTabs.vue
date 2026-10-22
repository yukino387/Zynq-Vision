<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
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

const root = ref<HTMLDivElement | null>(null),
  buttons = ref<(HTMLButtonElement | null)[]>([]),
  indicator = ref({ left: 0, width: 0, ready: false });

function setButton(el: unknown, index: number) {
  buttons.value[index] = (el as HTMLButtonElement | null) ?? null;
}

function measure() {
  if (props.variant !== "segment" || !root.value) return;
  const index = props.items.findIndex(
      (item) => normalize(item).key === props.modelValue,
    ),
    button = buttons.value[index];
  if (!button) {
    indicator.value = { ...indicator.value, ready: false };
    return;
  }
  const rootRect = root.value.getBoundingClientRect(),
    rect = button.getBoundingClientRect();
  indicator.value = {
    left: rect.left - rootRect.left - root.value.clientLeft,
    width: rect.width,
    ready: true,
  };
}

function scheduleMeasure() {
  void nextTick(measure);
}

onMounted(() => {
  scheduleMeasure();
  window.addEventListener("resize", measure);
});
onBeforeUnmount(() => window.removeEventListener("resize", measure));
watch([() => props.modelValue, () => props.items], scheduleMeasure, {
  deep: true,
});
</script>

<template>
  <div
    ref="root"
    class="ui-tabs"
    :class="[`variant-${variant}`, `size-${size}`]"
    role="tablist"
  >
    <span
      v-if="variant === 'segment'"
      class="ui-tab-indicator"
      :class="{ 'is-ready': indicator.ready }"
      :style="{
        width: `${indicator.width}px`,
        transform: `translateX(${indicator.left}px)`,
      }"
      aria-hidden="true"
    ></span>
    <button
      v-for="(raw, index) in items"
      :key="normalize(raw).key"
      :ref="(el) => setButton(el, index)"
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
  z-index: 1;
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
  background: transparent;
  color: var(--forest);
}

.ui-tab-indicator {
  position: absolute;
  top: 3px;
  bottom: 3px;
  left: 0;
  z-index: 0;
  border-radius: calc(var(--radius, 8px) - 2px);
  background: var(--surface);
  background-image: linear-gradient(
    180deg,
    var(--lui-surface-top, var(--surface)) 0%,
    var(--surface) 100%
  );
  box-shadow:
    inset 0 1px 0 var(--lui-rim, transparent),
    0 1px 3px rgba(0, 0, 0, 0.08);
  opacity: 0;
  transition:
    transform 260ms var(--lui-ease, ease),
    width 260ms var(--lui-ease, ease),
    opacity 160ms var(--lui-ease, ease);
  pointer-events: none;
}
.ui-tab-indicator.is-ready {
  opacity: 1;
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
