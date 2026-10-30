<script setup lang="ts">
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";
import Icon from "../Icon.vue";

export interface UiStatProps {
  label: string;
  value: string | number | null;
  unit?: string;
  hint?: string;
  icon?: string;
  tone?: "default" | "success" | "warn" | "crit" | "forest";
  to?: RouteLocationRaw;
}

const props = withDefaults(defineProps<UiStatProps>(), {
  tone: "default",
});
const displayValue = computed(() =>
  props.value == null ||
  props.value === "" ||
  props.value === "—" ||
  (typeof props.value === "number" && !Number.isFinite(props.value))
    ? "暂无数据"
    : props.value,
);
const numeric = computed(
  () =>
    props.value != null &&
    props.value !== "" &&
    Number.isFinite(Number(props.value)),
);

const isLink = computed(() => !!props.to);
</script>

<template>
  <component
    :is="isLink ? 'RouterLink' : 'div'"
    :to="to"
    class="ui-stat"
    :class="[`tone-${tone}`, { 'is-link': isLink }]"
  >
    <div class="ui-stat-header">
      <span class="ui-stat-label">{{ label }}</span>
      <span v-if="icon" class="ui-stat-icon">
        <Icon :name="icon" :size="16" />
      </span>
    </div>

    <div class="ui-stat-body">
      <span
        :key="String(displayValue)"
        class="ui-stat-value mono"
        :class="{ 'is-text': !numeric }"
        >{{ displayValue }}</span
      >
      <span v-if="unit && numeric" class="ui-stat-unit">{{ unit }}</span>
    </div>

    <div v-if="hint || $slots.hint" class="ui-stat-footer">
      <slot name="hint">
        <span class="ui-stat-hint">{{ hint }}</span>
      </slot>
    </div>
  </component>
</template>

<style scoped>
.ui-stat {
  display: flex;
  flex-direction: column;
  background: transparent;
  background-image: none;
  border: 0;
  border-top: 1px solid var(--ink);
  border-radius: 0;
  padding: 15px 18px 17px;
  text-decoration: none;
  color: inherit;
  box-sizing: border-box;
  box-shadow: none;
  transition: background-color 160ms ease;
}

.ui-stat.is-link:hover {
  background: color-mix(in srgb, var(--surface) 60%, transparent);
  border-color: var(--ink);
}

.ui-stat-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.ui-stat-label {
  font-family: var(--mono);
  font-size: 8.5px;
  font-weight: 400;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--muted);
}

.ui-stat-icon {
  color: var(--muted);
  display: inline-flex;
  align-items: center;
}

.ui-stat-body {
  display: flex;
  align-items: baseline;
  gap: 5px;
  margin: 8px 0 0;
}

.ui-stat-value {
  font-family: var(--display);
  font-size: clamp(30px, 2.8vw, 42px);
  font-weight: 400;
  line-height: 1;
  letter-spacing: -0.02em;
  color: var(--ink);
}
.ui-stat-value.is-text {
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.5;
  font-weight: 500;
}

.ui-stat-unit {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.06em;
  color: var(--muted);
}

.ui-stat-footer {
  margin-top: 7px;
  font-size: 9.5px;
  line-height: 1.55;
  color: var(--muted);
}

.tone-forest .ui-stat-value,
.tone-forest .ui-stat-icon {
  color: var(--forest);
}
.tone-success .ui-stat-value,
.tone-success .ui-stat-icon {
  color: var(--green);
}
.tone-warn .ui-stat-value,
.tone-warn .ui-stat-icon {
  color: var(--amber);
}
.tone-crit .ui-stat-value,
.tone-crit .ui-stat-icon {
  color: var(--red);
}
</style>