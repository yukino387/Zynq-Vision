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
  font-family: inherit;
  font-weight: 550;
  line-height: 1;
  white-space: nowrap;
  vertical-align: middle;
  border-radius: var(--radius, 4px);
  box-sizing: border-box;
  user-select: none;
}

.is-chip {
  border-radius: 999px;
}

/* 尺寸体系 */
.size-sm {
  font-size: 11px;
  padding: 3px 6px;
}
.size-sm.has-dot {
  padding-left: 5px;
}

.size-md {
  font-size: 12px;
  padding: 4px 8px;
}
.size-md.has-dot {
  padding-left: 7px;
}

/* 变体与色调：subtle */
.tone-forest.variant-subtle {
  background: color-mix(in srgb, var(--forest) 12%, transparent);
  color: var(--forest);
  border: 1px solid color-mix(in srgb, var(--forest) 25%, transparent);
}
.tone-success.variant-subtle {
  background: var(--ok-bg, #e1eee2);
  color: var(--green, #27734b);
  border: 1px solid color-mix(in srgb, var(--green) 25%, transparent);
}
.tone-warn.variant-subtle {
  background: var(--warn-bg, #f6e9c9);
  color: var(--amber, #98610b);
  border: 1px solid var(--warn-line, #d8b66b);
}
.tone-crit.variant-subtle {
  background: var(--crit-bg, #f5e0da);
  color: var(--red, #b6372a);
  border: 1px solid var(--crit-line, #d9a097);
}
.tone-info.variant-subtle {
  background: var(--info-bg, #e5e8e1);
  color: var(--info, #5c645d);
  border: 1px solid color-mix(in srgb, var(--info) 25%, transparent);
}
.tone-neutral.variant-subtle {
  background: var(--surface-2);
  color: var(--ink-2);
  border: 1px solid var(--line);
}

/* 变体：solid */
.tone-forest.variant-solid {
  background: var(--forest);
  color: var(--forest-ink);
}
.tone-success.variant-solid {
  background: var(--green, #27734b);
  color: #fff;
}
.tone-warn.variant-solid {
  background: var(--amber, #98610b);
  color: #fff;
}
.tone-crit.variant-solid {
  background: var(--red, #b6372a);
  color: #fff;
}
.tone-info.variant-solid {
  background: var(--info, #5c645d);
  color: #fff;
}
.tone-neutral.variant-solid {
  background: var(--ink-2);
  color: var(--surface);
}

/* 变体：outline */
.variant-outline {
  background: transparent;
}
.tone-forest.variant-outline {
  border: 1px solid var(--forest);
  color: var(--forest);
}
.tone-success.variant-outline {
  border: 1px solid var(--green, #27734b);
  color: var(--green, #27734b);
}
.tone-warn.variant-outline {
  border: 1px solid var(--amber, #98610b);
  color: var(--amber, #98610b);
}
.tone-crit.variant-outline {
  border: 1px solid var(--red, #b6372a);
  color: var(--red, #b6372a);
}
.tone-info.variant-outline {
  border: 1px solid var(--info, #5c645d);
  color: var(--info, #5c645d);
}
.tone-neutral.variant-outline {
  border: 1px solid var(--line-strong);
  color: var(--ink-2);
}

/* 状态小圆点 */
.ui-badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.ui-badge-dot.is-pulse {
  animation: dot-pulse 1.8s ease-in-out infinite;
}

@keyframes dot-pulse {
  0% {
    transform: scale(0.95);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.3);
    opacity: 1;
    box-shadow: 0 0 8px currentColor;
  }
  100% {
    transform: scale(0.95);
    opacity: 0.8;
  }
}

.ui-badge-content {
  display: inline-flex;
  align-items: center;
}
</style>
