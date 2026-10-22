<script setup lang="ts">
import { computed } from "vue";
import Icon from "../Icon.vue";

export interface UiInputProps {
  modelValue?: string | number;
  type?: "text" | "password" | "search" | "number" | "email" | "tel" | "url";
  placeholder?: string;
  disabled?: boolean;
  readonly?: boolean;
  required?: boolean;
  size?: "sm" | "md" | "lg";
  icon?: string;
  clearable?: boolean;
  error?: string | boolean;
  mono?: boolean;
  block?: boolean;
  min?: number | string;
  max?: number | string;
  step?: number | string;
  minlength?: number;
  maxlength?: number;
  autocomplete?: string;
  name?: string;
  id?: string;
  ariaLabel?: string;
}

const props = withDefaults(defineProps<UiInputProps>(), {
  modelValue: "",
  type: "text",
  placeholder: "",
  disabled: false,
  readonly: false,
  required: false,
  size: "md",
  clearable: false,
  mono: false,
  block: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: string | number): void;
  (e: "focus", event: FocusEvent): void;
  (e: "blur", event: FocusEvent): void;
  (e: "clear"): void;
  (e: "keydown", event: KeyboardEvent): void;
}>();

const hasValue = computed(() => {
  return (
    props.modelValue !== "" &&
    props.modelValue !== null &&
    props.modelValue !== undefined
  );
});

const showClear = computed(() => {
  return (
    props.clearable && !props.disabled && !props.readonly && hasValue.value
  );
});

function onInput(event: Event) {
  const target = event.target as HTMLInputElement;
  const val =
    props.type === "number"
      ? target.value === ""
        ? ""
        : Number(target.value)
      : target.value;
  emit("update:modelValue", val);
}

function onClear() {
  emit("update:modelValue", "");
  emit("clear");
}
</script>

<template>
  <div
    class="ui-input-wrap"
    :class="[
      `size-${size}`,
      {
        'is-disabled': disabled,
        'is-readonly': readonly,
        'has-error': Boolean(error),
        'is-block': block,
      },
    ]"
  >
    <div class="ui-input-inner">
      <span v-if="icon" class="ui-input-prefix" aria-hidden="true">
        <Icon
          :name="icon"
          :size="size === 'sm' ? 14 : size === 'lg' ? 18 : 16"
        />
      </span>

      <input
        :id="id"
        :name="name"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :required="required"
        :min="min"
        :max="max"
        :step="step"
        :minlength="minlength"
        :maxlength="maxlength"
        :autocomplete="autocomplete"
        :aria-label="ariaLabel"
        :aria-invalid="Boolean(error) || undefined"
        class="ui-input-native"
        :class="{ 'is-mono': mono }"
        @input="onInput"
        @focus="emit('focus', $event)"
        @blur="emit('blur', $event)"
        @keydown="emit('keydown', $event)"
      />

      <button
        v-if="showClear"
        type="button"
        class="ui-input-clear"
        aria-label="清空输入"
        tabindex="-1"
        @click.stop="onClear"
      >
        <Icon name="close" :size="12" />
      </button>

      <slot name="suffix" />
    </div>

    <span
      v-if="typeof error === 'string' && error"
      class="ui-input-error-msg"
      role="alert"
    >
      {{ error }}
    </span>
  </div>
</template>

<style scoped>
.ui-input-wrap {
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

.ui-input-inner {
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

.ui-input-inner:hover {
  border-color: var(--line-strong);
}

.ui-input-inner:focus-within {
  border-color: var(--forest);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--forest) 15%, transparent);
}

/* 尺寸体系 */
.size-sm .ui-input-inner {
  min-height: 30px;
  font-size: 12px;
}
.size-sm .ui-input-native {
  padding: 4px 8px;
}

.size-md .ui-input-inner {
  min-height: 38px;
  font-size: 13px;
}
.size-md .ui-input-native {
  padding: 8px 12px;
}

.size-lg .ui-input-inner {
  min-height: 44px;
  font-size: 14px;
}
.size-lg .ui-input-native {
  padding: 10px 14px;
}

.ui-input-native {
  flex: 1;
  width: 100%;
  min-width: 0;
  border: none;
  background: transparent;
  color: var(--ink);
  font-family: inherit;
  font-size: inherit;
  outline: none;
  box-sizing: border-box;
}

.ui-input-native::placeholder {
  color: var(--muted);
  opacity: 0.8;
}

.ui-input-native.is-mono {
  font-family: var(--mono);
}

.ui-input-prefix {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  padding-left: 10px;
  pointer-events: none;
  flex-shrink: 0;
}

.ui-input-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: var(--surface-3);
  color: var(--muted);
  border-radius: 50%;
  width: 16px;
  height: 16px;
  padding: 0;
  margin-right: 8px;
  cursor: pointer;
  flex-shrink: 0;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.ui-input-clear:hover {
  background: var(--line-strong);
  color: var(--ink);
}

/* 禁用与只读 */
.is-disabled .ui-input-inner {
  background: var(--surface-2);
  border-color: var(--line);
  cursor: not-allowed;
  opacity: 0.65;
}

.is-disabled .ui-input-native {
  cursor: not-allowed;
}

.is-readonly .ui-input-inner {
  background: var(--surface-2);
}

/* 错误态 */
.has-error .ui-input-inner {
  border-color: var(--red);
}

.has-error .ui-input-inner:focus-within {
  border-color: var(--red);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--red) 15%, transparent);
}

.ui-input-error-msg {
  display: block;
  font-size: 12px;
  color: var(--red);
  margin-top: 4px;
}
</style>
