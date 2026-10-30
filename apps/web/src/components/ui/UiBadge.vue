<script setup lang="ts">
export interface UiBadgeProps {
  tone?: "forest" | "success" | "warn" | "crit" | "info" | "neutral";
  variant?: "subtle" | "solid" | "outline";
  size?: "sm" | "md";
  dot?: boolean;
  chip?: boolean;
  pulse?: boolean;
}

withDefaults(defineProps<UiBadgeProps>(), {
  tone: "neutral",
  variant: "subtle",
  size: "sm",
  dot: false,
  chip: false,
  pulse: false,
});
</script>

<template>
  <span
    class="ui-badge"
    :class="[
      `tone-${tone}`,
      `variant-${variant}`,
      `size-${size}`,
      {
        'is-chip': chip,
        'has-dot': dot,
      },
    ]"
  >
    <span v-if="dot" class="ui-badge-dot" :class="{ 'is-pulse': pulse }" aria-hidden="true"></span>
    <span class="ui-badge-content"><slot /></span>
  </span>
</template>

<style scoped>
.ui-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--mono);
  font-weight: 400;
  line-height: 1.2;
  letter-spacing: 0.05em;
  white-space: nowrap;
  vertical-align: middle;
  border-radius: 0;
  box-sizing: border-box;
  user-select: none;
}

.is-chip {
  border-radius: 0;
}

.size-sm {
  font-size: 9px;
  padding: 3px 6px;
}
.size-sm.has-dot {
  padding-left: 5px;
}
.size-md {
  font-size: 10px;
  padding: 4px 7px;
}
.size-md.has-dot {
  padding-left: 6px;
}

.tone-forest.variant-subtle {
  color: var(--forest);
  background: color-mix(in srgb, var(--forest) 7%, transparent);
  border: 1px solid color-mix(in srgb, var(--forest) 25%, transparent);
}
.tone-success.variant-subtle {
  color: var(--green);
  background: color-mix(in srgb, var(--green) 7%, transparent);
  border: 1px solid color-mix(in srgb, var(--green) 25%, transparent);
}
.tone-warn.variant-subtle {
  color: var(--amber);
  background: color-mix(in srgb, var(--amber) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--amber) 26%, transparent);
}
.tone-crit.variant-subtle {
  color: var(--red);
  background: color-mix(in srgb, var(--red) 7%, transparent);
  border: 1px solid color-mix(in srgb, var(--red) 25%, transparent);
}
.tone-info.variant-subtle {
  color: var(--info);
  background: color-mix(in srgb, var(--info) 7%, transparent);
  border: 1px solid color-mix(in srgb, var(--info) 24%, transparent);
}
.tone-neutral.variant-subtle {
  color: var(--muted);
  background: transparent;
  border: 1px solid var(--line);
}

.tone-forest.variant-solid {
  background: var(--forest);
  color: var(--forest-ink);
}
.tone-success.variant-solid {
  background: var(--green);
  color: var(--surface);
}
.tone-warn.variant-solid {
  background: var(--amber);
  color: var(--surface);
}
.tone-crit.variant-solid {
  background: var(--red);
  color: var(--surface);
}
.tone-info.variant-solid {
  background: var(--info);
  color: var(--surface);
}
.tone-neutral.variant-solid {
  background: var(--ink);
  color: var(--surface);
}

.variant-outline {
  background: transparent;
}
.tone-forest.variant-outline {
  border: 1px solid color-mix(in srgb, var(--forest) 55%, transparent);
  color: var(--forest);
}
.tone-success.variant-outline {
  border: 1px solid color-mix(in srgb, var(--green) 55%, transparent);
  color: var(--green);
}
.tone-warn.variant-outline {
  border: 1px solid color-mix(in srgb, var(--amber) 55%, transparent);
  color: var(--amber);
}
.tone-crit.variant-outline {
  border: 1px solid color-mix(in srgb, var(--red) 55%, transparent);
  color: var(--red);
}
.tone-info.variant-outline {
  border: 1px solid color-mix(in srgb, var(--info) 55%, transparent);
  color: var(--info);
}
.tone-neutral.variant-outline {
  border: 1px solid var(--line-strong);
  color: var(--muted);
}

.ui-badge-dot {
  width: 4px;
  height: 4px;
  border-radius: 0;
  background: currentColor;
  flex-shrink: 0;
}
.ui-badge-dot.is-pulse {
  animation: dot-pulse 2.4s ease-in-out infinite;
}
@keyframes dot-pulse {
  0%,
  100% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
}

.ui-badge-content {
  display: inline-flex;
  align-items: center;
}
</style>