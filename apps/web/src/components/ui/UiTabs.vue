<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";
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

interface SurfaceRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

const root = ref<HTMLDivElement | null>(null),
  buttons = ref<(HTMLButtonElement | null)[]>([]),
  current = ref<SurfaceRect | null>(null),
  previous = ref<SurfaceRect | null>(null),
  motion = ref(0),
  surfaceSize = ref({ width: 0, height: 0 });
let clearTimer: ReturnType<typeof setTimeout> | undefined;

const uid = useId(),
  gooId = `ui-tabs-goo-${uid}`,
  gradientId = `ui-tabs-gradient-${uid}`;

function setButton(el: unknown, index: number) {
  buttons.value[index] = (el as HTMLButtonElement | null) ?? null;
}

function measure() {
  if (props.variant !== "segment" || !root.value) return;
  const index = props.items.findIndex(
      (item) => normalize(item).key === props.modelValue,
    ),
    button = buttons.value[index];
  if (!button) return;
  const rootRect = root.value.getBoundingClientRect(),
    rect = button.getBoundingClientRect(),
    next: SurfaceRect = {
      left: rect.left - rootRect.left - root.value.clientLeft,
      top: rect.top - rootRect.top - root.value.clientTop,
      width: rect.width,
      height: rect.height,
    };
  surfaceSize.value = {
    width: root.value.clientWidth,
    height: root.value.clientHeight,
  };
  const changed =
    current.value !== null &&
    (Math.abs(current.value.left - next.left) > 0.5 ||
      Math.abs(current.value.top - next.top) > 0.5 ||
      Math.abs(current.value.width - next.width) > 0.5 ||
      Math.abs(current.value.height - next.height) > 0.5);
  if (current.value === null) {
    current.value = next;
    motion.value++;
  } else if (changed) {
    previous.value = current.value;
    current.value = next;
    motion.value++;
    if (clearTimer) clearTimeout(clearTimer);
    clearTimer = setTimeout(() => {
      previous.value = null;
    }, 340);
  } else {
    current.value = next;
  }
}

function scheduleMeasure() {
  void nextTick(measure);
}

function onKeydown(event: KeyboardEvent) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const entries = props.items
    .map((item, index) => ({ item: normalize(item), index }))
    .filter(({ item }) => !item.disabled);
  if (!entries.length) return;
  event.preventDefault();
  const currentIndex = entries.findIndex(
      ({ item }) => item.key === props.modelValue,
    ),
    step = event.key === "ArrowRight" ? 1 : -1,
    next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? entries.length - 1
          : currentIndex < 0
            ? 0
            : (currentIndex + step + entries.length) % entries.length,
    target = entries[next]!;
  select(target.item.key);
  void nextTick(() => buttons.value[target.index]?.focus());
}

onMounted(() => {
  scheduleMeasure();
  window.addEventListener("resize", measure);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", measure);
  if (clearTimer) clearTimeout(clearTimer);
});
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
    @keydown="onKeydown"
  >
    <svg
      v-if="variant === 'segment' && current && surfaceSize.width"
      class="ui-tab-surface"
      :viewBox="`0 0 ${surfaceSize.width} ${surfaceSize.height}`"
      aria-hidden="true"
    >
      <defs>
        <filter
          :id="gooId"
          x="-18%"
          y="-40%"
          width="136%"
          height="180%"
          color-interpolation-filters="sRGB"
        >
          <feGaussianBlur
            in="SourceGraphic"
            stdDeviation="5"
            result="blurred-field"
          />
          <feColorMatrix
            in="blurred-field"
            type="matrix"
            values="
              1 0 0 0 0
              0 1 0 0 0
              0 0 1 0 0
              0 0 0 20 -9"
          />
        </filter>
        <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
          <stop
            offset="0"
            style="stop-color: var(--lui-surface-top, var(--surface))"
          />
          <stop offset="1" style="stop-color: var(--surface)" />
        </linearGradient>
      </defs>
      <g :filter="`url(#${gooId})`">
        <rect
          v-if="previous"
          :key="`previous-${motion}`"
          class="goo-shape goo-previous"
          :x="previous.left"
          :y="previous.top"
          :width="previous.width"
          :height="previous.height"
          rx="6"
        />
        <rect
          :key="`current-${motion}`"
          class="goo-shape goo-current"
          :x="current.left"
          :y="current.top"
          :width="current.width"
          :height="current.height"
          rx="6"
        />
      </g>
      <rect
        :key="`crisp-${motion}`"
        class="goo-crisp"
        :x="current.left"
        :y="current.top"
        :width="current.width"
        :height="current.height"
        rx="6"
        :fill="`url(#${gradientId})`"
      />
    </svg>

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
      :tabindex="modelValue === normalize(raw).key ? 0 : -1"
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

/*
 * L1 表面层：旧选中矩形收缩成芽，新选中矩形从芽展开，
 * 两者进入同一个 Alpha 场（模糊 + 阈值）形成连接颈部；
 * 上层清晰矩形保证当前选中面边缘不糊。内容与命中层不受影响。
 */
.ui-tab-surface {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.goo-shape {
  fill: var(--surface);
  transform-box: fill-box;
  transform-origin: center;
}

.goo-previous {
  animation: goo-split 300ms var(--lui-ease, ease) forwards;
}

.goo-current {
  animation: goo-merge 300ms var(--lui-ease, ease) both;
}

.goo-crisp {
  stroke: var(--lui-rim, transparent);
  stroke-width: 1;
  transform-box: fill-box;
  transform-origin: center;
  animation: goo-merge 300ms var(--lui-ease, ease) both;
}

@keyframes goo-split {
  0% {
    transform: scaleX(1);
    opacity: 1;
  }
  72% {
    opacity: 1;
  }
  100% {
    transform: scaleX(0.18);
    opacity: 0;
  }
}

@keyframes goo-merge {
  0% {
    transform: scaleX(0.18);
    opacity: 0;
  }
  32% {
    opacity: 1;
  }
  100% {
    transform: scaleX(1);
    opacity: 1;
  }
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
