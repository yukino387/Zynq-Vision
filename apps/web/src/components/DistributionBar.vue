<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

interface Slice {
  label: string;
  value: number;
  tone: "quiet" | "ok" | "info" | "warn" | "crit";
}

const props = defineProps<{ slices: Slice[]; unit?: string }>();

const total = computed(() =>
  props.slices.reduce((sum, s) => sum + Math.max(0, s.value), 0),
);
/** 零值不占宽度，否则条上会出现看不见但占位的段。 */
const visible = computed(() => props.slices.filter((s) => s.value > 0));
const percent = (value: number) =>
  total.value
    ? ((value / total.value) * 100).toFixed(value / total.value < 0.01 ? 1 : 0)
    : "0";
const shown = ref(false);
onMounted(() => requestAnimationFrame(() => (shown.value = true)));
</script>

<template>
  <div class="dist">
    <div
      v-if="total"
      class="dist-bar"
      role="img"
      :aria-label="
        slices.map((s) => `${s.label} ${s.value}`).join('，') + (unit ?? '')
      "
    >
      <span
        v-for="s in visible"
        :key="s.label"
        :class="['seg', s.tone]"
        :style="{ width: shown ? `${(s.value / total) * 100}%` : '0%' }"
        :title="`${s.label} ${s.value}`"
      ></span>
    </div>
    <div v-else class="dist-empty">本时段没有数据</div>
    <ul class="dist-legend">
      <li v-for="s in slices" :key="s.label">
        <span class="sw" :class="s.tone"></span>
        <span class="nm">{{ s.label }}</span>
        <span class="vl mono">{{ s.value }}{{ unit }}</span>
        <span v-if="total" class="pc mono">{{ percent(s.value) }}%</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.seg {
  transition: width 320ms var(--lui-ease, ease);
}
</style>
