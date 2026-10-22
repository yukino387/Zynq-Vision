<script setup lang="ts">
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";
import Icon from "../Icon.vue";

export interface UiButtonProps {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger" | "text";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  disabled?: boolean;
  icon?: string;
  iconPosition?: "left" | "right";
  type?: "button" | "submit" | "reset";
  to?: RouteLocationRaw;
  chip?: boolean;
  block?: boolean;
}

const props = withDefaults(defineProps<UiButtonProps>(), {
  variant: "secondary",
  size: "md",
  loading: false,
  disabled: false,
  iconPosition: "left",
  type: "button",
  chip: false,
  block: false,
});

const isDisabled = computed(() => props.disabled || props.loading);
const isLink = computed(() => !!props.to && !isDisabled.value);
</script>

<template>
  <RouterLink
    v-if="isLink"
    :to="to!"
    class="ui-button"
    :class="[
      `variant-${variant}`,
      `size-${size}`,
      {
        'is-chip': chip,
        'is-block': block,
        'is-loading': loading,
      },
    ]"
    :aria-busy="loading || undefined"
  >
    <Icon
      v-if="icon && iconPosition === 'left' && !loading"
      :name="icon"
      :size="size === 'sm' ? 14 : size === 'lg' ? 18 : 16"
      class="button-icon left"
    />
    <span v-if="loading" class="spinner" aria-hidden="true"></span>
    <span class="button-label"><slot /></span>
    <Icon
      v-if="icon && iconPosition === 'right' && !loading"
      :name="icon"
      :size="size === 'sm' ? 14 : size === 'lg' ? 18 : 16"
      class="button-icon right"
    />
  </RouterLink>

  <button
    v-else
    :type="type"
    class="ui-button"
    :class="[
      `variant-${variant}`,
      `size-${size}`,
      {
        'is-chip': chip,
        'is-block': block,
        'is-loading': loading,
      },
    ]"
    :disabled="isDisabled"
    :aria-busy="loading || undefined"
    :aria-disabled="isDisabled || undefined"
  >
    <Icon
      v-if="icon && iconPosition === 'left' && !loading"
      :name="icon"
      :size="size === 'sm' ? 14 : size === 'lg' ? 18 : 16"
      class="button-icon left"
    />
    <span v-if="loading" class="spinner" aria-hidden="true"></span>
    <span class="button-label"><slot /></span>
    <Icon
      v-if="icon && iconPosition === 'right' && !loading"
      :name="icon"
      :size="size === 'sm' ? 14 : size === 'lg' ? 18 : 16"
      class="button-icon right"
    />
  </button>
</template>

<style scoped>
.ui-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  gap: 7px;
  font-family: inherit;
  font-weight: 550;
  text-decoration: none;
  white-space: nowrap;
  vertical-align: middle;
  border-radius: var(--radius, 8px);
  border: 1px solid transparent;
  cursor: pointer;
  user-select: none;
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.08s ease;
  min-width: 0;
  box-sizing: border-box;
}

.ui-button:focus-visible {
  outline: 2px solid var(--forest);
  outline-offset: 2px;
}

.ui-button:active:not(:disabled) {
  transform: translateY(1px);
}

/* 尺寸体系 */
.size-sm {
  font-size: 12px;
  line-height: 1.3;
  padding: 5px 10px;
  min-height: 30px;
}

.size-md {
  font-size: 13px;
  line-height: 1.4;
  padding: 8px 14px;
  min-height: 38px;
}

.size-lg {
  font-size: 14px;
  line-height: 1.45;
  padding: 10px 20px;
  min-height: 44px;
}

.is-chip {
  border-radius: 999px;
  padding-left: 12px;
  padding-right: 12px;
}

.is-block {
  display: flex;
  width: 100%;
}

/* 变体体系 */
.variant-primary {
  background: var(--forest);
  border-color: var(--forest);
  color: var(--forest-ink);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
.variant-primary:hover:not(:disabled) {
  background: var(--forest-hover);
  border-color: var(--forest-hover);
  color: var(--forest-ink);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}
.variant-primary:active:not(:disabled) {
  background: var(--forest);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.variant-secondary {
  background: var(--surface);
  border-color: var(--line);
  color: var(--ink);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.variant-secondary:hover:not(:disabled) {
  background: var(--surface-2);
  border-color: var(--line-strong);
}
.variant-secondary:active:not(:disabled) {
  background: var(--surface-3);
}

.variant-outline {
  background: transparent;
  border-color: var(--line-strong);
  color: var(--ink);
}
.variant-outline:hover:not(:disabled) {
  background: var(--surface-2);
  border-color: var(--forest);
  color: var(--forest);
}

.variant-ghost {
  background: transparent;
  border-color: transparent;
  color: var(--ink-2);
}
.variant-ghost:hover:not(:disabled) {
  background: var(--surface-2);
  color: var(--ink);
}

.variant-text {
  background: transparent;
  border-color: transparent;
  color: var(--forest);
  padding-left: 6px;
  padding-right: 6px;
  min-height: auto;
}
.variant-text:hover:not(:disabled) {
  color: var(--forest-hover);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.variant-danger {
  background: var(--crit-bg, #f5e0da);
  border-color: var(--crit-line, #d9a097);
  color: var(--red, #b6372a);
}
.variant-danger:hover:not(:disabled) {
  background: var(--red, #b6372a);
  border-color: var(--red, #b6372a);
  color: #ffffff;
}

/* 禁用态与加载态 */
.ui-button:disabled,
.ui-button.is-loading {
  opacity: 0.55;
  cursor: not-allowed;
  pointer-events: none;
  box-shadow: none;
  transform: none;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: ui-spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes ui-spin {
  to {
    transform: rotate(360deg);
  }
}

.button-icon {
  flex-shrink: 0;
}

.button-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>
