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
      <span class="ui-stat-value mono" :class="{ 'is-text': !numeric }">{{
        displayValue
      }}</span>
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
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius, 8px);
  padding: 14px 18px;
  text-decoration: none;
  color: inherit;
  box-sizing: border-box;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.ui-stat.is-link:hover {
  border-color: var(--line-strong);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.ui-stat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ui-stat-label {
  font-size: 12px;
  font-weight: 550;
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
  gap: 4px;
  margin: 6px 0 2px;
}

.ui-stat-value {
  font-size: clamp(20px, 2.2vw, 28px);
  font-weight: 700;
  color: var(--ink);
  line-height: 1.2;
}

.ui-stat-unit {
  font-size: 13px;
  color: var(--muted);
  font-weight: 500;
}
.ui-stat-value.is-text {
  font-size: 16px;
  line-height: 1.5;
  font-weight: 500;
}

.ui-stat-footer {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
}

/* 强调色调 */
.tone-forest .ui-stat-value,
.tone-forest .ui-stat-icon {
  color: var(--forest);
}

.tone-success .ui-stat-value,
.tone-success .ui-stat-icon {
  color: var(--green, #27734b);
}

.tone-warn .ui-stat-value,
.tone-warn .ui-stat-icon {
  color: var(--amber, #98610b);
}

.tone-crit .ui-stat-value,
.tone-crit .ui-stat-icon {
  color: var(--red, #b6372a);
}
</style>
