<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    /** 数值序列，按时间先后。null 表示这一段没有数据，会断开。 */
    values: (number | null)[];
    width?: number;
    height?: number;
    /** 低于此比例的点标为异常色 */
    threshold?: number;
    unit?: string;
    label?: string;
  }>(),
  { width: 320, height: 72 },
);

const points = computed(() =>
  props.values.filter((v): v is number => v !== null),
);
const bounds = computed(() => {
  if (!points.value.length) return null;
  const min = Math.min(...points.value),
    max = Math.max(...points.value);
  // 全平的序列给一个人造区间，否则线会贴在边上
  return min === max ? { min: min - 1, max: max + 1 } : { min, max };
});
/** 折线路径与面积路径；x 按索引铺满，y 按 min/max 归一。 */
const geometry = computed(() => {
  const b = bounds.value;
  if (!b || !props.values.length) return null;
  const n = props.values.length;
  const pad = 6;
  const h = props.height - pad * 2;
  const x = (i: number) =>
    n === 1 ? props.width / 2 : (i / (n - 1)) * props.width;
  const y = (v: number) => pad + h - ((v - b.min) / (b.max - b.min)) * h;
  const segments: { x: number; y: number }[][] = [];
  let run: { x: number; y: number }[] = [];
  props.values.forEach((v, i) => {
    if (v === null) {
      if (run.length) segments.push(run);
      run = [];
      return;
    }
    run.push({ x: x(i), y: y(v) });
  });
  if (run.length) segments.push(run);
  const last = segments.at(-1)?.at(-1) ?? null;
  return {
    lines: segments.map((s) =>
      s.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" "),
    ),
    area: segments
      .map((s) => {
        const first = s[0],
          last = s.at(-1);
        if (!first || !last) return "";
        const line = s.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" ");
        return `${line}L${last.x},${props.height}L${first.x},${props.height}Z`;
      })
      .filter(Boolean)
      .join(" "),
    last,
  };
});
const range = computed(() =>
  bounds.value
    ? `${bounds.value.min.toFixed(0)}–${bounds.value.max.toFixed(0)}${props.unit ?? ""}`
    : "无数据",
);
</script>

<template>
  <div class="spark">
    <div class="spark-head">
      <span class="lbl">{{ label }}</span>
      <span class="mono rng">{{ range }}</span>
    </div>
    <svg
      v-if="geometry"
      :viewBox="`0 0 ${width} ${height}`"
      :height="height"
      preserveAspectRatio="none"
      role="img"
      :aria-label="`${label ?? '趋势'}，范围 ${range}`"
    >
      <path class="area" :d="geometry.area" />
      <path
        v-for="(d, i) in geometry.lines"
        :key="i"
        class="line"
        :d="d"
        fill="none"
      />
      <circle
        v-if="geometry.last"
        class="tip"
        :cx="geometry.last.x"
        :cy="geometry.last.y"
        r="2.5"
      />
    </svg>
    <div v-else class="spark-empty">等待遥测</div>
  </div>
</template>
