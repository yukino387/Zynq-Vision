<script setup lang="ts">
import { computed, useId } from "vue";

export interface UiSwitchProps {
  modelValue?: boolean;
  label?: string;
  disabled?: boolean;
  pending?: boolean;
  id?: string;
  ariaLabel?: string;
}

const props = withDefaults(defineProps<UiSwitchProps>(), {
  modelValue: false,
  label: "",
  disabled: false,
  pending: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "change", value: boolean): void;
}>();

const uid = useId(),
  inputId = computed(() => props.id || `ui-switch-${uid}`);

function onChange(event: Event) {
  const value = (event.target as HTMLInputElement).checked;
  emit("update:modelValue", value);
  emit("change", value);
}
</script>

<template>
  <label
    class="ui-switch"
    :class="{ 'is-disabled': disabled, 'is-pending': pending }"
  >
    <input
      :id="inputId"
      class="ui-switch-input"
      type="checkbox"
      role="switch"
      :checked="modelValue"
      :disabled="disabled || pending"
      :aria-label="ariaLabel || label || undefined"
      :aria-checked="modelValue"
      @change="onChange"
    />
    <span class="ui-switch-track" aria-hidden="true">
      <span class="ui-switch-thumb"></span>
    </span>
    <span v-if="label || $slots.default" class="ui-switch-label">
      <slot>{{ label }}</slot>
    </span>
  </label>
</template>

<style scoped>
.ui-switch {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  user-select: none;
  vertical-align: middle;
}

.ui-switch-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.ui-switch-track {
  position: relative;
  width: 38px;
  height: 22px;
  flex: 0 0 auto;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: var(--surface-3);
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.1);
  transition:
    background-color var(--lui-base, 240ms) var(--lui-ease, ease),
    border-color var(--lui-base, 240ms) var(--lui-ease, ease);
}

.ui-switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.22);
  transition:
    transform var(--lui-base, 240ms) var(--lui-ease, ease),
    background-color var(--lui-base, 240ms) var(--lui-ease, ease);
}

.ui-switch-input:checked + .ui-switch-track {
  border-color: var(--forest);
  background: var(--forest);
  background-image: linear-gradient(
    180deg,
    color-mix(in srgb, var(--forest) 86%, #fff) 0%,
    var(--forest) 58%
  );
}

.ui-switch-input:checked + .ui-switch-track .ui-switch-thumb {
  transform: translateX(16px);
  background: var(--forest-ink);
}

.ui-switch-input:active + .ui-switch-track .ui-switch-thumb {
  transform: scaleX(1.08);
}

.ui-switch-input:checked:active + .ui-switch-track .ui-switch-thumb {
  transform: translateX(16px) scaleX(1.08);
}

.ui-switch-input:focus-visible + .ui-switch-track {
  outline: 2px solid var(--forest);
  outline-offset: 2px;
}

.ui-switch-label {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.4;
}

.is-disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.is-pending .ui-switch-thumb {
  animation: switch-pending 1.1s var(--lui-ease, ease) infinite;
}

@keyframes switch-pending {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.45;
  }
}
</style>
