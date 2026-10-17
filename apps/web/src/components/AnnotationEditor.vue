<script setup lang="ts">
import { displayName, defectClasses } from "@vision/shared";
import { ref, watch, onMounted, onUnmounted, computed } from "vue";
import type { Sample } from "../types";
import type { DetectionBox } from "@vision/contracts";
import { blob, post } from "../api";
import { useNotificationStore } from "../stores/notifications";
const props = defineProps<{ sample: Sample }>(),
  emit = defineEmits<{ saved: [next: boolean] }>(),
  notices = useNotificationStore();
const image = ref(""),
  boxes = ref<DetectionBox[]>([]),
  selected = ref(-1),
  classId = ref(0),
  negative = ref(false),
  loadingSample = ref(false),
  zoom = ref(1),
  busy = ref(false),
  savedLocal = ref(false);
const asset = computed(() =>
  props.sample.assets.find((a) => a.kind === "PREVIEW"),
);
const width = computed(() => asset.value?.width ?? 416),
  height = computed(() => asset.value?.height ?? 416);
let start: {
  x: number;
  y: number;
  index: number;
  mode: "draw" | "move" | "resize";
  original: DetectionBox | null;
} | null = null;
let url = "";
watch(
  () => props.sample.id,
  async () => {
    const sampleId = props.sample.id;
    loadingSample.value = true;
    image.value = "";
    savedLocal.value = false;
    start = null;
    const draft = localStorage.getItem(`vision.annotation.${props.sample.id}`);
    boxes.value = draft
      ? (JSON.parse(draft) as DetectionBox[])
      : (props.sample.annotations[0]?.boxes ?? []).map((b) => ({ ...b }));
    selected.value = -1;
    negative.value =
      !boxes.value.length && props.sample.annotations[0]?.status === "COMPLETE";
    if (asset.value) {
      try {
        if (url) URL.revokeObjectURL(url);
        const content = await blob(`/assets/${asset.value.id}/content`);
        if (sampleId !== props.sample.id) return;
        url = URL.createObjectURL(content);
        image.value = url;
      } catch (e) {
        notices.error(e);
      }
    }
    if (sampleId === props.sample.id) loadingSample.value = false;
  },
  { immediate: true },
);
watch(selected, (index) => {
  if (index >= 0) classId.value = boxes.value[index]!.classId;
});
watch(classId, (value) => {
  if (selected.value >= 0 && defectClasses[value]) {
    boxes.value[selected.value]!.classId = value;
    boxes.value[selected.value]!.label = defectClasses[value]!;
  }
});
watch(
  () => boxes.value.length,
  (count) => {
    if (count) negative.value = false;
  },
);
watch(
  boxes,
  () => {
    if (loadingSample.value) return;
    localStorage.setItem(
      `vision.annotation.${props.sample.id}`,
      JSON.stringify(boxes.value),
    );
    savedLocal.value = true;
  },
  { deep: true },
);
function coords(e: PointerEvent) {
  const svg = e.currentTarget as SVGElement,
    rect = svg.getBoundingClientRect();
  return {
    x: Math.max(
      0,
      Math.min(
        width.value,
        ((e.clientX - rect.left) / rect.width) * width.value,
      ),
    ),
    y: Math.max(
      0,
      Math.min(
        height.value,
        ((e.clientY - rect.top) / rect.height) * height.value,
      ),
    ),
  };
}
function down(e: PointerEvent) {
  if (!image.value || busy.value || e.button !== 0) return;
  const p = coords(e),
    target = e.target as SVGElement,
    index = Number(target.dataset.index ?? -1);
  (e.currentTarget as Element).setPointerCapture(e.pointerId);
  if (index >= 0) {
    selected.value = index;
    const b = boxes.value[index]!;
    start = {
      ...p,
      index,
      mode: target.tagName === "circle" ? "resize" : "move",
      original: { ...b },
    };
  } else {
    const box = {
      classId: classId.value,
      label: defectClasses[classId.value]!,
      confidence: 1,
      x1: p.x,
      y1: p.y,
      x2: p.x + 1,
      y2: p.y + 1,
    };
    boxes.value.push(box);
    selected.value = boxes.value.length - 1;
    start = { ...p, index: selected.value, mode: "draw", original: null };
  }
}
function move(e: PointerEvent) {
  if (!start) return;
  const p = coords(e),
    b = boxes.value[start.index]!;
  if (start.mode === "draw") {
    b.x1 = Math.min(start.x, p.x);
    b.y1 = Math.min(start.y, p.y);
    b.x2 = Math.max(start.x, p.x);
    b.y2 = Math.max(start.y, p.y);
  } else if (start.mode === "resize") {
    b.x2 = Math.max(b.x1 + 1, p.x);
    b.y2 = Math.max(b.y1 + 1, p.y);
  } else {
    const o = start.original!,
      w = o.x2 - o.x1,
      h = o.y2 - o.y1;
    b.x1 = Math.max(0, Math.min(width.value - w, o.x1 + p.x - start.x));
    b.y1 = Math.max(0, Math.min(height.value - h, o.y1 + p.y - start.y));
    b.x2 = b.x1 + w;
    b.y2 = b.y1 + h;
  }
}
function up() {
  if (start) {
    const b = boxes.value[start.index];
    if (b && (b.x2 - b.x1 < 2 || b.y2 - b.y1 < 2))
      boxes.value.splice(start.index, 1);
  }
  start = null;
}
function remove() {
  if (selected.value >= 0) boxes.value.splice(selected.value, 1);
  selected.value = -1;
}
async function save(status: "DRAFT" | "COMPLETE", next = false) {
  if (busy.value) return;
  if (status === "COMPLETE" && !boxes.value.length && !negative.value) {
    notices.add("没有缺陷时，请勾选“这是一张无缺陷样本”", true);
    return;
  }
  if (
    boxes.value.some(
      (box) => !Number.isInteger(box.classId) || !defectClasses[box.classId],
    )
  ) {
    notices.add("请选择六类缺陷中的一个类别", true);
    return;
  }
  busy.value = true;
  try {
    await post(`/samples/${props.sample.id}/annotations`, {
      boxes: boxes.value.map(({ classId, confidence, x1, y1, x2, y2 }) => ({
        classId,
        label: defectClasses[classId]!,
        confidence,
        x1,
        y1,
        x2,
        y2,
      })),
      status,
    });
    localStorage.removeItem(`vision.annotation.${props.sample.id}`);
    notices.add(status === "COMPLETE" ? "标注已完成" : "草稿已保存");
    savedLocal.value = false;
    emit("saved", next);
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
function key(e: KeyboardEvent) {
  if ((e.target as HTMLElement).tagName.match(/INPUT|TEXTAREA|SELECT/)) return;
  if (e.key === "Delete") remove();
  if (/^[1-6]$/.test(e.key) && !e.ctrlKey && !e.metaKey)
    classId.value = Number(e.key) - 1;
  if (e.ctrlKey && e.key === "Enter") {
    e.preventDefault();
    void save("COMPLETE", true);
  }
  if (e.ctrlKey && e.key === "s") {
    e.preventDefault();
    void save("DRAFT");
  }
}
onMounted(() => window.addEventListener("keydown", key));
onUnmounted(() => {
  window.removeEventListener("keydown", key);
  if (url) URL.revokeObjectURL(url);
});
</script>
<template>
  <div class="annotation-workspace">
    <div class="toolbar">
      <label style="margin: 0"
        >缺陷类别<select v-model.number="classId" aria-label="当前缺陷类别">
          <option v-for="(label, id) in defectClasses" :key="id" :value="id">
            {{ id + 1 }} · {{ label }}
          </option>
        </select></label
      >
      <span class="annotation-tool-hint">{{
        selected >= 0 ? "修改选中框的类别" : "拖动图片，框选缺陷位置"
      }}</span>
      <button @click="zoom = Math.max(1, zoom - 0.25)" aria-label="缩小图像">
        −</button
      ><span class="mono">{{ zoom * 100 }}%</span
      ><button @click="zoom = Math.min(3, zoom + 0.25)" aria-label="放大图像">
        +</button
      ><button :disabled="selected < 0" @click="remove">删除框</button>
    </div>
    <div class="annotation-canvas-scroll">
      <div
        class="annotation-stage"
        :style="{
          width: `${zoom * 100}%`,
          maxWidth: `calc((var(--annotation-available) - 50px) * ${(zoom * width) / height})`,
        }"
      >
        <img :src="image" alt="待标注图像" /><svg
          :viewBox="`0 0 ${width} ${height}`"
          @pointerdown="down"
          @pointermove="move"
          @pointerup="up"
          @pointercancel="up"
        >
          <g v-for="(b, i) in boxes" :key="i">
            <rect
              :data-index="i"
              :x="b.x1"
              :y="b.y1"
              :width="b.x2 - b.x1"
              :height="b.y2 - b.y1"
              :style="{
                stroke: i === selected ? 'var(--amber)' : 'var(--forest)',
              }"
            />
            <text :data-index="i" :x="b.x1" :y="Math.max(12, b.y1 - 4)">
              {{ displayName(b.label) }}
            </text>
            <circle
              v-if="i === selected"
              :data-index="i"
              :cx="b.x2"
              :cy="b.y2"
              r="6"
              fill="var(--amber)"
            />
          </g>
        </svg>
      </div>
    </div>
    <aside class="annotation-inspector">
      <h3>
        标注对象 <span class="mono">{{ boxes.length }}</span>
      </h3>
      <p class="note">
        ① 选类别 · ② 框出缺陷 · ③ 保存并继续。拖动框可移动，右下角可调整大小。{{
          savedLocal ? "未提交的草稿已保存在本机。" : ""
        }}
      </p>
      <div
        v-for="(b, i) in boxes"
        :key="i"
        class="annotation-object"
        :class="{ active: selected === i }"
      >
        <button @click="selected = i" :aria-pressed="selected === i">
          {{ i + 1 }} ·
          {{ defectClasses[b.classId] ?? "请选择有效类别" }}</button
        ><button
          @click="
            selected = i;
            remove();
          "
          :aria-label="`删除第${i + 1}个框`"
        >
          删除
        </button>
        <small
          >{{ Math.round(b.x2 - b.x1) }} ×
          {{ Math.round(b.y2 - b.y1) }} 像素</small
        >
      </div>
      <p v-if="!boxes.length" class="note">
        还没有标注框。在左侧图片上拖动鼠标绘制。
      </p>
      <label v-if="!boxes.length" class="check-row"
        ><input type="checkbox" v-model="negative" />这是一张无缺陷样本</label
      >
      <div class="annotation-save-actions">
        <button
          class="primary"
          @click="save('COMPLETE', true)"
          :disabled="busy || (!boxes.length && !negative)"
        >
          完成并标注下一张
        </button>
        <button
          @click="save('COMPLETE')"
          :disabled="busy || (!boxes.length && !negative)"
        >
          仅完成当前张
        </button>
        <button @click="save('DRAFT')" :disabled="busy">保存草稿</button>
      </div>
      <p class="annotation-shortcuts">
        1–6 切换类别 · Delete 删除框<br />Ctrl+S 保存草稿 · Ctrl+Enter
        完成并继续
      </p>
    </aside>
  </div>
</template>
<style scoped>
.annotation-tool-hint {
  font-size: 12px;
  color: var(--muted);
  margin-right: auto;
}
.annotation-object {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 7px;
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}
.annotation-object > button:first-child {
  text-align: left;
  font-size: 12px;
}
.annotation-object.active > button:first-child {
  color: var(--forest);
  border-color: var(--forest);
}
.annotation-object small {
  grid-column: 1/-1;
  font-size: 11px;
  color: var(--muted);
}
.annotation-save-actions {
  display: grid;
  gap: 8px;
  margin-top: 24px;
}
.annotation-shortcuts {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.8;
  margin-top: 16px;
}
</style>
