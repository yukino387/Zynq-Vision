<script setup lang="ts">
import { displayName } from "@vision/shared";
import { ref, watch, onMounted, onUnmounted, computed } from "vue";
import { blob } from "../api";
import type { Asset } from "../types";
import type { DetectionBox } from "@vision/contracts";
const props = defineProps<{
  compact?: boolean;
  jpeg?: string;
  assets?: Asset[];
  boxes?: DetectionBox[] | null;
  width?: number;
  height?: number;
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
        ><span class="mono"
          >{{ Math.round(zoom * (actual ? 1 : fitWidth / size) * 100) }}%</span
        ><button
          aria-label="放大"
          :title="zoom >= 6 ? '已到最大缩放' : '放大'"
          :disabled="zoom >= 6"
          @click="zoom = Math.min(6, zoom + 0.25)"
        >
          +</button
        ><button @click="fit">适应窗口</button
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
          ><select v-if="assets" v-model="mode" aria-label="图像类型">
            <option value="PREVIEW">预览图</option>
            <option
              v-if="assets.some((a) => a.kind === 'MODEL_INPUT_PREVIEW')"
              value="MODEL_INPUT_PREVIEW"
            >
              重建输入
            </option>
          </select></template
        >
      </div>
    </div>
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
          v-if="displayBoxes"
          :viewBox="`0 0 ${size} ${imageHeight}`"
        >
          <g v-for="(box, i) in boxes ?? []" :key="i">
            <rect
              :x="box.x1"
              :y="box.y1"
              :width="box.x2 - box.x1"
              :height="box.y2 - box.y1"
            />
            <rect
              class="box-label"
              :x="box.x1"
              :y="Math.max(0, box.y1 - 20)"
              :width="Math.min(220, box.label.length * 11 + 48)"
              height="20"
            />
            <text :x="box.x1 + 5" :y="Math.max(15, box.y1 - 6)">
              {{ displayName(box.label) }}
              {{ (box.confidence * 100).toFixed(0) }}%
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
