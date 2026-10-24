<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { chinese, displayName, terminalActivity } from "@vision/shared";
import type { Inspection } from "@vision/contracts";
import { api, errorText, post } from "../api";
import { useDeviceStore } from "../stores/devices";
import Icon from "../components/Icon.vue";

const devices = useDeviceStore();
const root = ref<HTMLElement | null>(null);
const now = ref(Date.now()),
  message = ref("");
const full = ref(false),
  boxesVisible = ref(true),
  records = ref<Inspection[]>([]);
const device = computed(() => devices.current);
const state = computed(() => device.value?.terminal?.state);
const online = computed(() => device.value?.connectionState === "ONLINE");
const active = computed(() => online.value && state.value?.production);
const preview = computed(() => {
  const p = device.value && devices.previews[device.value.id];
  return online.value && p && now.value - Date.parse(p.receivedAt) < 4000
    ? p
    : null;
});
const activity = computed(() =>
  terminalActivity(state.value ?? null, online.value),
);
const counts = computed(() =>
  state.value?.productionRunId ? state.value.runCounts : state.value?.counts,
);
const total = computed(() =>
  counts.value ? Object.values(counts.value).reduce((a, b) => a + b, 0) : null,
);
const passRate = computed(() => {
  const c = counts.value;
  return c && c.PASS + c.FAIL ? (c.PASS / (c.PASS + c.FAIL)) * 100 : null;
});
const fps = computed(() =>
  online.value && state.value?.fresh
    ? (state.value.fps ?? device.value?.telemetry?.fps ?? null)
    : null,
);
const latency = computed(() =>
  online.value && device.value?.telemetry?.inferenceUs != null
    ? device.value.telemetry.inferenceUs / 1000
    : null,
);
const result = computed(() => state.value?.last);
const lastLabel = computed(() =>
  result.value ? chinese(result.value.result) : "等待第一件",
);
const resultClass = computed(() =>
  result.value?.result === "PASS"
    ? "pass"
    : result.value?.result === "FAIL"
      ? "fail"
      : "neutral",
);
const product = computed(
  () =>
    state.value?.product?.product ||
    state.value?.product?.name ||
    "尚未配置产品",
);
const level = computed(() => preview.value?.level);
/** 只有液位模型才有液位尺；瓶盖计数等产品不显示。 */
const liquidModel = computed(() =>
  (state.value?.model?.classes ?? []).includes("level_deviation"),
);
const timing = computed(() =>
  online.value && state.value?.fresh ? state.value.timing : null,
);
const stages = computed(() => [
  { label: "输入搬运", value: timing.value?.prepareMs },
  { label: "PL 卷积", value: timing.value?.convMs },
  { label: "张量提取", value: timing.value?.extractMs },
]);
const timingMax = computed(() =>
  Math.max(1, ...stages.value.map((s) => s.value ?? 0)),
);
const detections = computed(() => preview.value?.detections ?? []);
const confidence = computed(() =>
  detections.value.length
    ? Math.max(...detections.value.map((d) => d.confidence)) * 100
    : null,
);
const rules = computed(() => state.value?.product?.checks ?? []);
const memory = computed(() =>
  state.value?.memoryTotal
    ? (state.value.memoryUsed / state.value.memoryTotal) * 100
    : null,
);
const uptime = computed(() => {
  const seconds = state.value?.uptime;
  if (seconds == null) return "—";
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
});
const time = computed(() =>
  new Date(now.value).toLocaleTimeString("zh-CN", { hour12: false }),
);
const date = computed(() =>
  new Date(now.value)
    .toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    })
    .replaceAll("/", "."),
);
const clock = setInterval(() => {
  now.value = Date.now();
}, 1000);
async function loadRecords() {
  const id = device.value?.id;
  if (!id) {
    records.value = [];
    return;
  }
  try {
    const data = await api<{ items: Inspection[] }>(
      `/inspections?deviceId=${encodeURIComponent(id)}&realOnly=true&pageSize=100&sort=createdAt&order=desc`,
    );
    if (device.value?.id === id) records.value = data.items;
  } catch (e) {
    message.value = errorText(e);
  }
}
watch(
  () => device.value?.id,
  (id, old) => {
    if (old) devices.unwatchPreview(old);
    records.value = [];
    message.value = "";
    if (id) devices.watchPreview(id);
    void loadRecords();
  },
  { immediate: true },
);
watch(() => state.value?.last?.sequence, loadRecords);
async function fullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await root.value?.requestFullscreen();
  } catch {
    message.value = "浏览器未允许全屏，请使用 F11。";
  }
}
function onFull() {
  full.value = !!document.fullscreenElement;
}
document.addEventListener("fullscreenchange", onFull);
const ARM_S = 16.7258,
  PL_S = 0.06567,
  SPEEDUP = 254.7;
const lap = ref(0),
  cycles = ref(0);
let raf = 0,
  t0 = 0;
function tick(ts: number) {
  if (!t0) t0 = ts;
  const e = (ts - t0) / 1000;
  cycles.value = Math.floor(e / ARM_S);
  lap.value = e % ARM_S;
  raf = requestAnimationFrame(tick);
}
onMounted(() => {
  raf = requestAnimationFrame(tick);
});
const armPct = computed(() => (lap.value / ARM_S) * 100);
const plTotal = computed(() => Math.floor(lap.value / PL_S));
onBeforeUnmount(() => {
  cancelAnimationFrame(raf);
  clearInterval(clock);
  document.removeEventListener("fullscreenchange", onFull);
  if (device.value) devices.unwatchPreview(device.value.id);
});
const trend = computed(() => {
  const values = devices.history
    .slice(-40)
    .map((h) => h.fps)
    .filter((v): v is number => v != null && Number.isFinite(v));
  if (values.length < 2) return "";
  const max = Math.max(...values, 1),
    min = Math.min(...values, 0);
  return values
    .map(
      (v, i) =>
        `${(i / (values.length - 1)) * 240},${44 - ((v - min) / (max - min)) * 32}`,
    )
    .join(" ");
});
function tween(get: () => number | null) {
  const shown = ref<number | null>(get());
  let id = 0;
  watch(get, (to) => {
    cancelAnimationFrame(id);
    const from = shown.value;
    if (
      to == null ||
      from == null ||
      matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      shown.value = to;
      return;
    }
    const t0 = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / 700);
      shown.value = from + (to - from) * (1 - Math.pow(1 - k, 3));
      if (k < 1) id = requestAnimationFrame(step);
    };
    id = requestAnimationFrame(step);
  });
  onBeforeUnmount(() => cancelAnimationFrame(id));
  return shown;
}
const nTotal = tween(() => total.value);
const nPass = tween(() => counts.value?.PASS ?? null);
const nFail = tween(() => counts.value?.FAIL ?? null);
const nRate = tween(() => passRate.value);
const int = (v: number | null) => (v == null ? "—" : Math.round(v).toLocaleString());

// ── 计件口径：整件进入并离开画面、保存记录后才计一件；批次随开始/停止自动创建/关闭 ──
const scope = computed(() => (state.value?.productionRunId ? "本批" : "设备累计"));
const nBelt = tween(() => state.value?.beltCaps ?? null);
const resetting = ref(false);
async function resetCounts() {
  if (!device.value || resetting.value) return;
  resetting.value = true;
  try {
    await post(`/devices/${device.value.id}/commands`, {
      type: "RESET_COUNTS",
    });
    await devices.snapshot();
    message.value = "计数已清零，已重新开始检测";
  } catch (e) {
    message.value = errorText(e);
  } finally {
    resetting.value = false;
  }
}
const nCum = tween(() => state.value?.total ?? null);
const judged = computed(() =>
  counts.value ? counts.value.PASS + counts.value.FAIL : null,
);
const phases = [
  { key: "CLEARING", label: "清场" },
  { key: "WAITING", label: "等待产品" },
  { key: "INSPECTING", label: "多帧检查" },
  { key: "SAVING", label: "保存计件" },
];
const phaseIdx = computed(() =>
  state.value?.production
    ? phases.findIndex((p) => p.key === state.value?.passagePhase)
    : -1,
);

// ── 画布缩放：按 1920×1080 设计，整体缩放到窗口 ──
const W = 1920,
  H = 1080;
const k = ref(1),
  ox = ref(0),
  oy = ref(0);
let ro: ResizeObserver | null = null;
function fit() {
  const el = root.value;
  if (!el) return;
  const s = Math.min(el.clientWidth / W, el.clientHeight / H);
  k.value = s;
  ox.value = (el.clientWidth - W * s) / 2;
  oy.value = (el.clientHeight - H * s) / 2;
}
onMounted(() => {
  fit();
  ro = new ResizeObserver(fit);
  if (root.value) ro.observe(root.value);
});
onBeforeUnmount(() => ro?.disconnect());

// ── 方形视频上的标注 ──
const feedImg = ref<HTMLImageElement | null>(null);
const anns = computed(() => {
  const p = preview.value;
  if (!p) return [];
  const u = p.width / 224,
    fs = 7.5 * u,
    lh = fs * 2.3,
    gap = 10 * u;
  return detections.value.map((b, i) => {
    const text =
      `${displayName(b.label)} ${(b.confidence * 100).toFixed(0)}%` +
      (b.trackId != null ? ` #${b.trackId}` : "");
    let cw = 0;
    for (const ch of text) cw += ch.charCodeAt(0) > 255 ? fs : fs * 0.62;
    const lw = cw + fs * 1.4;
    const right = b.x2 + gap + lw <= p.width - 2 * u;
    const lx = right ? b.x2 + gap : Math.max(2 * u, b.x1 - gap - lw);
    const ly = Math.min(Math.max(b.y1, 2 * u), p.height - lh - 2 * u);
    const ax = right ? b.x2 : b.x1;
    return {
      key: b.trackId ?? i,
      b,
      text,
      u,
      fs,
      lx,
      ly,
      lw,
      lh,
      d: `M${ax},${b.y1}L${right ? lx : lx + lw},${ly + lh / 2}`,
    };
  });
});
const rowY = (r: number) => (r / 223) * (preview.value?.height ?? 0);

// ── 检测带：每出一个结论，截一张当前画面缩略图 ──
type Thumb = { seq: number; result: string; src: string | null };
const thumbs = ref<Thumb[]>([]);
watch(
  () => state.value?.last?.sequence,
  (seq) => {
    const last = state.value?.last;
    if (seq == null || !last) return;
    let src: string | null = null;
    try {
      const img = feedImg.value;
      if (img?.complete && img.naturalWidth) {
        const c = document.createElement("canvas");
        c.width = c.height = 120;
        const side = Math.min(img.naturalWidth, img.naturalHeight);
        c.getContext("2d")?.drawImage(
          img,
          (img.naturalWidth - side) / 2,
          (img.naturalHeight - side) / 2,
          side,
          side,
          0,
          0,
          120,
          120,
        );
        src = c.toDataURL("image/jpeg", 0.7);
      }
    } catch {
      src = null;
    }
    thumbs.value = [
      ...thumbs.value,
      { seq, result: last.result, src },
    ].slice(-24);
  },
);
watch(
  () => device.value?.id,
  () => {
    thumbs.value = [];
    confBins.value = Array(10).fill(0);
  },
);
const recentList = computed<Thumb[]>(() =>
  thumbs.value.length
    ? thumbs.value
    : [...records.value]
        .slice(0, 24)
        .reverse()
        .map((r, i) => ({ seq: i, result: r.result, src: null })),
);
const cells = computed(() => {
  const list = recentList.value;
  return [...Array(24 - list.length).fill(null), ...list] as (Thumb | null)[];
});
const recentStat = computed(() => {
  const list = [...recentList.value].reverse();
  let streak = 0;
  for (const t of list) {
    if (t.result !== "PASS") break;
    streak++;
  }
  return {
    pass: list.filter((t) => t.result === "PASS").length,
    fail: list.filter((t) => t.result === "FAIL").length,
    other: list.filter((t) => t.result !== "PASS" && t.result !== "FAIL").length,
    streak,
  };
});
const cls = (r: string) => (r === "PASS" ? "ok" : r === "FAIL" ? "bad" : "mid");

// ── 耗时瀑布 ──
const wf = computed(() => {
  const t = timing.value;
  const rows = [
    { label: "采集推理", v: t?.captureMs },
    { label: "输入搬运", v: t?.prepareMs },
    { label: "PL 卷积", v: t?.convMs, hot: true },
    { label: "张量提取", v: t?.extractMs },
    { label: "后处理", v: t?.postMs },
  ];
  const peak = Math.max(1, ...rows.map((r) => r.v ?? 0)) * 1.05;
  const max = [10, 20, 50, 100, 200, 500, 1000].find((s) => s >= peak) ?? peak;
  const X0 = 66,
    PW = 236;
  return {
    max,
    ticks: [0, 1, 2, 3, 4].map((i) => ({
      x: X0 + (i / 4) * PW,
      label: ((max * i) / 4).toFixed(max < 20 ? 1 : 0),
    })),
    rows: rows.map((r, i) => ({
      ...r,
      y: 12 + i * 34,
      x: X0,
      w: r.v == null ? 0 : Math.max(2, (r.v / max) * PW),
    })),
  };
});

// ── 延迟分布 + P50 / P99 ──
const hist = computed(() => {
  const vals = devices.history
    .map((h) => h.inferenceUs)
    .filter((v): v is number => v != null && Number.isFinite(v))
    .map((v) => v / 1000);
  if (vals.length < 8) return null;
  const s = [...vals].sort((a, b) => a - b);
  const q = (p: number) =>
    s[Math.min(s.length - 1, Math.floor(p * s.length))] ?? 0;
  const lo = s[0] ?? 0,
    span = (s[s.length - 1] ?? lo) - lo || 1,
    N = 12,
    bw = 26,
    HX = 14;
  const bins = Array(N).fill(0);
  vals.forEach((v) => {
    const i = Math.min(N - 1, Math.floor(((v - lo) / span) * N));
    bins[i] = (bins[i] ?? 0) + 1;
  });
  const mx = Math.max(...bins);
  const pos = (v: number) => HX + ((v - lo) / span) * N * bw;
  return {
    n: vals.length,
    bw,
    bars: bins.map((c, i) => ({ x: HX + i * bw, h: (c / mx) * 150 })),
    end: HX + N * bw,
    HX,
    p50: q(0.5),
    p99: q(0.99),
    x50: pos(q(0.5)),
    x99: pos(q(0.99)),
    ticks: [0, 0.25, 0.5, 0.75, 1].map((f) => ({
      x: HX + f * N * bw,
      label: (lo + f * span).toFixed(1),
    })),
  };
});

// ── 置信度分布（本次会话累计） ──
const confBins = ref<number[]>(Array(10).fill(0));
const confN = computed(() => confBins.value.reduce((a, b) => a + b, 0));
const confBars = computed(() => {
  const mx = Math.max(1, ...confBins.value);
  return confBins.value.map((c, i) => ({ x: i * 32, h: (c / mx) * 56 }));
});
watch(
  () => preview.value?.frameId,
  () => {
    for (const d of detections.value) {
      const i = Math.min(9, Math.max(0, Math.floor(d.confidence * 10)));
      confBins.value[i] = (confBins.value[i] ?? 0) + 1;
    }
  },
);
const gmacs = computed(() => (fps.value == null ? null : fps.value * 0.9775));

// ── 报告常量（hardware/camera/build/terminal 与 arm_vs_pl_20261022） ──
const resources = [
  { name: "DSP", used: 217, total: 220, text: "217/220" },
  { name: "LUT", used: 45299, total: 53200, text: "45.3k/53.2k" },
  { name: "BRAM", used: 112.5, total: 140, text: "112.5/140" },
  { name: "FF", used: 60859, total: 106400, text: "60.9k/106.4k" },
];
const armLayers = [
  [31, 3.163],
  [23, 2.528],
  [16, 1.897],
  [2, 1.634],
  [9, 1.63],
  [1, 1.25],
  [25, 1.144],
  [6, 0.55],
].map(([n = 0, s = 0], i) => ({
  name: `L${String(n).padStart(2, "0")}`,
  s,
  y: 6 + i * 24,
  w: (s / 3.163) * 230,
  hot: i === 0,
}));
// ── 多视图：纯展示，不含任何后台操作 ──
type View = "live" | "sys" | "stats";
const views: { key: View; label: string }[] = [
  { key: "live", label: "实时总览" },
  { key: "sys", label: "系统状态" },
  { key: "stats", label: "判定统计" },
];
const view = ref<View>("live");
const auto = ref(false);
const rotate = setInterval(() => {
  if (!auto.value) return;
  const i = views.findIndex((v) => v.key === view.value);
  view.value = views[(i + 1) % views.length]!.key;
}, 20000);
const samples = ref<{ cpu: number | null; mem: number | null }[]>([]);
const sampler = setInterval(() => {
  if (!state.value) return;
  samples.value = [
    ...samples.value,
    { cpu: state.value.cpuPercent, mem: memory.value },
  ].slice(-90);
}, 2000);
onBeforeUnmount(() => {
  clearInterval(rotate);
  clearInterval(sampler);
});
function line(vals: (number | null)[], max?: number, w = 400, h = 90) {
  const v = vals.filter((x): x is number => x != null && Number.isFinite(x));
  if (v.length < 2) return "";
  const top = max ?? (Math.max(...v) * 1.1 || 1);
  return v
    .map(
      (x, i) =>
        `${((i / (v.length - 1)) * w).toFixed(1)},${(h - 6 - (x / top) * (h - 12)).toFixed(1)}`,
    )
    .join(" ");
}
const cpuLine = computed(() => line(samples.value.map((s) => s.cpu), 100));
const memLine = computed(() => line(samples.value.map((s) => s.mem), 100));
const fpsLine = computed(() => line(devices.history.map((h) => h.fps)));
const latLine = computed(() =>
  line(devices.history.map((h) => (h.inferenceUs == null ? null : h.inferenceUs / 1000))),
);
const tele = computed(() => {
  const t = device.value?.telemetry;
  if (!t) return [];
  const rows: [string, number][] = [
    ["采集", t.captureUs],
    ["转换", t.conversionUs],
    ["推理", t.inferenceUs],
    ["传输", t.transferUs],
    ["周期", t.cycleUs],
  ];
  const mx = Math.max(1, ...rows.map((r) => r[1]));
  return rows.map(([label, us]) => ({ label, ms: us / 1000, pct: (us / mx) * 100 }));
});
const stat = computed(() => {
  const r = records.value;
  const c = { PASS: 0, FAIL: 0, other: 0 };
  for (const x of r) c[x.result === "PASS" ? "PASS" : x.result === "FAIL" ? "FAIL" : "other"]++;
  const conf = r.map((x) => x.confidence).filter((v): v is number => v != null);
  const bins: number[] = Array(10).fill(0);
  for (const v of conf) {
    const k = Math.min(9, Math.floor(v * 10));
    bins[k] = (bins[k] ?? 0) + 1;
  }
  const mx = Math.max(1, ...bins);
  const reasons = new Map<string, number>();
  for (const x of r)
    if (x.result !== "PASS") {
      const key = x.reason || "未记录";
      reasons.set(key, (reasons.get(key) ?? 0) + 1);
    }
  const top = [...reasons].sort((a, b) => b[1] - a[1]).slice(0, 5);
  return {
    n: r.length,
    c,
    pct: (v: number) => (r.length ? (v / r.length) * 100 : 0),
    bins: bins.map((v, i) => ({ x: i * 40, h: (v / mx) * 110 })),
    avg: conf.length ? conf.reduce((a, b) => a + b, 0) / conf.length : null,
    reasons: top.map(([text, n]) => ({ text, n, pct: (n / (top[0]?.[1] ?? 1)) * 100 })),
    latest: r.slice(0, 10),
  };
});
</script>


<template>
  <div ref="root" class="fit">
    <div
      class="sc"
      :class="resultClass"
      :style="{ transform: `translate(${ox}px, ${oy}px) scale(${k})` }"
    >
      <header class="top">
        <RouterLink to="/overview" class="brand" aria-label="返回运行概览"
          >视觉检测</RouterLink
        >
        <nav class="tabs" aria-label="展示视图">
          <button
            v-for="v in views"
            :key="v.key"
            :class="{ on: view === v.key }"
            @click="view = v.key"
          >
            {{ v.label }}
          </button>
        </nav>
        <span class="sp"></span>
        <span class="tag prod"
          >{{ product }} · {{ state?.model?.version || "尚未加载模型" }}</span
        >
        <span class="live" :class="{ up: online }"
          ><i></i>{{ online ? "终端在线" : "等待终端" }}</span
        >
        <select
          v-if="devices.devices.length > 1"
          v-model="devices.selected"
          class="sel"
          aria-label="选择演示设备"
        >
          <option v-for="d in devices.devices" :key="d.id" :value="d.id">
            {{ d.name }}
          </option>
        </select>
        <button
          v-if="view === 'live'"
          class="ico"
          :aria-pressed="boxesVisible"
          @click="boxesVisible = !boxesVisible"
        >
          标注
        </button>
        <button
          class="ico"
          :disabled="!online || resetting"
          @click="resetCounts"
        >
          清零重检
        </button>
        <button class="ico" :aria-pressed="auto" @click="auto = !auto">
          轮播
        </button>
        <span class="clk">{{ time }}</span>
        <button
          class="ico"
          :aria-label="full ? '退出全屏' : '进入全屏'"
          @click="fullscreen"
        >
          ⛶
        </button>
        <RouterLink class="ico" to="/workbench" aria-label="前往现场工作台"
          >⌂</RouterLink
        >
      </header>

      <main v-if="view === 'live'" class="main">
        <div class="lcol">
          <div class="vid" :class="{ 'no-ruler': !liquidModel }">
            <div class="sq">
              <template v-if="preview">
                <img
                  ref="feedImg"
                  :src="`data:image/jpeg;base64,${preview.jpeg}`"
                  alt="设备实时检测画面"
                  draggable="false"
                />
                <svg
                  class="ov"
                  :viewBox="`0 0 ${preview.width} ${preview.height}`"
                  preserveAspectRatio="xMidYMid slice"
                >
                  <g v-if="level && boxesVisible">
                    <rect
                      x="0"
                      :y="rowY(level.band[0])"
                      :width="preview.width"
                      :height="rowY(level.band[1]) - rowY(level.band[0])"
                      class="bandfill"
                    />
                    <line
                      v-if="level.row != null"
                      x1="0"
                      :x2="preview.width"
                      :y1="rowY(level.row)"
                      :y2="rowY(level.row)"
                      class="rowline"
                    />
                  </g>
                  <g v-if="boxesVisible">
                    <g v-for="a in anns" :key="a.key" class="ann">
                      <rect
                        class="bx"
                        :x="a.b.x1"
                        :y="a.b.y1"
                        :width="a.b.x2 - a.b.x1"
                        :height="a.b.y2 - a.b.y1"
                        :stroke-width="1.6 * a.u"
                      />
                      <path class="ld" :d="a.d" :stroke-width="0.8 * a.u" />
                      <g :transform="`translate(${a.lx},${a.ly})`">
                        <rect class="lb" :width="a.lw" :height="a.lh" />
                        <text
                          :x="a.fs * 0.7"
                          :y="a.lh / 2 + a.fs * 0.35"
                          :font-size="a.fs"
                        >
                          {{ a.text }}
                        </text>
                      </g>
                    </g>
                  </g>
                </svg>
              </template>
              <div v-else class="idle">
                <b>{{ online ? "正在建立实时视野" : "等待视频信号" }}</b>
                <p>
                  {{
                    online
                      ? "画面接收后自动显示"
                      : "连接边缘终端，开启视觉检测"
                  }}
                </p>
              </div>
              <span class="vtag">{{
                preview
                  ? `FRAME ${String(preview.frameId).padStart(6, "0")} · ${preview.width}×${preview.height} · 目标 ${detections.length}（不等于件数）`
                  : "NO SIGNAL"
              }}</span>
              <Transition name="stamp">
                <div
                  v-if="result"
                  :key="result.sequence"
                  class="stamp"
                  :class="resultClass"
                >
                  {{ lastLabel }}
                </div>
              </Transition>
            </div>
            <div v-if="liquidModel" class="ruler">
              <template v-if="level">
                <template v-for="n in 12" :key="n">
                  <i class="tk" :style="{ top: `${((n - 1) * 20 / 223) * 100}%` }"></i>
                  <span class="rl" :style="{ top: `${((n - 1) * 20 / 223) * 100}%` }">{{
                    (n - 1) * 20
                  }}</span>
                </template>
                <div
                  class="band"
                  :style="{
                    top: `${(level.band[0] / 223) * 100}%`,
                    height: `${((level.band[1] - level.band[0]) / 223) * 100}%`,
                  }"
                ></div>
                <div
                  v-if="level.row != null"
                  class="ptr"
                  :style="{ top: `${(level.row / 223) * 100}%` }"
                >
                  <b>{{ level.row.toFixed(1) }}</b>
                </div>
                <span v-else class="miss">未测到液面</span>
              </template>
              <span v-else class="miss">液位尺</span>
            </div>
          </div>

          <div class="p strip-card">
            <div class="eb">
              <span>检测带 · 最近 24 件</span>
              <ol class="phases" aria-label="单件检测流程">
                <li
                  v-for="(p, i) in phases"
                  :key="p.key"
                  :class="{ on: i === phaseIdx, done: phaseIdx >= 0 && i < phaseIdx }"
                >
                  {{ p.label }}
                </li>
              </ol>
            </div>
            <p class="hint">{{ activity.hint }}</p>
            <TransitionGroup name="cell" tag="div" class="strip">
              <i
                v-for="(c, n) in cells"
                :key="c ? `s${c.seq}` : `e${n}`"
                :class="c ? cls(c.result) : 'e'"
                :title="c ? chinese(c.result) : ''"
                :style="c?.src ? { backgroundImage: `url(${c.src})` } : undefined"
              ></i>
            </TransitionGroup>
            <div class="kv">
              <div class="g"><span>近 24 件合格</span><b>{{ recentStat.pass }}</b></div>
              <div class="nb"><span>近 24 件不合格</span><b>{{ recentStat.fail }}</b></div>
              <div><span>连续合格</span><b>{{ recentStat.streak }}</b></div>
              <div><span>复核 / 错误</span><b>{{ recentStat.other }}</b></div>
            </div>
          </div>
        </div>

        <div class="rcol">
          <div class="p hero">
            <div>
              <div class="eb">
                <span>PL 加速比</span><span class="badge b-meas">实测</span>
              </div>
              <div class="big">{{ SPEEDUP.toFixed(0) }}<small>×</small></div>
              <p>
                同一模型 · 同一块板 · 单帧推理<br />978 MMAC · 输出与 Python
                参考 0 差异
              </p>
            </div>
            <div class="tl">
              <div class="lane">
                <div><b>ARM Cortex-A9</b><small>单核 标量 INT8</small></div>
                <div class="trk">
                  <div class="fillA" :style="{ width: `${armPct}%` }"></div>
                </div>
                <div class="t">16.73<small> s</small></div>
              </div>
              <div class="lane">
                <div><b>PL 加速器</b><small>33 层全部在 PL</small></div>
                <div class="trk pl"></div>
                <div class="t pt">65.7<small> ms</small></div>
              </div>
              <div class="axis">
                <span>0</span><span>4 s</span><span>8 s</span><span>12 s</span
                ><span>16.7 s</span>
              </div>
              <div class="cnt">
                <span>在 ARM 完成 1 帧的时间里，PL 已完成</span
                ><b>{{ plTotal }} 帧</b>
              </div>
            </div>
          </div>

          <div class="row r2">
            <div class="p">
              <div class="eb">
                <span>计件 · {{ scope }}</span
                ><span class="badge b-live">实时</span>
              </div>
              <div :key="total ?? 'x'" class="tally">
                {{ int(nTotal) }}<em>件</em>
              </div>
              <div class="rate-line">
                合格率
                <b>{{ nRate == null ? "—" : nRate.toFixed(1) }}%</b>
                <small>已判定 {{ judged ?? "—" }} 件</small>
              </div>
              <div class="rate-line">
                传送带瓶盖
                <b>{{ int(nBelt) }}</b>
                <small>本次检测累计经过的瓶盖数</small>
              </div>
              <div class="bar">
                <i :style="{ width: `${nRate ?? 0}%` }"></i>
              </div>
              <div class="kv">
                <div class="g"><span>合格</span><b>{{ int(nPass) }}</b></div>
                <div class="nb"><span>不合格</span><b>{{ int(nFail) }}</b></div>
                <div><span>待复核</span><b>{{ counts?.REVIEW ?? "—" }}</b></div>
                <div><span>错误</span><b>{{ counts?.ERROR ?? "—" }}</b></div>
              </div>
              <p class="rule">
                合格率 = 合格 ÷（合格 + 不合格），复核与错误不计入 · 设备累计
                {{ int(nCum) }} 件 · 待上传 {{ state?.pendingSync ?? "—" }} 条
              </p>
            </div>
            <div class="p">
              <div class="eb">
                <span>单帧耗时 (ms)</span><span class="badge b-live">实时</span>
              </div>
              <svg class="ch" width="100%" height="235" viewBox="0 0 330 235">
                <g v-for="t in wf.ticks" :key="t.x">
                  <path :d="`M${t.x} 8V190`" stroke="#c9c6bf" />
                  <text :x="t.x" y="208" text-anchor="middle">{{ t.label }}</text>
                </g>
                <g v-for="r in wf.rows" :key="r.label">
                  <text x="0" :y="r.y + 15">{{ r.label }}</text>
                  <rect
                    class="wbar"
                    :class="{ hot: r.hot }"
                    :x="r.x"
                    :y="r.y"
                    :width="r.w"
                    height="22"
                  />
                  <text
                    v-if="r.v != null"
                    :x="r.x + r.w + 4"
                    :y="r.y + 16"
                    class="val"
                  >
                    {{ r.v.toFixed(1) }}
                  </text>
                </g>
                <text x="330" y="226" text-anchor="end">
                  预处理与卷积并行，阶段不可相加
                </text>
              </svg>
            </div>
            <div class="p">
              <div class="eb">
                <span>推理延迟分布 · n={{ hist?.n ?? 0 }}</span
                ><span class="badge b-live">实时</span>
              </div>
              <svg
                v-if="hist"
                class="ch"
                width="100%"
                height="235"
                viewBox="0 0 330 235"
              >
                <rect
                  v-for="(b, i) in hist.bars"
                  :key="i"
                  :x="b.x"
                  :y="190 - b.h"
                  :width="hist.bw - 3"
                  :height="b.h"
                  fill="#151715"
                />
                <path :d="`M${hist.HX} 190H${hist.end}`" stroke="#151715" />
                <path :d="`M${hist.x50} 22V190`" stroke="#1f4d3a" stroke-width="2" />
                <text :x="hist.x50 + 4" y="16" class="val ok">
                  P50 {{ hist.p50.toFixed(1) }}
                </text>
                <path
                  :d="`M${hist.x99} 22V190`"
                  stroke="#b8381c"
                  stroke-width="2"
                  stroke-dasharray="4 3"
                />
                <text :x="hist.x99 - 4" y="32" text-anchor="end" class="val bad">
                  P99 {{ hist.p99.toFixed(1) }}
                </text>
                <text v-for="t in hist.ticks" :key="t.x" :x="t.x" y="208">
                  {{ t.label }}
                </text>
                <text :x="hist.end" y="226" text-anchor="end">ms</text>
              </svg>
              <div v-else class="wait">等待足够的遥测样本（≥ 8 帧）</div>
            </div>
          </div>

          <div class="row r3">
            <div class="p">
              <div class="eb">
                <span>PL 资源 · Zynq-7020</span
                ><span class="badge b-meas">实测</span>
              </div>
              <div class="res">
                <div v-for="r in resources" :key="r.name">
                  <span>{{ r.name }}</span>
                  <div class="bar">
                    <i :style="{ width: `${(r.used / r.total) * 100}%` }"></i>
                  </div>
                  <b>{{ r.text }}</b>
                </div>
              </div>
              <div class="trio">
                <div>
                  <div class="eb">WNS</div>
                  <div class="big2 ok">+0.060<small> ns</small></div>
                </div>
                <div>
                  <div class="eb">WHS</div>
                  <div class="big2 ok">+0.046<small> ns</small></div>
                </div>
                <div>
                  <div class="eb">失败端点</div>
                  <div class="big2">0</div>
                </div>
                <div>
                  <div class="eb">PL 时钟</div>
                  <div class="big2">125<small> MHz</small></div>
                </div>
              </div>
            </div>
            <div class="p">
              <div class="eb">
                <span>ARM 逐层耗时 · 最重 8 层 (s)</span
                ><span class="badge b-meas">实测</span>
              </div>
              <svg class="ch" width="100%" height="215" viewBox="0 0 330 215">
                <g v-for="l in armLayers" :key="l.name">
                  <text x="0" :y="l.y + 13">{{ l.name }}</text>
                  <rect
                    class="wbar"
                    :class="{ hot: l.hot }"
                    x="34"
                    :y="l.y"
                    :width="l.w"
                    height="17"
                  />
                  <text :x="40 + l.w" :y="l.y + 13" class="val">
                    {{ l.s.toFixed(2) }}
                  </text>
                </g>
                <text x="0" y="212">其余 25 层合计 3.0 s · PL 全部 65.7 ms</text>
              </svg>
            </div>
            <div class="p">
              <div class="eb">
                <span>算力对比 (GMAC/s)</span
                ><span class="badge b-est">推算</span>
              </div>
              <div class="cmp">
                <div class="eb"><span>PL 实时（fps × 0.9775）</span></div>
                <div class="big3 ok">{{ gmacs == null ? "—" : gmacs.toFixed(1) }}</div>
                <div class="eb"><span>ARM 单核</span></div>
                <div class="big3 mut">0.058</div>
              </div>
              <div class="eb conf-t">
                <span>置信度分布 · 本次会话 n={{ confN }}</span>
              </div>
              <svg class="ch" width="100%" height="70" viewBox="0 0 320 70">
                <rect
                  v-for="(b, i) in confBars"
                  :key="i"
                  :x="b.x"
                  :y="62 - b.h"
                  width="29"
                  :height="b.h"
                  fill="#151715"
                />
                <path d="M0 62H320" stroke="#151715" />
              </svg>
            </div>
          </div>
        </div>
      </main>
      <main v-else-if="view === 'sys'" class="alt alt4">
        <div class="p">
          <div class="eb"><span>CPU</span><span class="badge b-live">实时</span></div>
          <div class="bigs">{{ state?.cpuPercent?.toFixed(0) ?? "—" }}<small>%</small></div>
          <svg class="ch" width="100%" height="90" viewBox="0 0 400 90"><polyline v-if="cpuLine" :points="cpuLine" class="trace" /></svg>
        </div>
        <div class="p">
          <div class="eb"><span>内存</span><span class="badge b-live">实时</span></div>
          <div class="bigs">{{ memory?.toFixed(0) ?? "—" }}<small>%</small></div>
          <svg class="ch" width="100%" height="90" viewBox="0 0 400 90"><polyline v-if="memLine" :points="memLine" class="trace" /></svg>
        </div>
        <div class="p">
          <div class="eb"><span>运行与连接</span><span class="badge b-live">实时</span></div>
          <div class="bigs">{{ uptime }}</div>
          <dl class="dl">
            <dt>连接</dt><dd>{{ online ? "在线" : "离线" }}</dd>
            <dt>最近心跳</dt><dd>{{ device?.lastSeenAt ? new Date(device.lastSeenAt).toLocaleTimeString("zh-CN", { hour12: false }) : "—" }}</dd>
            <dt>固件</dt><dd>{{ device?.firmwareVersion || "—" }}</dd>
            <dt>协议</dt><dd>{{ device?.protocolVersion || "—" }}</dd>
          </dl>
        </div>
        <div class="p">
          <div class="eb"><span>遥测分段 (ms)</span><span class="badge b-live">实时</span></div>
          <div v-for="t in tele" :key="t.label" class="hb">
            <span>{{ t.label }}</span><div class="bar"><i :style="{ width: `${t.pct}%` }"></i></div><b>{{ t.ms.toFixed(1) }}</b>
          </div>
        </div>
        <div class="p">
          <div class="eb"><span>模型</span><span class="badge b-live">实时</span></div>
          <div class="bigs sm">{{ state?.model?.version || "未部署" }}</div>
          <dl class="dl">
            <dt>载荷 sha</dt><dd>{{ state?.model?.payloadSha256?.slice(0, 8) || "—" }}</dd>
            <dt>权重 sha</dt><dd>{{ state?.model?.weightsSha256?.slice(0, 8) || "—" }}</dd>
            <dt>类别</dt><dd>{{ state?.model?.classes?.map((c) => displayName(c)).join(" / ") || "—" }}</dd>
          </dl>
        </div>
        <div class="p">
          <div class="eb"><span>产品方案</span><span class="badge b-live">实时</span></div>
          <div class="bigs sm">{{ product }}</div>
          <dl class="dl">
            <dt>置信度阈值</dt><dd>{{ state?.product ? (state.product.acceptance.confidence * 100).toFixed(0) + "%" : "—" }}</dd>
            <dt>质量门控</dt><dd>{{ state?.product ? (state.product.acceptance.qualityGate ? "开启" : "关闭") : "—" }}</dd>
            <template v-for="r in rules" :key="r.classId">
              <dt>{{ displayName(r.label) }}</dt>
              <dd>{{ r.max === 0 ? "禁止出现" : r.min === r.max ? `${r.min} 个` : `${r.min}–${r.max} 个` }}</dd>
            </template>
          </dl>
        </div>
        <div class="p">
          <div class="eb"><span>批次与同步</span><span class="badge b-live">实时</span></div>
          <div class="bigs sm">{{ state?.productionRunId ? "批次进行中" : "无进行中批次" }}</div>
          <dl class="dl">
            <dt>本批件数</dt><dd>{{ state?.runTotal ?? "—" }}</dd>
            <dt>设备累计</dt><dd>{{ state?.total ?? "—" }}</dd>
            <dt>待上传</dt><dd>{{ state?.pendingSync ?? "—" }} 条</dd>
            <dt>同步异常</dt><dd>{{ state?.syncError || "无" }}</dd>
          </dl>
        </div>
        <div class="p">
          <div class="eb"><span>帧率 / 推理延迟趋势</span><span class="badge b-live">实时</span></div>
          <div class="bigs sm">{{ fps == null ? "—" : fps.toFixed(1) }}<small> FPS</small> · {{ latency == null ? "—" : latency.toFixed(1) }}<small> ms</small></div>
          <svg class="ch" width="100%" height="90" viewBox="0 0 400 90"><polyline v-if="fpsLine" :points="fpsLine" class="trace" /><polyline v-if="latLine" :points="latLine" class="trace ok" /></svg>
        </div>
      </main>

      <main v-else class="alt alt3">
        <div class="p">
          <div class="eb"><span>判定构成 · 最近 {{ stat.n }} 条</span><span class="badge b-live">实时</span></div>
          <div class="stack">
            <i class="ok" :style="{ width: `${stat.pct(stat.c.PASS)}%` }"></i>
            <i class="bad" :style="{ width: `${stat.pct(stat.c.FAIL)}%` }"></i>
            <i class="mid" :style="{ width: `${stat.pct(stat.c.other)}%` }"></i>
          </div>
          <div class="kv">
            <div class="g"><span>合格</span><b>{{ stat.c.PASS }}</b></div>
            <div class="nb"><span>不合格</span><b>{{ stat.c.FAIL }}</b></div>
            <div><span>复核 / 其他</span><b>{{ stat.c.other }}</b></div>
          </div>
        </div>
        <div class="p">
          <div class="eb"><span>置信度分布 · 均值 {{ stat.avg == null ? "—" : (stat.avg * 100).toFixed(1) + "%" }}</span><span class="badge b-live">实时</span></div>
          <svg class="ch" width="100%" height="150" viewBox="0 0 400 150">
            <rect v-for="(b, i) in stat.bins" :key="i" :x="b.x + 2" :y="124 - b.h" width="36" :height="b.h" fill="#151715" />
            <path d="M0 124H400" stroke="#151715" />
            <text v-for="i in 5" :key="i" :x="(i - 1) * 80" y="142">{{ (i - 1) * 20 }}%</text>
          </svg>
        </div>
        <div class="p">
          <div class="eb"><span>不合格原因 TOP 5</span><span class="badge b-live">实时</span></div>
          <div v-for="r in stat.reasons" :key="r.text" class="hb wide">
            <span :title="r.text">{{ r.text }}</span><div class="bar"><i class="badfill" :style="{ width: `${r.pct}%` }"></i></div><b>{{ r.n }}</b>
          </div>
          <div v-if="!stat.reasons.length" class="wait">暂无不合格记录</div>
        </div>
        <div class="p span2">
          <div class="eb"><span>最近 10 条记录</span><span class="badge b-live">实时</span></div>
          <RouterLink
            v-for="item in stat.latest"
            :key="item.id"
            class="rec"
            :class="cls(item.result)"
            :to="{ name: 'inspection', params: { id: item.id } }"
          >
            <b>{{ chinese(item.result) }}</b>
            <span>{{ new Date(item.createdAt).toLocaleTimeString("zh-CN", { hour12: false }) }}</span>
            <span class="rs">{{ item.reason || "—" }}</span>
            <span>{{ item.confidence == null ? "—" : (item.confidence * 100).toFixed(0) + "%" }}</span>
          </RouterLink>
          <div v-if="!stat.latest.length" class="wait">检测记录将在完成后呈现</div>
        </div>
        <div class="p">
          <div class="eb"><span>说明</span></div>
          <p class="rule">本页统计取自平台已上传的最近 100 条真实检测记录；合格率只统计已明确判定的件，复核与错误不计入。演示页只读，启停与配置请回工作台。</p>
        </div>
      </main>

      <footer class="foot">
        <span class="badge b-meas">实测</span
        ><span>Zynq-7020 · Cortex-A9 @ 666.7 MHz · Linux 6.6.159</span>
        <i class="s"></i>
        <span>模型 LEVEL-v3-20261022 · sha256 d64e7b51</span>
        <i class="s"></i>
        <span>资源与时序 build/terminal/*.rpt</span>
        <i class="s"></i>
        <span>对比数据 2026-10-22</span>
        <i class="s"></i>
        <span>内存 {{ memory?.toFixed(0) ?? "—" }}% · 运行 {{ uptime }}</span>
        <span v-if="message" class="msg" role="alert">{{ message }}</span>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.fit {
  --paper: #f1f0ed;
  --card: #fbfaf8;
  --ink: #151715;
  --ink2: #484c49;
  --mut: #7c807c;
  --line: #c9c6bf;
  --acc: #1f4d3a;
  --ok: #2f7a4b;
  --bad: #b8381c;
  --amb: #a06a00;
  --mono: "IBM Plex Mono", "Cascadia Code", Consolas, monospace;
  --sans: "Noto Sans SC", "Microsoft YaHei", sans-serif;
  position: relative;
  width: 100%;
  height: 100dvh;
  overflow: hidden;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
}
.fit * {
  box-sizing: border-box;
}
.sc {
  position: absolute;
  left: 0;
  top: 0;
  width: 1920px;
  height: 1080px;
  transform-origin: 0 0;
  display: grid;
  grid-template-rows: 64px 1fr 36px;
  padding: 0 32px;
}
.sc h1,
.sc p {
  margin: 0;
}
.sc b,
.sc em {
  font-style: normal;
}
.top {
  display: flex;
  align-items: center;
  gap: 18px;
  border-bottom: 2px solid var(--ink);
}
.brand {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--ink);
  text-decoration: none;
}
.tag {
  font: 500 12px var(--mono);
  color: var(--mut);
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.tag.prod {
  letter-spacing: 0.04em;
}
.tabs {
  display: flex;
  gap: 4px;
  margin-left: 8px;
}
.tabs > * {
  padding: 5px 14px;
  font-size: 13px;
  color: var(--mut);
  text-decoration: none;
  border: 1px solid transparent;
}
.tabs .on {
  color: var(--ink);
  border-color: var(--ink);
}
.sp {
  flex: 1;
}
.live {
  display: flex;
  align-items: center;
  gap: 8px;
  font: 600 13px var(--mono);
  color: var(--mut);
}
.live i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--mut);
}
.live.up {
  color: var(--ink);
}
.live.up i {
  background: var(--ok);
  animation: blink 1.6s infinite;
}
@keyframes blink {
  50% {
    opacity: 0.25;
  }
}
.clk {
  font: 600 22px var(--mono);
}
.sel,
.ico,
.go {
  font: 600 13px var(--sans);
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--ink);
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}
.ico[aria-pressed="true"] {
  background: var(--ink);
  color: var(--paper);
}
.go {
  background: var(--acc);
  border-color: var(--acc);
  color: #fff;
}
.go.stop {
  background: var(--bad);
  border-color: var(--bad);
}
.go:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.main {
  display: grid;
  grid-template-columns: 720px 1fr;
  gap: 0 28px;
  padding: 16px 0;
  min-height: 0;
  overflow: hidden;
}
.lcol {
  display: grid;
  grid-template-rows: 656px 1fr;
  gap: 16px;
  min-height: 0;
}
.rcol {
  display: grid;
  grid-template-rows: 296px 1fr 1fr;
  gap: 16px;
  min-height: 0;
}
.p {
  overflow: hidden;
  background: var(--card);
  border: 1px solid var(--line);
  padding: 16px 20px;
  position: relative;
  min-width: 0;
}
.eb {
  font: 500 11px var(--mono);
  letter-spacing: 0.16em;
  color: var(--mut);
  text-transform: uppercase;
  display: flex;
  justify-content: space-between;
}
.badge {
  font: 600 10px var(--mono);
  letter-spacing: 0.1em;
  padding: 2px 6px;
  border: 1px solid currentColor;
}
.b-meas {
  color: var(--acc);
}
.b-est {
  color: var(--amb);
}
.b-live {
  color: var(--ink);
}

/* 视频 */
.vid {
  border: 2px solid var(--ink);
  display: grid;
  grid-template-columns: 652px 64px;
  background: var(--card);
}
.vid.no-ruler {
  grid-template-columns: 1fr;
  grid-template-rows: 1fr;
}
/* 没有刻度列时画面撑满整列，左边缘与下方卡片对齐 */
.vid.no-ruler .sq {
  aspect-ratio: auto;
  min-height: 0;
}
.sq {
  position: relative;
  aspect-ratio: 1;
  background: #d9d6cd;
  overflow: hidden;
}
.sq img,
.ov {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.sq img {
  object-fit: cover;
  user-select: none;
}
.bandfill {
  fill: color-mix(in srgb, var(--ok) 16%, transparent);
}
.rowline {
  stroke: var(--ink);
  stroke-width: 1;
  stroke-dasharray: 4 3;
}
.ann .bx {
  fill: none;
  stroke: var(--ink);
}
.ann .ld {
  fill: none;
  stroke: var(--ink);
}
.ann .lb {
  fill: var(--ink);
}
.ann text {
  fill: #fff;
  font-family: var(--mono);
  font-weight: 700;
}
.pass .ann .bx,
.pass .ann .ld {
  stroke: var(--ok);
}
.pass .ann .lb {
  fill: var(--ok);
}
.fail .ann .bx,
.fail .ann .ld {
  stroke: var(--bad);
}
.fail .ann .lb {
  fill: var(--bad);
}
.idle {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: 8px;
  text-align: center;
}
.idle b {
  font-size: 22px;
}
.idle p {
  font-size: 13px;
  color: var(--mut);
}
.vtag {
  position: absolute;
  left: 12px;
  top: 10px;
  font: 600 12px var(--mono);
  background: var(--card);
  border: 1px solid var(--ink);
  padding: 3px 8px;
}
.stamp {
  position: absolute;
  left: 14px;
  bottom: 14px;
  padding: 8px 22px;
  font: 800 30px var(--mono);
  letter-spacing: 0.12em;
  color: #fff;
  background: var(--ink);
}
.stamp.pass {
  background: var(--ok);
}
.stamp.fail {
  background: var(--bad);
}
.stamp-enter-active {
  animation: stamp 0.42s cubic-bezier(0.2, 1.3, 0.4, 1);
}
.stamp-leave-active {
  transition: opacity 0.2s;
  position: absolute;
}
.stamp-leave-to {
  opacity: 0;
}
@keyframes stamp {
  from {
    transform: scale(1.5) rotate(-4deg);
    opacity: 0;
  }
}
.ruler {
  border-left: 1px solid var(--ink);
  position: relative;
  font: 500 10px var(--mono);
}
.ruler .band {
  position: absolute;
  left: 0;
  right: 0;
  background: color-mix(in srgb, var(--ok) 22%, transparent);
  border-top: 2px solid var(--ok);
  border-bottom: 2px solid var(--ok);
}
.ruler .ptr {
  position: absolute;
  left: 0;
  right: 0;
  height: 0;
  border-top: 3px solid var(--ink);
  transition: top 0.35s cubic-bezier(0.2, 0.9, 0.3, 1);
}
.ruler .ptr b {
  position: absolute;
  right: 4px;
  top: -22px;
  background: var(--ink);
  color: #fff;
  padding: 1px 5px;
  font-size: 11px;
}
.ruler .tk {
  position: absolute;
  right: 0;
  width: 10px;
  border-top: 1px solid var(--ink2);
}
.ruler .rl {
  position: absolute;
  left: 5px;
  color: var(--mut);
}
.ruler .miss {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%) rotate(90deg);
  white-space: nowrap;
  color: var(--mut);
  font-size: 12px;
}

/* 检测带 */
.strip {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 6px;
  margin-top: 10px;
}
.strip i {
  aspect-ratio: 1;
  display: block;
  background: #d9d6cd center / cover;
  border: 2px solid var(--ok);
}
.strip i.bad {
  border-color: var(--bad);
}
.strip i.mid {
  border-color: var(--amb);
}
.strip i.e {
  border: 1px dashed var(--line);
  background: transparent;
}
.cell-enter-active {
  animation: cell 0.45s cubic-bezier(0.2, 1.2, 0.4, 1);
}
@keyframes cell {
  from {
    transform: translateX(14px) scale(0.6);
    opacity: 0;
  }
}
.kv {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 12px;
}
.kv div {
  border-top: 2px solid var(--ink);
  padding-top: 4px;
}
.kv span {
  font-size: 11px;
  color: var(--mut);
  display: block;
}
.kv b {
  font: 700 24px var(--mono);
}
.kv .g b {
  color: var(--ok);
}
.kv .nb b {
  color: var(--bad);
}

/* 英雄区 */
.hero {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 28px;
  background: var(--ink);
  color: var(--paper);
  border-color: var(--ink);
}
.hero .eb {
  color: #a3a8a3;
}
.big {
  font: 800 190px/0.9 var(--mono);
  letter-spacing: -0.07em;
  margin-top: 14px;
}
.big small {
  font-size: 90px;
  letter-spacing: 0;
  margin-left: 4px;
  color: #7fc79a;
}
.hero p {
  font-size: 13px;
  color: #a3a8a3;
  margin-top: 10px;
  line-height: 1.6;
}
.tl {
  display: grid;
  align-content: center;
  gap: 14px;
}
.lane {
  display: grid;
  grid-template-columns: 150px 1fr 120px;
  gap: 14px;
  align-items: center;
}
.lane b {
  font-size: 14px;
}
.lane small {
  display: block;
  font: 11px var(--mono);
  color: #a3a8a3;
}
.trk {
  height: 44px;
  background: #2a2d2a;
  position: relative;
  overflow: hidden;
}
.trk.pl {
  background: repeating-linear-gradient(90deg, #7fc79a 0 2px, transparent 2px 6px);
  animation: pl 0.5s linear infinite;
}
@keyframes pl {
  to {
    background-position: 6px 0;
  }
}
.fillA {
  position: absolute;
  inset: 0 auto 0 0;
  background: #8a8f8a;
}
.lane .t {
  font: 700 26px var(--mono);
  text-align: right;
  white-space: nowrap;
}
.lane .t small {
  display: inline;
  font-size: 12px;
}
.lane .t.pt {
  color: #7fc79a;
}
.axis {
  display: flex;
  justify-content: space-between;
  font: 10px var(--mono);
  color: #7b807b;
  margin: -6px 134px 0 164px;
}
.cnt {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-top: 1px solid #3b3f3b;
  padding-top: 10px;
}
.cnt b {
  font: 800 44px var(--mono);
  color: #7fc79a;
}
.cnt span {
  font-size: 13px;
  color: #a3a8a3;
}

/* 中下行 */
.row {
  display: grid;
  gap: 16px;
  min-height: 0;
  overflow: hidden;
}
.r2 {
  grid-template-columns: 330px 1fr 1fr;
}
.r3 {
  grid-template-columns: 1fr 1fr 1fr;
}
.rate {
  font: 800 92px/1 var(--mono);
  letter-spacing: -0.05em;
  margin: 8px 0 4px;
}
.rate em {
  font-size: 36px;
  color: var(--mut);
}
.bar {
  height: 10px;
  background: #e4e2dd;
  position: relative;
  margin: 6px 0;
}
.bar i {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--ok);
  transition: width 0.7s cubic-bezier(0.2, 0.9, 0.3, 1);
}
svg.ch text {
  font-family: var(--mono);
  font-size: 11px;
  fill: var(--mut);
}
svg.ch text.val {
  fill: var(--ink);
  font-weight: 700;
}
svg.ch text.val.ok {
  fill: var(--acc);
}
svg.ch text.val.bad {
  fill: var(--bad);
}
.wbar {
  fill: var(--ink2);
  transition: width 0.5s cubic-bezier(0.2, 0.9, 0.3, 1);
}
.wbar.hot {
  fill: var(--acc);
}
.wait {
  display: grid;
  place-content: center;
  height: 200px;
  color: var(--mut);
  font-size: 13px;
}
.res {
  display: grid;
  gap: 11px;
  margin-top: 12px;
}
.res > div {
  display: grid;
  grid-template-columns: 40px 1fr 118px;
  gap: 8px;
  align-items: center;
  font: 12px var(--mono);
}
.res .bar {
  height: 16px;
  margin: 0;
}
.res b {
  text-align: right;
  font-size: 11px;
  white-space: nowrap;
}
.trio {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 18px;
  margin-top: 12px;
  border-top: 1px solid var(--line);
  padding-top: 10px;
}
.trio .big2 {
  font-size: 28px;
}
.big2 {
  font: 800 34px/1 var(--mono);
  letter-spacing: -0.04em;
}
.big2 small {
  font-size: 12px;
  letter-spacing: 0;
}
.big2.ok,
.big3.ok {
  color: var(--ok);
}
.cmp {
  display: grid;
  gap: 6px;
  margin-top: 12px;
}
.big3 {
  font: 800 54px/1 var(--mono);
  letter-spacing: -0.04em;
}
.big3.mut {
  color: var(--mut);
}
.conf-t {
  margin-top: 14px;
}
.foot {
  display: flex;
  align-items: center;
  gap: 16px;
  border-top: 1px solid var(--line);
  font: 11px var(--mono);
  color: var(--mut);
}
.foot .s {
  width: 1px;
  height: 12px;
  background: var(--line);
}
.foot .msg {
  margin-left: auto;
  color: var(--bad);
  font-weight: 700;
}
.phases {
  display: flex;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
  letter-spacing: 0;
  text-transform: none;
}
.phases li {
  font: 600 11px var(--mono);
  padding: 3px 9px;
  border: 1px solid var(--line);
  color: var(--mut);
}
.phases li.done {
  color: var(--ok);
  border-color: var(--ok);
}
.phases li.on {
  background: var(--ink);
  border-color: var(--ink);
  color: var(--paper);
}
.hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ink2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tally {
  font: 800 84px/1 var(--mono);
  letter-spacing: -0.05em;
  margin: 10px 0 2px;
  animation: bump 0.5s cubic-bezier(0.2, 1.4, 0.4, 1);
  transform-origin: left center;
}
.tally em {
  font-size: 26px;
  margin-left: 6px;
  color: var(--mut);
  letter-spacing: 0;
}
@keyframes bump {
  from {
    transform: scale(1.12);
    color: var(--ok);
  }
}
.rate-line {
  font-size: 13px;
  color: var(--ink2);
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.rate-line b {
  font: 800 28px var(--mono);
  letter-spacing: -0.03em;
  color: var(--ink);
}
.rate-line small {
  margin-left: auto;
  font: 11px var(--mono);
  color: var(--mut);
}
.rule {
  margin-top: 10px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--mut);
}
.tabs button {
  padding: 5px 16px;
  font: 600 13px var(--sans);
  color: var(--mut);
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
}
.tabs button.on {
  color: var(--ink);
  border-color: var(--ink);
}
.alt {
  display: grid;
  gap: 16px;
  padding: 16px 0;
  min-height: 0;
  overflow: hidden;
}
.alt4 {
  grid-template-columns: repeat(4, 1fr);
  grid-template-rows: 1fr 1fr;
}
.alt3 {
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: 300px 1fr;
}
.alt .span2 {
  grid-column: span 2;
}
.bigs {
  font: 800 76px/1 var(--mono);
  letter-spacing: -0.05em;
  margin: 14px 0 6px;
}
.bigs.sm {
  font-size: 34px;
  letter-spacing: -0.02em;
}
.bigs small {
  font-size: 0.4em;
  color: var(--mut);
  letter-spacing: 0;
}
.trace {
  fill: none;
  stroke: var(--ink);
  stroke-width: 2;
  stroke-linejoin: round;
}
.trace.ok {
  stroke: var(--ok);
}
.dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 16px;
  margin: 10px 0 0;
  font-size: 13px;
}
.dl dt {
  color: var(--mut);
}
.dl dd {
  margin: 0;
  font: 600 13px var(--mono);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hb {
  display: grid;
  grid-template-columns: 44px 1fr 56px;
  gap: 10px;
  align-items: center;
  margin-top: 14px;
  font: 12px var(--mono);
}
.hb.wide {
  grid-template-columns: 1fr 120px 36px;
}
.hb span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hb b {
  text-align: right;
}
.hb .bar {
  margin: 0;
  height: 12px;
}
.bar i.badfill {
  background: var(--bad);
}
.stack {
  display: flex;
  height: 28px;
  margin: 20px 0 10px;
  background: #e4e2dd;
}
.stack i.ok {
  background: var(--ok);
}
.stack i.bad {
  background: var(--bad);
}
.stack i.mid {
  background: var(--amb);
}
.rec {
  display: grid;
  grid-template-columns: 70px 90px 1fr 60px;
  gap: 12px;
  align-items: baseline;
  padding: 7px 0;
  border-bottom: 1px solid var(--line);
  font: 13px var(--mono);
  color: var(--ink);
  text-decoration: none;
}
.rec b {
  color: var(--ok);
}
.rec.bad b {
  color: var(--bad);
}
.rec.mid b {
  color: var(--amb);
}
.rec .rs {
  font-family: var(--sans);
  color: var(--ink2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (prefers-reduced-motion: reduce) {
  .tally {
    animation: none;
  }
  .stamp-enter-active,
  .cell-enter-active,
  .live.up i,
  .trk.pl {
    animation: none;
  }
  .bar i,
  .wbar,
  .ruler .ptr {
    transition: none;
  }
}
</style>
