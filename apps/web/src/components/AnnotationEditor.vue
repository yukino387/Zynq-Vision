<script setup lang="ts">
import { displayName } from "@vision/shared";
import { ref, watch, onMounted, onUnmounted, computed, nextTick } from "vue";
import type { Sample } from "../types";
import type { DetectionBox } from "@vision/contracts";
import { blob, post } from "../api";
import { useNotificationStore } from "../stores/notifications";
const props = defineProps<{
    sample: Sample;
    position?: number;
    total?: number;
    advancing?: boolean;
  }>(),
  emit = defineEmits<{ saved: [next: boolean]; skip: []; discard: [] }>(),
  notices = useNotificationStore();
const image = ref(""),
  boxes = ref<DetectionBox[]>([]),
  selected = ref(-1),
  activeClass = ref(0),
  noObject = ref(false),
  loadingSample = ref(false),
  zoom = ref(1),
  busy = ref(false),
  savedLocal = ref(false),
  draftApplied = ref(false),
  discarding = ref(false),
  showHelp = ref(false),
  tool = ref<"draw" | "edit">("draw"),
  cursor = ref<{ x: number; y: number } | null>(null),
  imageError = ref(false),
  draft = ref<{
    boxes: DetectionBox[];
    savedAt: number;
    baseVersion: number | null;
    noObject: boolean;
  } | null>(null),
  history = ref<DetectionBox[][]>([]),
  future = ref<DetectionBox[][]>([]);
const asset = computed(() =>
  props.sample.assets.find((a) => a.kind === "PREVIEW"),
);
const classes = computed<string[]>(() =>
  Array.isArray(props.sample.plan?.rules?.classes)
    ? props.sample.plan.rules.classes
    : [],
);
const canAnnotate = computed(() => classes.value.length > 0);
const locked = computed(
  () => busy.value || loadingSample.value || props.advancing,
);
const palette = [
  "#75d4ff",
  "#ffcf66",
  "#d7a5ff",
  "#7fe3b0",
  "#ff9db6",
  "#a9baff",
];
const classColor = (id: number) => palette[id % palette.length];
let lastClassLabel = "";
function chooseClass(id: number) {
  activeClass.value = id;
  lastClassLabel = classes.value[id] ?? "";
}
function selectBox(index: number) {
  selected.value = index;
  tool.value = "edit";
}
function setTool(mode: "draw" | "edit") {
  if (start) return;
  tool.value = mode;
  selected.value = -1;
}
function changeZoom(delta: number) {
  zoom.value = Math.max(
    0.5,
    Math.min(3, Math.round((zoom.value + delta) * 100) / 100),
  );
}
const width = computed(() => asset.value?.width ?? 416),
  height = computed(() => asset.value?.height ?? 416);
const draftTime = computed(() =>
  draft.value ? new Date(draft.value.savedAt).toLocaleString() : "",
);
type Handle = "nw" | "ne" | "sw" | "se";
let start: {
  x: number;
  y: number;
  index: number;
  mode: "draw" | "move" | "resize";
  handle?: Handle;
  original: DetectionBox | null;
} | null = null;
let url = "";
function clone(items: DetectionBox[]) {
  return items.map((b) => ({ ...b }));
}
function snapshot() {
  history.value = [...history.value.slice(-49), clone(boxes.value)];
  future.value = [];
}
function undo() {
  if (locked.value || start) return;
  const previous = history.value.pop();
  if (!previous) return;
  future.value = [...future.value, clone(boxes.value)];
  boxes.value = previous;
  selected.value = -1;
}
function redo() {
  if (locked.value || start) return;
  const next = future.value.pop();
  if (!next) return;
  history.value = [...history.value, clone(boxes.value)];
  boxes.value = next;
  selected.value = -1;
}
function readDraft() {
  try {
    const raw = localStorage.getItem(`vision.annotation.${props.sample.id}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as
      | DetectionBox[]
      | {
          boxes?: DetectionBox[];
          savedAt?: number;
          baseVersion?: number | null;
          noObject?: boolean;
        };
    if (Array.isArray(parsed))
      return {
        boxes: parsed,
        savedAt: 0,
        baseVersion: null,
        noObject: false,
      };
    if (!Array.isArray(parsed.boxes)) return null;
    return {
      boxes: parsed.boxes,
      savedAt: Number(parsed.savedAt) || 0,
      baseVersion:
        typeof parsed.baseVersion === "number" ? parsed.baseVersion : null,
      noObject: parsed.noObject === true,
    };
  } catch {
    return null;
  }
}
watch(
  () => [props.sample.id, props.sample.plan?.id],
  async () => {
    const sampleId = props.sample.id;
    loadingSample.value = true;
    image.value = "";
    imageError.value = false;
    cursor.value = null;
    savedLocal.value = false;
    start = null;
    history.value = [];
    future.value = [];
    const annotation = props.sample.annotations[0];
    const serverBoxes = annotation?.boxes ? clone(annotation.boxes) : [];
    const local = readDraft();
    draft.value = local;
    boxes.value = serverBoxes;
    noObject.value = annotation?.status === "COMPLETE" && !serverBoxes.length;
    draftApplied.value = false;
    discarding.value = false;
    // 没有服务器标注时，本机草稿是唯一可用数据；有服务器标注时默认以服务器为准。
    if (!annotation && local) {
      boxes.value = clone(local.boxes);
      noObject.value = local.noObject;
      draftApplied.value = true;
      savedLocal.value = true;
    }
    selected.value = -1;
    activeClass.value = Math.max(0, classes.value.indexOf(lastClassLabel));
    tool.value = "draw";
    if (asset.value) {
      try {
        if (url) URL.revokeObjectURL(url);
        const content = await blob(`/assets/${asset.value.id}/content`);
        if (sampleId !== props.sample.id) return;
        url = URL.createObjectURL(content);
        image.value = url;
      } catch (e) {
        if (sampleId !== props.sample.id) return;
        imageError.value = true;
        notices.error(e);
      }
    }
    await nextTick();
    if (sampleId === props.sample.id) loadingSample.value = false;
  },
  { immediate: true },
);
watch(
  () => boxes.value.length,
  (count) => {
    if (count) noObject.value = false;
  },
);
watch(
  [boxes, noObject],
  () => {
    if (loadingSample.value || discarding.value) return;
    try {
      localStorage.setItem(
        `vision.annotation.${props.sample.id}`,
        JSON.stringify({
          boxes: boxes.value,
          savedAt: Date.now(),
          baseVersion: props.sample.annotations[0]?.version ?? null,
          noObject: noObject.value,
        }),
      );
      savedLocal.value = true;
    } catch {
      // 本地存储不可用时不影响服务器保存。
    }
  },
  { deep: true },
);
function restoreDraft() {
  if (!draft.value) return;
  boxes.value = clone(draft.value.boxes);
  noObject.value = draft.value.noObject;
  draft.value = null;
  draftApplied.value = true;
  savedLocal.value = true;
}
function discardDraft() {
  discarding.value = true;
  localStorage.removeItem(`vision.annotation.${props.sample.id}`);
  if (draftApplied.value) {
    boxes.value = clone(props.sample.annotations[0]?.boxes ?? []);
    selected.value = -1;
    noObject.value = false;
  }
  draftApplied.value = false;
  draft.value = null;
  savedLocal.value = false;
  void nextTick(() => {
    discarding.value = false;
  });
}
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
  if (!image.value || locked.value || e.button !== 0 || !canAnnotate.value)
    return;
  e.preventDefault();
  const p = coords(e),
    target = e.target as SVGElement,
    index = Number(target.dataset.index ?? -1),
    handle = target.dataset.handle as Handle | undefined;
  (e.currentTarget as Element).setPointerCapture(e.pointerId);
  if (tool.value === "edit" && index >= 0 && handle) {
    selected.value = index;
    snapshot();
    start = {
      ...p,
      index,
      mode: "resize",
      handle,
      original: { ...boxes.value[index]! },
    };
    return;
  }
  if (tool.value === "edit" && index >= 0 && !e.altKey) {
    selected.value = index;
    snapshot();
    start = {
      ...p,
      index,
      mode: "move",
      original: { ...boxes.value[index]! },
    };
    return;
  }
  if (tool.value === "edit" && !e.altKey) {
    selected.value = -1;
    return;
  }
  // 画框模式下始终创建新框，可直接在已有目标内标注重叠目标。
  snapshot();
  const box: DetectionBox = {
    classId: activeClass.value,
    label: classes.value[activeClass.value]!,
    confidence: 1,
    x1: p.x,
    y1: p.y,
    x2: p.x,
    y2: p.y,
  };
  boxes.value.push(box);
  selected.value = boxes.value.length - 1;
  start = { ...p, index: selected.value, mode: "draw", original: null };
}
function move(e: PointerEvent) {
  cursor.value = coords(e);
  if (!start) return;
  const p = coords(e),
    b = boxes.value[start.index]!,
    o = start.original;
  if (start.mode === "draw") {
    b.x1 = Math.min(start.x, p.x);
    b.y1 = Math.min(start.y, p.y);
    b.x2 = Math.max(start.x, p.x);
    b.y2 = Math.max(start.y, p.y);
  } else if (start.mode === "resize" && o) {
    if (start.handle === "nw" || start.handle === "sw")
      b.x1 = Math.max(0, Math.min(p.x, o.x2 - 1));
    if (start.handle === "ne" || start.handle === "se")
      b.x2 = Math.min(width.value, Math.max(p.x, o.x1 + 1));
    if (start.handle === "nw" || start.handle === "ne")
      b.y1 = Math.max(0, Math.min(p.y, o.y2 - 1));
    if (start.handle === "sw" || start.handle === "se")
      b.y2 = Math.min(height.value, Math.max(p.y, o.y1 + 1));
  } else if (o) {
    const w = o.x2 - o.x1,
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
    if (b && (b.x2 - b.x1 < 2 || b.y2 - b.y1 < 2)) {
      boxes.value.splice(start.index, 1);
      selected.value = -1;
    }
  }
  start = null;
}
function cancelDrag() {
  if (!start) return;
  const previous = history.value.pop();
  if (previous) boxes.value = previous;
  start = null;
  selected.value = -1;
}
function remove() {
  if (locked.value || start || selected.value < 0) return;
  snapshot();
  boxes.value.splice(selected.value, 1);
  selected.value = -1;
}
function setBoxClass(id: number) {
  if (locked.value || start || selected.value < 0 || !classes.value[id]) return;
  snapshot();
  const b = boxes.value[selected.value]!;
  b.classId = id;
  b.label = classes.value[id]!;
  chooseClass(id);
}
function nudge(dx: number, dy: number) {
  if (locked.value || start || selected.value < 0) return;
  snapshot();
  const b = boxes.value[selected.value]!;
  const w = b.x2 - b.x1,
    h = b.y2 - b.y1;
  b.x1 = Math.max(0, Math.min(width.value - w, b.x1 + dx));
  b.y1 = Math.max(0, Math.min(height.value - h, b.y1 + dy));
  b.x2 = b.x1 + w;
  b.y2 = b.y1 + h;
}
async function save(status: "DRAFT" | "COMPLETE", next = false) {
  if (locked.value || start || !image.value || !canAnnotate.value) return;
  if (status === "COMPLETE" && !boxes.value.length && !noObject.value) {
    notices.add("请框选目标，或点击“图中无目标”", true);
    return;
  }
  if (
    boxes.value.some(
      (box) => !Number.isInteger(box.classId) || !classes.value[box.classId],
    )
  ) {
    notices.add("请选择当前方案中的对象类别", true);
    return;
  }
  busy.value = true;
  try {
    await post(`/samples/${props.sample.id}/annotations`, {
      boxes: boxes.value.map(({ classId, confidence, x1, y1, x2, y2 }) => ({
        classId,
        label: classes.value[classId]!,
        confidence,
        x1,
        y1,
        x2,
        y2,
      })),
      status,
    });
    localStorage.removeItem(`vision.annotation.${props.sample.id}`);
    draft.value = null;
    draftApplied.value = false;
    savedLocal.value = false;
    notices.add(status === "COMPLETE" ? "标注已完成" : "草稿已保存");
    emit("saved", next);
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
function markNoObject() {
  if (locked.value || start || !image.value) return;
  if (boxes.value.length && !confirm("当前有标注框，确认标记为“图中无目标”？"))
    return;
  snapshot();
  boxes.value = [];
  selected.value = -1;
  noObject.value = true;
  void save("COMPLETE", true);
}
function key(e: KeyboardEvent) {
  if (
    (e.target as HTMLElement).closest(
      "input, textarea, select, [contenteditable=true]",
    )
  )
    return;
  if (locked.value) return;
  if (e.key === "Escape") {
    e.preventDefault();
    cancelDrag();
    selected.value = -1;
    return;
  }
  if (start) return;
  if (!e.ctrlKey && !e.metaKey && !e.altKey) {
    if (e.key.toLowerCase() === "w") setTool("draw");
    if (e.key.toLowerCase() === "v") setTool("edit");
    if (e.key.toLowerCase() === "n") emit("skip");
  }
  if (e.key === "Delete" || e.key === "Backspace") {
    e.preventDefault();
    remove();
  }
  if (
    !e.ctrlKey &&
    !e.metaKey &&
    /^[1-6]$/.test(e.key) &&
    classes.value[Number(e.key) - 1]
  ) {
    const id = Number(e.key) - 1;
    if (tool.value === "edit" && selected.value >= 0) setBoxClass(id);
    else chooseClass(id);
  }
  const step = e.shiftKey ? 10 : 1;
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    nudge(-step, 0);
  }
  if (e.key === "ArrowRight") {
    e.preventDefault();
    nudge(step, 0);
  }
  if (e.key === "ArrowUp") {
    e.preventDefault();
    nudge(0, -step);
  }
  if (e.key === "ArrowDown") {
    e.preventDefault();
    nudge(0, step);
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    e.preventDefault();
    if (e.shiftKey) redo();
    else undo();
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
    e.preventDefault();
    redo();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    void save("COMPLETE", true);
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
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
    <div class="annotation-topbar">
      <span v-if="position && total" class="mono"
        >第 {{ position }} / {{ total }} 张</span
      ><span v-if="sample.plan"
        >{{ sample.plan.rules.product }} · {{ sample.plan.name }}</span
      ><button :disabled="locked" @click="emit('discard')">弃用图片</button
      ><span v-if="savedLocal" class="tag ok">本机草稿已保存</span>
      <button
        class="right"
        :disabled="locked"
        @click="emit('skip')"
        title="保留本机草稿并查看下一张（N）"
      >
        跳过 / 下一张 <kbd>N</kbd>
      </button>
      <button :aria-expanded="showHelp" @click="showHelp = !showHelp">
        快捷键
      </button>
    </div>
    <div v-if="!canAnnotate" class="annotation-blocked">
      此样本未关联检查方案，无法标注。请先在采样任务中关联方案。
    </div>
    <template v-else>
      <div class="annotation-classes">
        <span>新框类别</span>
        <button
          v-for="(label, id) in classes"
          :key="id"
          :class="{ active: activeClass === id }"
          :aria-pressed="activeClass === id"
          :disabled="locked"
          :style="{ '--class-color': classColor(id) }"
          @click="
            chooseClass(id);
            setTool('draw');
          "
        >
          <b>{{ id + 1 }}</b> {{ label }}
        </button>
      </div>
      <div class="annotation-tools">
        <div class="segmented" role="group" aria-label="画框工具">
          <button
            :disabled="locked"
            :aria-pressed="tool === 'draw'"
            :class="{ active: tool === 'draw' }"
            @click="setTool('draw')"
          >
            画框 <kbd>W</kbd>
          </button>
          <button
            :disabled="locked"
            :aria-pressed="tool === 'edit'"
            :class="{ active: tool === 'edit' }"
            @click="setTool('edit')"
          >
            调整 <kbd>V</kbd>
          </button>
        </div>
        <span class="tool-hint">{{
          tool === "draw"
            ? `拖动绘制「${classes[activeClass]}」，可直接画重叠框`
            : "点击选框，拖动移动；拖动四角调整大小"
        }}</span>
        <button
          :disabled="locked || !history.length"
          @click="undo"
          title="撤销（Ctrl+Z）"
        >
          撤销
        </button>
        <button
          :disabled="locked || !future.length"
          @click="redo"
          title="重做（Ctrl+Shift+Z）"
        >
          重做
        </button>
        <div class="zoom-tools">
          <button
            aria-label="缩小图像"
            :disabled="zoom <= 0.5"
            @click="changeZoom(-0.25)"
          >
            −</button
          ><button title="适应画布" @click="zoom = 1">
            {{ Math.round(zoom * 100) }}% · 适应</button
          ><button
            aria-label="放大图像"
            :disabled="zoom >= 3"
            @click="changeZoom(0.25)"
          >
            ＋
          </button>
        </div>
      </div>
      <div v-if="draft" class="draft-notice">
        <span
          >{{ draftApplied ? "已恢复本机草稿" : "发现本机草稿" }}（{{
            draftTime || "时间未知"
          }}）</span
        >
        <button v-if="!draftApplied" :disabled="locked" @click="restoreDraft">
          恢复草稿
        </button>
        <button :disabled="locked" @click="discardDraft">丢弃</button>
      </div>
      <div class="annotation-canvas-scroll">
        <p v-if="loadingSample" class="canvas-message" role="status">
          正在加载图片…
        </p>
        <p v-else-if="imageError || !image" class="canvas-message" role="alert">
          预览图不可用，请关闭后重试，或等待图片处理完成。
        </p>
        <div
          v-else
          class="annotation-stage"
          :class="{ 'edit-mode': tool === 'edit' }"
          :style="{
            width: `${zoom * 100}%`,
            maxWidth: `calc((var(--annotation-available) - 50px) * ${(zoom * width) / height})`,
            aspectRatio: `${width} / ${height}`,
          }"
        >
          <img :src="image" alt="待标注图像" draggable="false" /><svg
            aria-label="标注画布"
            :viewBox="`0 0 ${width} ${height}`"
            @pointerdown="down"
            @pointermove="move"
            @pointerup="up"
            @pointercancel="cancelDrag"
            @lostpointercapture="up"
            @pointerleave="cursor = null"
          >
            <g
              v-if="cursor && tool === 'draw'"
              class="crosshair"
              aria-hidden="true"
            >
              <line :x1="cursor.x" y1="0" :x2="cursor.x" :y2="height" />
              <line x1="0" :y1="cursor.y" :x2="width" :y2="cursor.y" />
            </g>
            <g v-for="(b, i) in boxes" :key="i">
              <rect
                :data-index="i"
                :x="b.x1"
                :y="b.y1"
                :width="b.x2 - b.x1"
                :height="b.y2 - b.y1"
                :style="{
                  stroke: classColor(b.classId),
                  fill: classColor(b.classId) + (i === selected ? '24' : '0d'),
                }"
                :class="{ 'selected-box': i === selected }"
              />
              <text
                :data-index="i"
                :x="b.x1 + 3"
                :y="Math.max(15, b.y1 - 5)"
                :style="{ fill: classColor(b.classId) }"
              >
                {{ i + 1 }} · {{ displayName(b.label) }}
              </text>
              <template v-if="i === selected && tool === 'edit'">
                <circle
                  v-for="handle in ['nw', 'ne', 'sw', 'se'] as Handle[]"
                  :key="handle"
                  :data-index="i"
                  :data-handle="handle"
                  :cx="handle.includes('w') ? b.x1 : b.x2"
                  :cy="handle.includes('n') ? b.y1 : b.y2"
                  r="6"
                  fill="white"
                  :stroke="classColor(b.classId)"
                  stroke-width="2"
                  :style="{
                    cursor: ['nw', 'se'].includes(handle)
                      ? 'nwse-resize'
                      : 'nesw-resize',
                  }"
                />
              </template>
            </g>
          </svg>
        </div>
      </div>
      <aside class="annotation-inspector">
        <div class="annotation-save-actions">
          <button
            class="primary"
            @click="save('COMPLETE', true)"
            :disabled="locked || !image || (!boxes.length && !noObject)"
          >
            {{ busy ? "正在保存…" : "完成并下一张" }} <kbd>Ctrl ↵</kbd>
          </button>
          <div class="secondary-save">
            <button :disabled="locked || !image" @click="save('DRAFT')">
              保存草稿</button
            ><button
              :disabled="locked || !image || (!boxes.length && !noObject)"
              @click="save('COMPLETE')"
            >
              仅完成当前张
            </button>
          </div>
          <button
            class="no-object"
            :disabled="locked || !image"
            @click="markNoObject"
          >
            图中无目标 · 完成并下一张
          </button>
        </div>
        <h3>
          标注对象 <span class="mono">{{ boxes.length }}</span>
        </h3>
        <div v-if="selected >= 0" class="annotation-selected-class">
          <span>选中框类别</span>
          <button
            v-for="(label, id) in classes"
            :key="id"
            :class="{ active: boxes[selected]?.classId === id }"
            :disabled="locked"
            @click="setBoxClass(id)"
          >
            {{ label }}
          </button>
          <button class="danger" :disabled="locked" @click="remove">
            删除框
          </button>
        </div>
        <div
          v-for="(b, i) in boxes"
          :key="i"
          class="annotation-object"
          :class="{ active: selected === i }"
        >
          <button
            :disabled="locked"
            @click="selectBox(i)"
            :aria-pressed="selected === i"
            :style="{ borderLeft: `3px solid ${classColor(b.classId)}` }"
          >
            {{ i + 1 }} · {{ classes[b.classId] ?? "请选择有效类别"
            }}<small
              >{{ Math.round(b.x2 - b.x1) }} ×
              {{ Math.round(b.y2 - b.y1) }} px</small
            ></button
          ><button
            :disabled="locked"
            @click="
              selected = i;
              remove();
            "
            :aria-label="`删除第${i + 1}个框`"
          >
            删除
          </button>
        </div>
        <p v-if="!boxes.length" class="note">
          先选类别，再在图片上拖动绘制框。需要移动或缩放已有框时，点击“调整”或右侧对象。
        </p>
        <details v-if="showHelp" open class="annotation-help">
          <summary>快捷键</summary>
          <p>
            W 画框 · V 调整 · 1–6 选类别（调整时修改选中框）<br />
            Delete 删除 · Ctrl+Z 撤销 · Ctrl+Shift+Z 重做<br />
            方向键微调（Shift 加快）· Esc 取消当前操作<br />
            N 跳过 · Ctrl+S 保存草稿 · Ctrl+Enter 完成并下一张
          </p>
        </details>
      </aside>
    </template>
  </div>
</template>
<style scoped>
.annotation-workspace {
  align-content: start;
}
@media (min-width: 761px) {
  .annotation-workspace {
    --annotation-available: max(300px, calc(100dvh - 410px));
  }
  .annotation-canvas-scroll,
  .annotation-inspector {
    max-height: var(--annotation-available);
  }
}
.annotation-topbar {
  flex-wrap: wrap;
}
.annotation-tools {
  grid-column: 1/-1;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  background: var(--surface);
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
}
.annotation-tools button {
  padding: 7px 10px;
  font-size: 12px;
}
.tool-hint {
  font-size: 12px;
  color: var(--muted);
  flex: 1;
}
.zoom-tools {
  display: flex;
  gap: 4px;
}
kbd {
  font: inherit;
  opacity: 0.7;
  margin-left: 5px;
}
.annotation-canvas-scroll {
  background: #111820;
  min-height: 280px;
  align-items: center;
}
.canvas-message {
  margin: auto;
  color: #d9e3ec;
  padding: 30px;
  font-size: 13px;
}
.annotation-stage {
  user-select: none;
}
.annotation-stage img {
  height: 100%;
  pointer-events: none;
}
.annotation-stage svg {
  touch-action: none;
}
.annotation-stage.edit-mode svg {
  cursor: default;
}
.annotation-stage.edit-mode rect {
  cursor: move;
}
.annotation-stage rect {
  vector-effect: non-scaling-stroke;
}
.annotation-stage rect.selected-box {
  stroke-width: 3;
}
.annotation-stage text {
  font-weight: 600;
  paint-order: stroke;
  stroke: #101820;
  stroke-width: 3px;
  stroke-linejoin: round;
  pointer-events: none;
}
.crosshair {
  pointer-events: none;
  stroke: #fff;
  stroke-width: 1;
  stroke-dasharray: 5 4;
  opacity: 0.65;
}
.crosshair line {
  vector-effect: non-scaling-stroke;
}
.annotation-classes button {
  border-left: 4px solid var(--class-color);
}
.annotation-classes button.active {
  background: var(--surface-2);
  box-shadow: inset 0 -2px var(--forest);
  font-weight: 700;
}
.secondary-save {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.annotation-save-actions {
  margin: 0 0 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--line);
}
.annotation-object small {
  display: block;
  color: var(--muted);
  margin-top: 4px;
  font-size: 11px;
}
@media (max-width: 760px) {
  .tool-hint {
    flex-basis: 100%;
    order: 1;
  }
  .annotation-canvas-scroll {
    min-height: 220px;
    padding: 12px;
  }
  .annotation-inspector {
    max-height: none;
  }
}
.annotation-topbar {
  grid-column: 1/-1;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--muted);
  margin: 0;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line-strong);
  background: var(--surface);
}
.annotation-classes {
  grid-column: 1/-1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
  font-size: 12px;
  color: var(--muted);
}
.annotation-selected-class {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--muted);
}
.annotation-classes button,
.annotation-selected-class button {
  padding: 7px 10px;
  font-size: 12px;
}
.annotation-classes button.active,
.annotation-selected-class button.active {
  border-color: var(--forest);
  color: var(--forest);
}
.annotation-blocked,
.draft-notice {
  grid-column: 1/-1;
  padding: 14px;
  margin-bottom: 14px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  font-size: 13px;
}
.draft-notice {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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
.annotation-save-actions {
  display: grid;
  gap: 8px;
  margin-top: 0;
}
.annotation-help {
  margin-top: 16px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.8;
}
</style>
