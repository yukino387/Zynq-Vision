<script setup lang="ts">
import { computed, ref } from "vue";

interface Point {
  label: string;
  value: number | null;
}

const props = withDefaults(
  defineProps<{
    points: Point[];
    label: string;
    height?: number;
    unit?: string;
    color?: string;
    min?: number;
    max?: number;
    decimals?: number;
    emptyText?: string;
  }>(),
  {
    height: 200,
    unit: "",
    color: "var(--forest)",
    decimals: 0,
    emptyText: "暂无数据",
  },
);

const width = 680,
  pad = { top: 14, right: 16, bottom: 28, left: 48 },
  plotWidth = width - pad.left - pad.right,
  plotHeight = computed(() => props.height - pad.top - pad.bottom);
const svg = ref<SVGSVGElement | null>(null),
  hover = ref<number | null>(null);

function niceMax(value: number) {
  if (value <= 4) return 4;
  const power = 10 ** Math.floor(Math.log10(value));
  const unit = value / power;
  return (unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * power;
}

const finite = computed(() =>
  props.points
    .map((point) => point.value)
    .filter(
      (value): value is number => value != null && Number.isFinite(value),
    ),
);
const bounds = computed(() => {
  if (!finite.value.length) return null;
  const min = props.min ?? Math.min(0, ...finite.value);
  const max = props.max ?? niceMax(Math.max(1, ...finite.value));
  return { min, max: max === min ? min + 1 : max };
});
const hasData = computed(() => finite.value.length > 0);

const xFor = (index: number) =>
  pad.left +
  (props.points.length <= 1
    ? plotWidth / 2
    : (index / (props.points.length - 1)) * plotWidth);
const yFor = (value: number) => {
  const range = bounds.value!;
  return (
    pad.top +
    plotHeight.value -
    ((value - range.min) / (range.max - range.min)) * plotHeight.value
  );
};

const segments = computed(() => {
  if (!bounds.value) return [];
  const result: { x: number; y: number }[][] = [];
  let run: { x: number; y: number }[] = [];
  props.points.forEach((point, index) => {
    if (point.value == null) {
      if (run.length) result.push(run);
      run = [];
      return;
    }
    run.push({ x: xFor(index), y: yFor(point.value) });
  });
  if (run.length) result.push(run);
  return result;
});

const lines = computed(() =>
  segments.value.map((segment) =>
    segment
      .map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`)
      .join(" "),
  ),
);
const areas = computed(() =>
  segments.value.flatMap((segment, index) => {
    if (segment.length <= 1) return [];
    const first = segment[0]!,
      last = segment.at(-1)!;
    return [
      `${lines.value[index]}L${last.x},${pad.top + plotHeight.value}L${first.x},${pad.top + plotHeight.value}Z`,
    ];
  }),
);
const singlePoint = computed(() =>
  segments.value.length === 1 && segments.value[0]!.length === 1
    ? segments.value[0]![0]!
    : null,
);

const grid = computed(() => {
  const range = bounds.value;
  if (!range) return [];
  return Array.from({ length: 5 }, (_, index) => {
    const value = range.min + ((range.max - range.min) * index) / 4;
    return {
      y: yFor(value),
      label: `${Math.round(value)}${props.unit}`,
    };
  });
});

const xTicks = computed(() => {
  const count = props.points.length;
  if (!count) return [];
  const tickCount = Math.min(6, count);
  const indexes = new Set<number>();
  if (tickCount === 1) indexes.add(0);
  else
    for (let index = 0; index < tickCount; index++)
      indexes.add(Math.round((index / (tickCount - 1)) * (count - 1)));
  return [...indexes].map((index) => ({
    key: index,
    x: xFor(index),
    label: props.points[index]!.label,
  }));
});

const hoverPoint = computed(() =>
  hover.value == null ? null : (props.points[hover.value] ?? null),
);
const hoverX = computed(() => (hover.value == null ? 0 : xFor(hover.value)));
const hoverY = computed(() =>
  hoverPoint.value?.value == null ? null : yFor(hoverPoint.value.value),
);
const tipLeft = computed(() => `${(hoverX.value / width) * 100}%`);

function format(value: number | null) {
  return value == null
    ? "无数据"
    : `${value.toFixed(props.decimals)}${props.unit}`;
}

function onMove(event: PointerEvent) {
  const rect = svg.value?.getBoundingClientRect();
  if (!rect || props.points.length <= 1) {
    hover.value = props.points.length ? 0 : null;
    return;
  }
  const x = ((event.clientX - rect.left) / rect.width) * width;
  const index = Math.round(
    ((x - pad.left) / plotWidth) * (props.points.length - 1),
  );
  hover.value = Math.max(0, Math.min(props.points.length - 1, index));
}
</script>

<template>
  <div v-if="hasData" class="trend">
    <svg
      ref="svg"
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      :aria-label="`${label}趋势`"
      @pointermove="onMove"
      @pointerleave="hover = null"
    >
      <g aria-hidden="true">
        <line
          v-for="line in grid"
          :key="line.y"
          class="grid"
          :x1="pad.left"
          :x2="pad.left + plotWidth"
          :y1="line.y"
          :y2="line.y"
        />
        <text
          v-for="line in grid"
          :key="`label-${line.y}`"
          class="axis-label"
          :x="pad.left - 8"
          :y="line.y"
          text-anchor="end"
          dy="0.32em"
        >
          {{ line.label }}
        </text>
        <text
          v-for="tick in xTicks"
          :key="tick.key"
          class="axis-label"
          :x="tick.x"
          :y="height - 8"
          text-anchor="middle"
        >
          {{ tick.label }}
        </text>
      </g>
      <path
        v-for="(area, index) in areas"
        :key="`area-${index}`"
        class="area"
        :d="area"
        :style="{ fill: color }"
      />
      <path
        v-for="(line, index) in lines"
        :key="`line-${index}`"
        class="line"
        :d="line"
        :style="{ stroke: color }"
      />
      <circle
        v-if="singlePoint"
        :cx="singlePoint.x"
        :cy="singlePoint.y"
        r="3"
        :style="{ fill: color }"
      />
      <g v-if="hoverPoint" aria-hidden="true">
        <line
          class="crosshair"
          :x1="hoverX"
          :x2="hoverX"
          :y1="pad.top"
          :y2="pad.top + plotHeight"
        />
        <circle
          v-if="hoverY != null"
          :cx="hoverX"
          :cy="hoverY"
          r="4"
          :style="{
            fill: color,
            stroke: 'var(--surface)',
            'stroke-width': 2,
          }"
        />
      </g>
    </svg>
    <div
      v-if="hoverPoint"
      class="chart-tip"
      :style="{ left: tipLeft }"
      role="status"
    >
      <b>{{ hoverPoint.label }}</b>
      <span class="mono">{{ format(hoverPoint.value) }}</span>
    </div>
    <details class="chart-data">
      <summary>数据表</summary>
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>{{ label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(point, index) in points" :key="index">
            <td>{{ point.label }}</td>
            <td class="mono">{{ format(point.value) }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </div>
  <p v-else class="chart-empty">{{ emptyText }}</p>
</template>

<style scoped>
.trend {
  position: relative;
}
svg {
  display: block;
  width: 100%;
  height: auto;
  touch-action: none;
}
.grid {
  stroke: var(--line);
  stroke-width: 1;
}
.axis-label {
  fill: var(--muted);
  font-family: var(--mono);
  font-size: 10px;
}
.line {
  fill: none;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.area {
  opacity: 0.12;
  stroke: none;
}
.crosshair {
  stroke: var(--line-strong);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}
.chart-tip {
  position: absolute;
  top: 0;
  display: flex;
  gap: 8px;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  background: var(--surface);
  box-shadow: 0 4px 14px #0002;
  font-size: 11px;
  white-space: nowrap;
  transform: translateX(-50%);
  pointer-events: none;
}
.chart-empty {
  display: grid;
  place-items: center;
  min-height: 120px;
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.chart-data {
  margin-top: 10px;
  font-size: 12px;
}
.chart-data summary {
  cursor: pointer;
  color: var(--muted);
}
.chart-data table {
  width: 100%;
  margin-top: 8px;
  border-collapse: collapse;
}
.chart-data th,
.chart-data td {
  padding: 4px 6px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
.chart-data th {
  color: var(--muted);
  font-weight: 550;
}
</style>
