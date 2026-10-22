<script setup lang="ts">
import { displayName } from "@vision/shared";
import { ref, watch, onMounted, onUnmounted, computed } from "vue";
import { blob } from "../api";
import type { Asset } from "../types";
import type { DetectionBox } from "@vision/contracts";
const props = defineProps<{
  postprocess?: import("@vision/contracts").PostprocessReport;
  compact?: boolean;
  operator?: boolean;
  jpeg?: string;
  assets?: Asset[];
  boxes?: DetectionBox[] | null;
  width?: number;
  height?: number;
  region?: { x: number; y: number; width: number; height: number };
  regions?: {
    x: number;
    y: number;
    width: number;
    height: number;
    label: string;
  }[];
}>();
const toolsOpen = ref(false);
const image = ref(""),
  error = ref(""),
  mode = ref("PREVIEW"),
  zoom = ref(1),
  offset = ref({ x: 0, y: 0 }),
  showBoxes = ref(true),
  actual = ref(false);
const stage = ref<HTMLElement | null>(null),
  fitWidth = ref(416);
let observer: ResizeObserver | null = null;
let oldUrl = "",
  drag: { x: number; y: number; ox: number; oy: number } | null = null;
const size = computed(
    () =>
      props.assets?.find((a) => a.kind === mode.value)?.width ??
      props.width ??
      416,
  ),
  imageHeight = computed(
    () =>
      props.assets?.find((a) => a.kind === mode.value)?.height ??
      props.height ??
      size.value,
  );
const displayBoxes = computed(
  () => mode.value === "PREVIEW" && showBoxes.value,
);
const boxColors = [
  "#60c5ff",
  "#ffc857",
  "#d495ff",
  "#75d69c",
  "#ff9292",
  "#5fdfd4",
];
function boxCaption(box: DetectionBox) {
  const chars = Array.from(displayName(box.label));
  const label =
    chars.length > 22 ? chars.slice(0, 21).join("") + "…" : chars.join("");
  return `${label} ${(box.confidence * 100).toFixed(0)}%${box.trackId ? ` · #${box.trackId}${box.trackConfirmed ? "" : "?"}` : ""}`;
}
function tagWidth(box: DetectionBox) {
  return Math.min(
    size.value,
    10 +
      Array.from(boxCaption(box)).reduce(
        (total, char) => total + (char.charCodeAt(0) > 255 ? 12 : 7),
        0,
      ),
  );
}
const tagX = (box: DetectionBox) =>
  Math.max(0, Math.min(box.x1, size.value - tagWidth(box)));
const tagY = (box: DetectionBox) =>
  Math.max(
    0,
    Math.min(imageHeight.value - 20, box.y1 >= 20 ? box.y1 - 20 : box.y1),
  );
function measure() {
  if (stage.value)
    fitWidth.value = Math.min(
      stage.value.clientWidth,
      (stage.value.clientHeight * size.value) / imageHeight.value,
    );
}
watch([size, imageHeight], measure);
onMounted(() => {
  observer = new ResizeObserver(measure);
  if (stage.value) observer.observe(stage.value);
  measure();
});
watch(
  () => [props.jpeg, props.assets, mode.value],
  async () => {
    error.value = "";
    if (props.jpeg && mode.value === "PREVIEW") {
      image.value = `data:image/jpeg;base64,${props.jpeg}`;
      return;
    }
    const asset = props.assets?.find((a) => a.kind === mode.value);
    if (!asset) {
      image.value = "";
      return;
    }
    try {
      const data = await blob(`/assets/${asset.id}/content`);
      if (oldUrl) URL.revokeObjectURL(oldUrl);
      oldUrl = URL.createObjectURL(data);
      image.value = oldUrl;
    } catch (e) {
      error.value = String(e);
    }
  },
  { immediate: true },
);
function down(e: PointerEvent) {
  if (e.button !== 0) return;
  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  drag = { x: e.clientX, y: e.clientY, ox: offset.value.x, oy: offset.value.y };
}
function move(e: PointerEvent) {
  if (drag)
    offset.value = {
      x: drag.ox + e.clientX - drag.x,
      y: drag.oy + e.clientY - drag.y,
    };
}
function fit() {
  actual.value = false;
  zoom.value = 1;
  offset.value = { x: 0, y: 0 };
}
onUnmounted(() => {
  observer?.disconnect();
  if (oldUrl) URL.revokeObjectURL(oldUrl);
});
</script>
<template>
  <div class="image-viewer">
    <div class="image-toolbar">
      <span class="mono">{{
        mode === "MODEL_INPUT_PREVIEW" ? "模型输入预览" : "采样图像"
      }}</span>
      <div>
        <button
          aria-label="缩小"
          :title="zoom <= 0.25 ? '已到最小缩放' : '缩小'"
          :disabled="zoom <= 0.25"
          @click="zoom = Math.max(0.25, zoom - 0.25)"
        >
          −</button
        ><span v-if="!operator" class="mono"
          >{{ Math.round(zoom * (actual ? 1 : fitWidth / size) * 100) }}%</span
        ><button
          aria-label="放大"
          :title="zoom >= 6 ? '已到最大缩放' : '放大'"
          :disabled="zoom >= 6"
          @click="zoom = Math.min(6, zoom + 0.25)"
        >
          +</button
        ><button @click="fit">适应窗口</button
        ><template v-if="!operator"
          ><button
            v-if="compact"
            :aria-expanded="toolsOpen"
            @click="toolsOpen = !toolsOpen"
          >
            图像工具</button
          ><template v-if="!compact || toolsOpen"
            ><button
              @click="
                actual = true;
                zoom = 1;
                offset = { x: 0, y: 0 };
              "
            >
              1:1</button
            ><button @click="showBoxes = !showBoxes">
              {{ showBoxes ? "隐藏框" : "显示框" }}</button
            ><UiSelect
              v-if="assets"
              v-model="mode"
              aria-label="图像类型"
              size="sm"
            >
              <option value="PREVIEW">预览图</option>
              <option
                v-if="assets.some((a) => a.kind === 'MODEL_INPUT_PREVIEW')"
                value="MODEL_INPUT_PREVIEW"
              >
                重建输入
              </option>
            </UiSelect></template
          ></template
        >
      </div>
    </div>
    <p
      v-if="postprocess?.overflow || postprocess?.invalid"
      class="postprocess-warning"
    >
      候选过多或数据异常，当前显示不用于确认合格，请人工复核。
    </p>
    <div
      class="image-stage"
      ref="stage"
      @pointerdown="down"
      @pointermove="move"
      @pointerup="drag = null"
      @pointercancel="drag = null"
      @wheel.prevent="
        zoom = Math.max(
          0.25,
          Math.min(6, zoom - ($event.deltaY > 0 ? 0.1 : -0.1)),
        )
      "
    >
      <div
        v-if="image"
        class="image-plane"
        :style="{
          width: `${actual ? size : fitWidth}px`,
          maxWidth: 'none',
          flexShrink: 0,
          transform: `translate(${offset.x}px,${offset.y}px) scale(${zoom})`,
        }"
      >
        <img :src="image" alt="采样图像" draggable="false" /><svg
          v-if="
            displayBoxes || (mode === 'PREVIEW' && (region || regions?.length))
          "
          :viewBox="`0 0 ${size} ${imageHeight}`"
        >
          <rect
            v-if="mode === 'PREVIEW' && region"
            :x="region.x * size"
            :y="region.y * imageHeight"
            :width="region.width * size"
            :height="region.height * imageHeight"
            fill="none"
            stroke-dasharray="6 5"
          />
          <g
            v-for="(area, i) in mode === 'PREVIEW' ? (regions ?? []) : []"
            :key="`region-${i}`"
          >
            <rect
              :x="area.x * size"
              :y="area.y * imageHeight"
              :width="area.width * size"
              :height="area.height * imageHeight"
              fill="none"
              style="stroke: #e6ad39"
              stroke-dasharray="6 4"
            />
            <text
              :x="area.x * size + 3"
              :y="Math.max(16, area.y * imageHeight - 5)"
              style="fill: #e6ad39"
            >
              {{ area.label }} · 合格中心范围
            </text>
          </g>
          <g
            v-for="(box, i) in displayBoxes ? (boxes ?? []) : []"
            :key="i"
            :style="{
              '--box-color': boxColors[box.classId % boxColors.length],
            }"
          >
            <title>
              {{ box.label }} · {{ (box.confidence * 100).toFixed(1) }}%{{
                box.trackId
                  ? ` · 跟踪 #${box.trackId}${box.trackConfirmed ? "" : " 待确认"}`
                  : ""
              }}
            </title>
            <rect
              :x="box.x1"
              :y="box.y1"
              :width="box.x2 - box.x1"
              :height="box.y2 - box.y1"
              style="stroke: var(--box-color)"
            />
            <rect
              class="box-label"
              :x="tagX(box)"
              :y="tagY(box)"
              :width="tagWidth(box)"
              height="20"
              style="fill: var(--box-color)"
            />
            <text :x="tagX(box) + 5" :y="tagY(box) + 14">
              {{ boxCaption(box) }}
            </text>
          </g>
        </svg>
      </div>
      <div v-else class="image-empty">
        <b>{{ error ? "图像读取失败" : assets ? "暂无预览图" : "等待图像" }}</b
        ><small>{{
          error || (assets ? "该记录没有可用的预览图" : "连接设备以接收完整帧")
        }}</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.postprocess-warning {
  margin: 0;
  padding: 8px 12px;
  color: var(--red);
  font-size: 12px;
}
</style>
