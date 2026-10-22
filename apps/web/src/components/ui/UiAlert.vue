<script setup lang="ts">
import { computed } from "vue";
import Icon from "../Icon.vue";

export interface UiAlertProps {
  tone?: "info" | "success" | "warn" | "crit";
  title?: string;
  icon?: string;
  closable?: boolean;
}

const props = withDefaults(defineProps<UiAlertProps>(), {
  tone: "info",
  title: "",
  closable: false,
});

defineEmits<{ (e: "close"): void }>();

const iconName = computed(
  () =>
    props.icon ??
    ({ info: "activity", success: "check", warn: "alert", crit: "alert" }[
      props.tone
    ] as string),
);
</script>

<template>
  <div class="ui-alert" :class="`tone-${tone}`" role="alert">
    <span class="ui-alert-icon" aria-hidden="true">
      <Icon :name="iconName" :size="16" />
    </span>
    <div class="ui-alert-content">
      <strong v-if="title" class="ui-alert-title">{{ title }}</strong>
      <div class="ui-alert-message"><slot /></div>
    </div>
    <button
      v-if="closable"
      type="button"
      class="ui-alert-close"
      aria-label="关闭提示"
      @click="$emit('close')"
    >
      <Icon name="close" :size="14" />
    </button>
  </div>
</template>

<style scoped>
.ui-alert {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 11px 13px;
  border: 1px solid var(--line);
  border-radius: var(--radius, 8px);
  background: var(--surface-2);
  box-shadow:
    inset 0 1px 0 var(--lui-rim, transparent),
    0 1px 2px rgba(0, 0, 0, 0.03);
  font-size: 13px;
  line-height: 1.55;
  color: var(--ink-2);
}

.ui-alert-icon {
  display: inline-flex;
  flex: 0 0 auto;
  margin-top: 2px;
}

.ui-alert-content {
  flex: 1;
  min-width: 0;
}

.ui-alert-title {
  display: block;
  margin-bottom: 2px;
  color: var(--ink);
  font-weight: 600;
}

.ui-alert-message {
  overflow-wrap: anywhere;
}

.ui-alert-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 2px;
  border: 0;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  border-radius: 4px;
}

.ui-alert-close:hover {
  background: color-mix(in srgb, currentColor 10%, transparent);
  color: var(--ink);
}

.tone-info {
  border-color: color-mix(in srgb, var(--info) 28%, var(--line));
  background: var(--info-bg);
  color: var(--info);
}
.tone-success {
  border-color: color-mix(in srgb, var(--green) 28%, var(--line));
  background: var(--ok-bg);
  color: var(--green);
}
.tone-warn {
  border-color: color-mix(in srgb, var(--amber) 32%, var(--line));
  background: var(--warn-bg);
  color: var(--amber);
}
.tone-crit {
  border-color: color-mix(in srgb, var(--red) 32%, var(--line));
  background: var(--crit-bg);
  color: var(--red);
}

.tone-info .ui-alert-title,
.tone-success .ui-alert-title,
.tone-warn .ui-alert-title,
.tone-crit .ui-alert-title {
  color: inherit;
}
</style>
