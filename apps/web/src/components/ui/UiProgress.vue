<script setup lang="ts">
import { computed } from "vue";

export interface UiProgressProps {
  value?: number | null;
  tone?: "forest" | "success" | "warn" | "crit";
}

const props = withDefaults(defineProps<UiProgressProps>(), {
  value: null,
  tone: "forest",
});

const clamped = computed(() =>
  props.value == null || !Number.isFinite(props.value)
    ? 0
    : Math.min(100, Math.max(0, props.value)),
);
const known = computed(
  () => props.value != null && Number.isFinite(props.value),
);
</script>

<template>
  <div
    class="ui-progress"
    :class="[`tone-${tone}`, { 'is-unknown': !known }]"
    role="progressbar"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuenow="known ? clamped : undefined"
    :aria-valuetext="known ? `${clamped}%` : '进度未上报'"
  >
    <span class="ui-progress-fill" :style="{ width: `${clamped}%` }"></span>
  </div>
</template>

<style scoped>
.ui-progress {
  position: relative;
  display: block;
  width: 100%;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-2);
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.1);
  box-sizing: border-box;
}

.ui-progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--forest);
  background-image: linear-gradient(
    90deg,
    color-mix(in srgb, var(--forest) 72%, var(--surface)) 0%,
    var(--forest) 100%
  );
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2);
  transition: width var(--lui-base, 240ms) var(--lui-ease, ease);
}

.is-unknown {
  background-image: repeating-linear-gradient(
    -45deg,
    transparent 0 5px,
    color-mix(in srgb, var(--line-strong) 30%, transparent) 5px 7px
  );
}

.tone-success .ui-progress-fill {
  background: var(--green);
  background-image: linear-gradient(
    90deg,
    color-mix(in srgb, var(--green) 72%, var(--surface)) 0%,
    var(--green) 100%
  );
}
.tone-warn .ui-progress-fill {
  background: var(--amber);
  background-image: linear-gradient(
    90deg,
    color-mix(in srgb, var(--amber) 72%, var(--surface)) 0%,
    var(--amber) 100%
  );
}
.tone-crit .ui-progress-fill {
  background: var(--red);
  background-image: linear-gradient(
    90deg,
    color-mix(in srgb, var(--red) 72%, var(--surface)) 0%,
    var(--red) 100%
  );
}
</style>
