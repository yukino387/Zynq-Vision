<script setup lang="ts">
import {
  Comment,
  Fragment,
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  useId,
  useSlots,
  watch,
} from "vue";
import type { VNode } from "vue";
import {
  SPRING_STEP,
  integrateRect,
  rectSettled,
  springSubsteps,
} from "../../lib/spring";
import Icon from "../Icon.vue";

export type UiSelectValue = string | number | boolean | null | undefined;

export interface UiSelectOption {
  label: string;
  value: UiSelectValue;
  disabled?: boolean;
}

export interface UiSelectProps {
  modelValue?: UiSelectValue;
  options?: Array<UiSelectOption | string | number>;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  size?: "sm" | "md" | "lg";
  icon?: string;
  block?: boolean;
  id?: string;
  name?: string;
  ariaLabel?: string;
  error?: string | boolean;
}

const props = withDefaults(defineProps<UiSelectProps>(), {
  modelValue: "",
  options: () => [],
  placeholder: "",
  disabled: false,
  required: false,
  size: "md",
  block: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: UiSelectValue): void;
  (e: "change", event: Event): void;
}>();

const slots = useSlots();

const triggerRef = ref<HTMLButtonElement | null>(null);
const nativeRef = ref<HTMLSelectElement | null>(null);
const menuRef = ref<HTMLElement | null>(null);
const open = ref(false);
const positioned = ref(false);
const activeIndex = ref(-1);
const uid = useId();
const listId = `ui-select-${uid}`;
const gooId = `ui-select-goo-${uid}`;
const gradientId = `ui-select-gradient-${uid}`;
const shadowId = `ui-select-shadow-${uid}`;

interface SurfaceRect {
  x: number;
  y: number;
  width: number;
  height: number;
}
interface SelectSurface {
  width: number;
  height: number;
  trigger: SurfaceRect;
}
const surface = ref<SelectSurface | null>(null);
const renderMenu = ref(false);
const closing = ref(false);
const contentLeaving = ref(false);
let closeTimer: ReturnType<typeof setTimeout> | undefined;
const motionRect = ref<SurfaceRect>({
  x: 0,
  y: 0,
  width: 0,
  height: 0,
});
const spring = { x: 0, y: 0, width: 0, height: 0, vx: 0, vy: 0, vw: 0, vh: 0 };
let springTarget: SurfaceRect = { x: 0, y: 0, width: 0, height: 0 };
let frameId: number | null = null;
let lastFrame = 0;
let settleFrames = 0;
const reducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const revealProgress = computed(() => {
  const size = surface.value;
  if (!size) return 0;
  return Math.max(
    0,
    Math.min(
      1,
      Math.min(
        motionRect.value.width / Math.max(1, size.width),
        motionRect.value.height / Math.max(1, size.height),
      ),
    ),
  );
});
const contentOpacity = computed(() =>
  contentLeaving.value
    ? 0
    : Math.max(0, Math.min(1, (revealProgress.value - 0.22) / 0.4)),
);
const contentReady = computed(() => open.value && revealProgress.value > 0.3);
const menuViewport = ref({ left: 0, top: 0 });
const anchorStyle = computed(() => {
  const size = surface.value;
  if (!size) return {};
  return {
    left: `${menuViewport.value.left + size.trigger.x}px`,
    top: `${menuViewport.value.top + size.trigger.y}px`,
    width: `${size.trigger.width}px`,
    height: `${size.trigger.height}px`,
  };
});
const contentClip = computed(() => {
  const size = surface.value;
  if (!size) return "inset(100% 0 0 0 round 8px)";
  const rect = motionRect.value,
    top = Math.max(0, rect.y),
    left = Math.max(0, rect.x),
    right = Math.max(0, size.width - (rect.x + rect.width)),
    bottom = Math.max(0, size.height - (rect.y + rect.height));
  return `inset(${top}px ${right}px ${bottom}px ${left}px round 8px)`;
});

function sameValue(a: unknown, b: unknown) {
  if (Object.is(a, b)) return true;
  if (a == null || b == null) return false;
  return String(a) === String(b);
}

function optionText(children: unknown): string {
  if (children == null) return "";
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(optionText).join("");
  if (typeof children === "object")
    return optionText((children as { children?: unknown }).children);
  return "";
}

function collectOptions(nodes: unknown, out: UiSelectOption[]) {
  const list: unknown[] = Array.isArray(nodes) ? nodes : [nodes];
  for (const node of list) {
    if (node == null || typeof node === "boolean") continue;
    if (typeof node === "string" || typeof node === "number") continue;
    if (Array.isArray(node)) {
      collectOptions(node, out);
      continue;
    }
    const vnode = node as VNode;
    if (vnode.type === Fragment) {
      collectOptions(vnode.children, out);
      continue;
    }
    if (vnode.type === Comment) continue;
    if (vnode.type === "option") {
      const attrs = (vnode.props ?? {}) as Record<string, unknown>;
      const label = optionText(vnode.children).replace(/\s+/g, " ").trim();
      out.push({
        label,
        value: ("value" in attrs ? attrs.value : label) as UiSelectValue,
        disabled: Boolean(attrs.disabled),
      });
      continue;
    }
    if (vnode.children && typeof vnode.children === "object")
      collectOptions(vnode.children, out);
  }
}

const normalizedOptions = computed<UiSelectOption[]>(() =>
  props.options.map((opt) =>
    typeof opt === "string" || typeof opt === "number"
      ? { label: String(opt), value: opt }
      : opt,
  ),
);

const slotOptions = computed<UiSelectOption[]>(() => {
  if (props.options.length) return [];
  const out: UiSelectOption[] = [];
  collectOptions(slots.default?.() ?? [], out);
  return out;
});

const allOptions = computed<UiSelectOption[]>(() =>
  props.options.length ? normalizedOptions.value : slotOptions.value,
);

const selectedOption = computed(() =>
  allOptions.value.find((opt) => sameValue(opt.value, props.modelValue)),
);

const displayLabel = computed(() => {
  if (selectedOption.value) return selectedOption.value.label;
  if (props.modelValue !== "" && props.modelValue != null)
    return String(props.modelValue);
  return props.placeholder;
});

const measureLabel = computed(() => {
  const labels = allOptions.value.map((opt) => opt.label);
  if (props.placeholder) labels.push(props.placeholder);
  return labels.reduce(
    (longest, label) => (label.length > longest.length ? label : longest),
    "",
  );
});

const nativeValue = computed(() =>
  props.modelValue == null ? "" : String(props.modelValue),
);

const hasEmptyOption = computed(() =>
  allOptions.value.some((opt) => sameValue(opt.value, "")),
);

function optionId(index: number) {
  return `${listId}-${index}`;
}

function isSelected(option: UiSelectOption) {
  return sameValue(option.value, props.modelValue);
}

function firstEnabledIndex() {
  return allOptions.value.findIndex((opt) => !opt.disabled);
}

function stopLoop() {
  if (frameId != null) cancelAnimationFrame(frameId);
  frameId = null;
}

function tick(now: number) {
  const previous = lastFrame || now - 16.67;
  lastFrame = now;
  const delta = Math.min(48, Math.max(1, now - previous)),
    steps = springSubsteps(delta);
  for (let index = 0; index < steps; index++)
    integrateRect(spring, springTarget, SPRING_STEP);
  motionRect.value = {
    x: spring.x,
    y: spring.y,
    width: spring.width,
    height: spring.height,
  };
  if (rectSettled(spring, springTarget)) {
    settleFrames++;
    if (settleFrames >= 2) {
      stopLoop();
      if (!open.value) {
        renderMenu.value = false;
        positioned.value = false;
        surface.value = null;
        closing.value = false;
        contentLeaving.value = false;
      }
      return;
    }
  } else settleFrames = 0;
  frameId = requestAnimationFrame(tick);
}

function startLoop() {
  if (frameId != null) return;
  lastFrame = 0;
  settleFrames = 0;
  frameId = requestAnimationFrame(tick);
}

function startOpen(reset: boolean) {
  const size = surface.value;
  if (!size) return;
  if (reducedMotion) {
    spring.x = 0;
    spring.y = 0;
    spring.width = size.width;
    spring.height = size.height;
    spring.vx = 0;
    spring.vy = 0;
    spring.vw = 0;
    spring.vh = 0;
    motionRect.value = { x: 0, y: 0, width: size.width, height: size.height };
    closing.value = false;
    stopLoop();
    return;
  }
  if (reset) {
    spring.x = size.trigger.x;
    spring.y = size.trigger.y;
    spring.width = size.trigger.width;
    spring.height = size.trigger.height;
    spring.vx = 0;
    spring.vy = 0;
    spring.vw = 0;
    spring.vh = 0;
    motionRect.value = { ...size.trigger };
  }
  springTarget = { x: 0, y: 0, width: size.width, height: size.height };
  closing.value = false;
  startLoop();
}

function closeMenu() {
  if (!open.value && !renderMenu.value) return;
  open.value = false;
  contentLeaving.value = true;
  if (!surface.value || reducedMotion) {
    renderMenu.value = false;
    positioned.value = false;
    surface.value = null;
    closing.value = false;
    contentLeaving.value = false;
    stopLoop();
    return;
  }
  closing.value = true;
  stopLoop();
  if (closeTimer) clearTimeout(closeTimer);
  // 内容先退出；表面在 120ms 后才沿锚点回吸。
  closeTimer = setTimeout(() => {
    if (!closing.value || !surface.value) return;
    springTarget = surface.value.trigger;
    startLoop();
  }, 120);
}

async function openMenu() {
  if (props.disabled || open.value) return;
  const wasRendered = renderMenu.value,
    hadSurface = !!surface.value;
  renderMenu.value = true;
  open.value = true;
  closing.value = false;
  contentLeaving.value = false;
  if (closeTimer) clearTimeout(closeTimer);
  if (!wasRendered) {
    surface.value = null;
    positioned.value = false;
  }
  const selected = allOptions.value.findIndex(
    (opt) => !opt.disabled && isSelected(opt),
  );
  activeIndex.value = selected >= 0 ? selected : firstEnabledIndex();
  await nextTick();
  positionMenu();
  startOpen(!wasRendered || !hadSurface);
  scrollActiveIntoView();
}

function toggle() {
  if (open.value) closeMenu();
  else void openMenu();
}

function selectOption(option: UiSelectOption) {
  if (option.disabled) return;
  if (sameValue(option.value, props.modelValue)) {
    closeMenu();
    triggerRef.value?.focus();
    return;
  }
  emit("update:modelValue", option.value);
  // 原生 select 保留在表单里，承担 required 校验，并让 @change 处理函数
  // 仍能像以前一样读取 event.target.value。
  const event = new Event("change", { bubbles: true });
  if (nativeRef.value) {
    nativeRef.value.value = option.value == null ? "" : String(option.value);
    nativeRef.value.dispatchEvent(event);
  }
  emit("change", event);
  closeMenu();
  triggerRef.value?.focus();
}

function moveActive(step: number) {
  const options = allOptions.value;
  if (!options.length) return;
  let index = activeIndex.value;
  for (let stepCount = 0; stepCount < options.length; stepCount++) {
    index = (index + step + options.length) % options.length;
    if (!options[index]!.disabled) {
      activeIndex.value = index;
      break;
    }
  }
  scrollActiveIntoView();
}

function edgeActive(fromEnd: boolean) {
  const options = allOptions.value;
  const indexes = options
    .map((_, index) => index)
    .filter((index) => !options[index]!.disabled);
  if (!indexes.length) return;
  activeIndex.value = fromEnd ? indexes[indexes.length - 1]! : indexes[0]!;
  scrollActiveIntoView();
}

function scrollActiveIntoView() {
  void nextTick(() => {
    menuRef.value
      ?.querySelector<HTMLElement>(".is-active")
      ?.scrollIntoView({ block: "nearest" });
  });
}

function setActive(index: number) {
  if (allOptions.value[index]?.disabled) return;
  activeIndex.value = index;
}

function positionMenu() {
  const trigger = triggerRef.value;
  const menu = menuRef.value;
  if (!trigger || !menu) return;
  const rect = trigger.getBoundingClientRect();
  const gap = 4;
  const margin = 8;
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  menu.style.minWidth = `${rect.width}px`;
  menu.style.maxHeight = "320px";
  menu.style.left = `${rect.left}px`;
  menu.style.top = `${rect.bottom + gap}px`;

  const measured = menu.getBoundingClientRect();
  let maxHeight = Math.min(320, viewportHeight - rect.bottom - gap - margin);
  if (
    measured.height > Math.max(160, maxHeight) &&
    rect.top - gap - margin > maxHeight
  ) {
    maxHeight = Math.min(320, rect.top - gap - margin);
    menu.style.top = `${Math.max(margin, rect.top - gap - Math.min(measured.height, maxHeight))}px`;
  }

  if (rect.left + measured.width > viewportWidth - margin) {
    menu.style.left = `${Math.max(margin, viewportWidth - margin - measured.width)}px`;
  }

  menu.style.maxHeight = `${Math.max(120, maxHeight)}px`;

  // 触发器与菜单是同一个表面实体：从触发器的完整矩形 Morph 到菜单矩形，
  // 关闭时沿同一锚点收回。没有独立的芽或连接线。
  const wasPositioned = positioned.value,
    menuRect = menu.getBoundingClientRect();
  menuViewport.value = { left: menuRect.left, top: menuRect.top };
  surface.value = {
    width: Math.round(menuRect.width),
    height: Math.round(menuRect.height),
    trigger: {
      x: rect.left - menuRect.left,
      y: rect.top - menuRect.top,
      width: rect.width,
      height: rect.height,
    },
  };
  positioned.value = true;
  if (wasPositioned && surface.value) {
    if (open.value) {
      springTarget = {
        x: 0,
        y: 0,
        width: surface.value.width,
        height: surface.value.height,
      };
      startLoop();
    } else if (closing.value) {
      springTarget = surface.value.trigger;
    }
  }
}

function onDocumentPointerDown(event: PointerEvent) {
  if (!open.value) return;
  const target = event.target as Node;
  if (triggerRef.value?.contains(target) || menuRef.value?.contains(target))
    return;
  closeMenu();
}

function onViewportChange() {
  positionMenu();
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case "ArrowDown":
      event.preventDefault();
      if (open.value) moveActive(1);
      else void openMenu();
      break;
    case "ArrowUp":
      event.preventDefault();
      if (open.value) moveActive(-1);
      else void openMenu();
      break;
    case "Home":
      if (!open.value) return;
      event.preventDefault();
      edgeActive(false);
      break;
    case "End":
      if (!open.value) return;
      event.preventDefault();
      edgeActive(true);
      break;
    case "Enter":
    case " ":
      event.preventDefault();
      if (open.value) {
        const option = allOptions.value[activeIndex.value];
        if (option) selectOption(option);
      } else {
        void openMenu();
      }
      break;
    case "Escape":
      if (!open.value) return;
      event.preventDefault();
      closeMenu();
      break;
    case "Tab":
      closeMenu();
      break;
  }
}

function onNativeFocus() {
  triggerRef.value?.focus();
}

watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) closeMenu();
  },
);

watch(open, (isOpen) => {
  if (isOpen) {
    window.addEventListener("scroll", onViewportChange, true);
    window.addEventListener("resize", onViewportChange);
  } else {
    window.removeEventListener("scroll", onViewportChange, true);
    window.removeEventListener("resize", onViewportChange);
  }
});

onMounted(() =>
  document.addEventListener("pointerdown", onDocumentPointerDown, true),
);

onBeforeUnmount(() => {
  stopLoop();
  if (closeTimer) clearTimeout(closeTimer);
  document.removeEventListener("pointerdown", onDocumentPointerDown, true);
  window.removeEventListener("scroll", onViewportChange, true);
  window.removeEventListener("resize", onViewportChange);
});
</script>

<template>
  <div
    class="ui-select"
    :class="[
      `size-${size}`,
      {
        'is-disabled': disabled,
        'has-error': Boolean(error),
        'has-icon': Boolean(icon),
        'is-block': block,
        'is-open': open,
        'is-surfaced': renderMenu && Boolean(surface),
      },
    ]"
  >
    <div class="ui-select-inner">
      <span v-if="icon" class="ui-select-prefix" aria-hidden="true">
        <Icon
          :name="icon"
          :size="size === 'sm' ? 14 : size === 'lg' ? 18 : 16"
        />
      </span>

      <button
        :id="id"
        ref="triggerRef"
        type="button"
        class="ui-select-trigger"
        :disabled="disabled"
        :aria-label="ariaLabel"
        :aria-expanded="open"
        :aria-controls="open ? listId : undefined"
        :aria-activedescendant="
          open && activeIndex >= 0 ? optionId(activeIndex) : undefined
        "
        :aria-invalid="Boolean(error) || undefined"
        aria-haspopup="listbox"
        role="combobox"
        @click="toggle"
        @keydown="onKeydown"
        @blur="closeMenu"
      >
        <span
          class="ui-select-value"
          :class="{ 'is-placeholder': !selectedOption }"
        >
          {{ displayLabel }}
        </span>
        <span class="ui-select-measure" aria-hidden="true">{{
          measureLabel
        }}</span>
      </button>

      <span
        class="ui-select-arrow"
        :class="{ 'is-open': open }"
        aria-hidden="true"
      >
        <svg
          viewBox="0 0 10 6"
          width="10"
          height="6"
          fill="none"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M1 1l4 4 4-4" />
        </svg>
      </span>
    </div>

    <span
      v-if="typeof error === 'string' && error"
      class="ui-select-error-msg"
      role="alert"
    >
      {{ error }}
    </span>

    <select
      ref="nativeRef"
      class="ui-select-native"
      :name="name"
      :value="nativeValue"
      :disabled="disabled"
      :required="required"
      tabindex="-1"
      aria-hidden="true"
      @focus="onNativeFocus"
    >
      <option v-if="placeholder && !hasEmptyOption" value="">
        {{ placeholder }}
      </option>
      <option
        v-for="(option, index) in allOptions"
        :key="index"
        :value="option.value"
        :disabled="option.disabled"
      >
        {{ option.label }}
      </option>
    </select>

    <Teleport to="body">
      <div
        v-if="renderMenu"
        :id="listId"
        ref="menuRef"
        class="ui-select-menu"
        :class="{ 'is-positioned': positioned }"
        role="listbox"
        :aria-label="ariaLabel"
        @pointerdown.prevent
      >
        <svg
          v-if="surface"
          class="ui-select-surface"
          :viewBox="`0 0 ${surface.width} ${surface.height}`"
          aria-hidden="true"
        >
          <defs>
            <filter
              :id="gooId"
              x="-20%"
              y="-40%"
              width="140%"
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
            <filter :id="shadowId" x="-20%" y="-20%" width="140%" height="170%">
              <feDropShadow
                dx="0"
                dy="8"
                stdDeviation="10"
                flood-color="#000"
                flood-opacity="0.18"
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
              class="goo-shape"
              :x="surface.trigger.x"
              :y="surface.trigger.y"
              :width="surface.trigger.width"
              :height="surface.trigger.height"
              rx="8"
            />
            <rect
              class="goo-shape"
              :x="motionRect.x"
              :y="motionRect.y"
              :width="motionRect.width"
              :height="motionRect.height"
              rx="8"
            />
          </g>
          <rect
            class="goo-crisp"
            :x="surface.trigger.x"
            :y="surface.trigger.y"
            :width="surface.trigger.width"
            :height="surface.trigger.height"
            rx="8"
            :fill="`url(#${gradientId})`"
          />
          <rect
            class="goo-crisp"
            :filter="`url(#${shadowId})`"
            :x="motionRect.x"
            :y="motionRect.y"
            :width="motionRect.width"
            :height="motionRect.height"
            rx="8"
            :fill="`url(#${gradientId})`"
          />
        </svg>
        <div
          v-if="surface"
          class="ui-select-anchor"
          :class="[`size-${size}`, { 'has-icon': Boolean(icon) }]"
          :style="anchorStyle"
          aria-hidden="true"
        >
          <span v-if="icon" class="ui-select-prefix">
            <Icon
              :name="icon"
              :size="size === 'sm' ? 14 : size === 'lg' ? 18 : 16"
            />
          </span>
          <span
            class="ui-select-anchor-value"
            :class="{ 'is-placeholder': !selectedOption }"
            >{{ displayLabel }}</span
          >
          <span class="ui-select-anchor-arrow">
            <svg
              viewBox="0 0 10 6"
              width="10"
              height="6"
              fill="none"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M1 1l4 4 4-4" />
            </svg>
          </span>
        </div>
        <div
          class="ui-select-list"
          :class="{ 'is-leaving': contentLeaving }"
          :style="{
            opacity: contentOpacity,
            transform: `translateY(${(1 - contentOpacity) * 6}px)`,
            clipPath: contentClip,
            pointerEvents: contentReady ? 'auto' : 'none',
          }"
        >
          <div
            v-for="(option, index) in allOptions"
            :id="optionId(index)"
            :key="index"
            class="ui-select-option"
            :class="{
              'is-active': index === activeIndex,
              'is-selected': isSelected(option),
              'is-disabled': option.disabled,
            }"
            role="option"
            :aria-selected="isSelected(option)"
            :aria-disabled="option.disabled || undefined"
            @pointermove="setActive(index)"
            @click="selectOption(option)"
          >
            <span class="ui-select-option-label">{{ option.label }}</span>
            <svg
              v-if="isSelected(option)"
              class="ui-select-check"
              viewBox="0 0 12 12"
              width="12"
              height="12"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M2 6.2l2.6 2.6L10 3.2" />
            </svg>
          </div>
          <div v-if="!allOptions.length" class="ui-select-empty">暂无选项</div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.ui-select {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  vertical-align: middle;
  min-width: 0;
  box-sizing: border-box;
}

.is-block {
  display: flex;
  width: 100%;
}

.ui-select-inner {
  display: inline-flex;
  align-items: center;
  position: relative;
  background: var(--surface);
  background-image: linear-gradient(
    180deg,
    var(--lui-surface-top, var(--surface)) 0%,
    var(--surface) 100%
  );
  border: 1px solid var(--line-strong);
  border-radius: var(--radius, 8px);
  box-shadow: inset 0 1px 0 var(--lui-rim, transparent);
  transition:
    border-color var(--lui-quick, 140ms) var(--lui-ease, ease),
    box-shadow var(--lui-quick, 140ms) var(--lui-ease, ease),
    background-color var(--lui-quick, 140ms) var(--lui-ease, ease);
  width: 100%;
  box-sizing: border-box;
}

.ui-select-inner:hover {
  border-color: var(--line-strong);
}

.ui-select-inner:focus-within {
  border-color: var(--forest);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--forest) 15%, transparent);
}

.ui-select-trigger {
  flex: 1;
  display: inline-grid;
  align-items: center;
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--ink);
  font-family: inherit;
  font-size: inherit;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  outline: none;
  border-radius: inherit;
  box-sizing: border-box;
}

.ui-select-trigger:hover:not(:disabled),
.ui-select-trigger:active:not(:disabled) {
  background: transparent;
  border-color: transparent;
  transform: none;
}

.ui-select-trigger:disabled {
  cursor: not-allowed;
}

.ui-select-value,
.ui-select-measure {
  grid-area: 1 / 1;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.ui-select-value.is-placeholder {
  color: var(--muted);
}

.ui-select-measure {
  visibility: hidden;
  height: 0;
  overflow: hidden;
  pointer-events: none;
}

/* 尺寸体系 */
.size-sm .ui-select-trigger {
  min-height: 30px;
  padding: 4px 26px 4px 8px;
  font-size: 12px;
}
.size-sm.has-icon .ui-select-trigger {
  padding-left: 4px;
}

.size-md .ui-select-trigger {
  min-height: 38px;
  padding: 8px 32px 8px 12px;
  font-size: 13px;
}
.size-md.has-icon .ui-select-trigger {
  padding-left: 4px;
}

.size-lg .ui-select-trigger {
  min-height: 44px;
  padding: 10px 36px 10px 14px;
  font-size: 14px;
}
.size-lg.has-icon .ui-select-trigger {
  padding-left: 6px;
}

/* 打开时触发器内容由覆盖层中的镜像保持清晰；表面本身由 SVG 触发器皮肤承担 */
.ui-select-anchor {
  position: fixed;
  z-index: 2;
  display: flex;
  align-items: center;
  border: 1px solid transparent;
  box-sizing: border-box;
  overflow: hidden;
  color: var(--ink);
  font-weight: 500;
  white-space: nowrap;
  pointer-events: none;
}

.ui-select-anchor.size-sm {
  font-size: 12px;
  padding: 4px 26px 4px 8px;
}

.ui-select-anchor.size-sm.has-icon {
  padding-left: 4px;
}

.ui-select-anchor.size-md {
  font-size: 13px;
  padding: 8px 32px 8px 12px;
}

.ui-select-anchor.size-md.has-icon {
  padding-left: 4px;
}

.ui-select-anchor.size-lg {
  font-size: 14px;
  padding: 10px 36px 10px 14px;
}

.ui-select-anchor.size-lg.has-icon {
  padding-left: 6px;
}

.ui-select-anchor-value {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ui-select-anchor-value.is-placeholder {
  color: var(--muted);
}

.ui-select-anchor-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  display: inline-flex;
  align-items: center;
  color: var(--muted);
  transform: translateY(-50%);
}

.ui-select-prefix {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  padding-left: 10px;
  pointer-events: none;
  flex-shrink: 0;
}

.ui-select-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  pointer-events: none;
  transition:
    transform 0.15s ease,
    color 0.15s ease;
}

.ui-select-arrow.is-open {
  transform: translateY(-50%) rotate(180deg);
  color: var(--forest);
}

.ui-select-inner:focus-within .ui-select-arrow {
  color: var(--forest);
}

/* 打开时触发器表面交给同一 Morph 实体，内容层淡出，避免出现两个表面 */
.ui-select.is-surfaced .ui-select-inner {
  background: transparent;
  background-image: none;
  border-color: transparent;
  box-shadow: none;
}

.ui-select.is-surfaced .ui-select-trigger:focus-visible {
  outline: none;
}

.ui-select.is-surfaced .ui-select-value,
.ui-select.is-surfaced .ui-select-arrow,
.ui-select.is-surfaced .ui-select-prefix,
.ui-select.is-surfaced .ui-select-measure {
  opacity: 0;
}

/* 禁用与错误 */
.is-disabled .ui-select-inner {
  background: var(--surface-2);
  border-color: var(--line);
  cursor: not-allowed;
  opacity: 0.65;
}

.has-error .ui-select-inner {
  border-color: var(--red);
}

.has-error .ui-select-inner:focus-within {
  border-color: var(--red);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--red) 15%, transparent);
}

.ui-select-error-msg {
  display: block;
  font-size: 12px;
  color: var(--red);
  margin-top: 4px;
}

/* 仅供表单校验与旧式 @change 读取，不参与布局 */
.ui-select-native {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  border: 0;
  opacity: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  pointer-events: none;
}

/* 弹出的选项列表 */
.ui-select-menu {
  position: fixed;
  z-index: 1200;
  display: block;
  margin: 0;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: var(--radius, 8px);
  box-sizing: border-box;
  max-width: calc(100vw - 16px);
  overflow: visible;
  opacity: 0;
  pointer-events: none;
}

/* L1 表面层：菜单主体、连接颈与触发器芽共用同一个 Alpha 场 */
.ui-select-surface {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.ui-select-list {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px;
  max-height: inherit;
  overflow-y: auto;
  overscroll-behavior: contain;
  box-sizing: border-box;
  will-change: opacity, transform;
}

.ui-select-list.is-leaving {
  opacity: 0 !important;
  transition: opacity 120ms var(--lui-ease, ease);
}

.goo-shape {
  fill: var(--surface);
}

.goo-crisp {
  stroke: var(--line-strong);
  stroke-width: 1;
}

.ui-select-menu.is-positioned {
  opacity: 1;
}

.ui-select-option {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  padding: 8px 10px;
  border-radius: 6px;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.4;
  white-space: nowrap;
  cursor: pointer;
}

.ui-select-option.is-active {
  background: var(--surface-2);
}

.ui-select-option.is-selected {
  color: var(--forest);
  font-weight: 600;
}

.ui-select-option.is-disabled {
  color: var(--muted);
  opacity: 0.55;
  cursor: not-allowed;
}

.ui-select-option-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ui-select-check {
  flex-shrink: 0;
}

.ui-select-empty {
  padding: 10px;
  color: var(--muted);
  font-size: 12px;
}
</style>
