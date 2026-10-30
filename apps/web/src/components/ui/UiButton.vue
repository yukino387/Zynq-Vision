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
  font-family: var(--font);
  font-weight: 500;
  letter-spacing: 0.03em;
  text-decoration: none;
  white-space: nowrap;
  vertical-align: middle;
  border-radius: 2px;
  border: 1px solid transparent;
  cursor: pointer;
  user-select: none;
  min-width: 0;
  box-sizing: border-box;
  transition:
    background-color 140ms ease,
    border-color 140ms ease,
    color 140ms ease;
}

.ui-button:focus-visible {
  outline: 1px solid var(--forest);
  outline-offset: 3px;
}

.ui-button:active:not(:disabled) {
  transform: none;
}

.size-sm {
  font-size: 10px;
  line-height: 1.3;
  padding: 5px 9px;
  min-height: 28px;
}

.size-md {
  font-size: 11.5px;
  line-height: 1.4;
  padding: 7px 13px;
  min-height: 34px;
}

.size-lg {
  font-size: 12.5px;
  line-height: 1.45;
  padding: 9px 18px;
  min-height: 42px;
}

.is-chip {
  border-radius: 2px;
  padding-left: 10px;
  padding-right: 10px;
}

.is-block {
  display: flex;
  width: 100%;
}

.variant-primary {
  background: var(--forest);
  border-color: var(--forest);
  color: var(--forest-ink);
}
.variant-primary:hover:not(:disabled) {
  background: var(--forest-hover);
  border-color: var(--forest-hover);
  color: var(--forest-ink);
}
.variant-primary:active:not(:disabled) {
  background: var(--forest);
  filter: brightness(0.94);
}

.variant-secondary {
  background: transparent;
  border-color: var(--line-strong);
  color: var(--ink);
}
.variant-secondary:hover:not(:disabled) {
  background: var(--surface-2);
  border-color: var(--ink);
}
.variant-secondary:active:not(:disabled) {
  background: var(--surface-3);
}

.variant-outline {
  background: transparent;
  border-color: var(--line);
  color: var(--ink-2);
}
.variant-outline:hover:not(:disabled) {
  background: var(--surface-2);
  border-color: var(--line-strong);
  color: var(--ink);
}

.variant-ghost {
  background: transparent;
  border-color: transparent;
  color: var(--muted);
}
.variant-ghost:hover:not(:disabled) {
  background: var(--surface-2);
  color: var(--ink);
}

.variant-text {
  background: transparent;
  border-color: transparent;
  color: var(--forest);
  padding-left: 3px;
  padding-right: 3px;
  min-height: auto;
}
.variant-text:hover:not(:disabled) {
  background: transparent;
  color: var(--forest-hover);
  text-decoration: underline;
  text-underline-offset: 4px;
}

.variant-danger {
  background: transparent;
  border-color: transparent;
  color: var(--red);
}
.variant-danger:hover:not(:disabled) {
  background: var(--crit-bg);
  border-color: var(--crit-line);
  color: var(--red);
}

.ui-button:disabled,
.ui-button.is-loading {
  opacity: 0.45;
  cursor: not-allowed;
  pointer-events: none;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 1.5px solid currentColor;
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
  opacity: 0.85;
}

.button-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>