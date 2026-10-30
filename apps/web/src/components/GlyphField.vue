<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

/** 登录页的光学视场：字符点云 + 孔径刻度 + 鼠标准星。
 *  只用一层 canvas，坐标全部按 CSS 像素计算，DPR 仅影响清晰度。
 *  字符先烘焙成贴图（bone / warm 两套），逐帧只 drawImage，避免 fillText 的开销。 */
interface Mote {
  angle: number;
  radius: number;
  depth: number;
  glyph: number;
  alpha: number;
  phase: number;
  speed: number;
  dir: number;
  hot: boolean;
  han: boolean;
  size: number;
}
interface Ripple {
  x: number;
  y: number;
  born: number;
  strength: number;
}

const host = ref<HTMLDivElement | null>(null);
const surface = ref<HTMLCanvasElement | null>(null);

const TAU = Math.PI * 2;
const MONO = '"Cascadia Mono", Consolas, monospace';
const GLYPHS = "0123456789ABCDEF·+×○◇".split("");
const HAN = [
  "光",
  "视",
  "检",
  "测",
  "像",
  "素",
  "阈",
  "边",
  "缘",
  "帧",
  "深",
  "度",
];
const BONE = "rgb(236,231,218)";
const WARM = "rgb(127,191,160)";

let ctx: CanvasRenderingContext2D | null = null;
let frameId = 0;
let watching: ResizeObserver | null = null;
let reduced = false;
let started = 0;
let lastFrame = 0;
let w = 0;
let h = 0;
let dpr = 1;
let cx = 0;
let cy = 0;
let radius = 300;
let motes: Mote[] = [];
let boneSprites: HTMLCanvasElement[] = [];
let warmSprites: HTMLCanvasElement[] = [];
let hanSprites: HTMLCanvasElement[] = [];
let spriteDpr = 0;
const target = { x: 0, y: 0, inside: false };
const pointer = { x: 0, y: 0, inside: false };
let reticle = 0;
let ripples: Ripple[] = [];

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

/** 把单字渲染成一张贴图；贴图用 DPR 分辨率，绘制时再缩到 CSS 尺寸。 */
function sprite(glyph: string, color: string) {
  const font = Math.round(34 * spriteDpr);
  const box = Math.ceil(font * 1.6);
  const canvas = document.createElement("canvas");
  canvas.width = box;
  canvas.height = box;
  const pen = canvas.getContext("2d");
  if (!pen) return canvas;
  pen.font = `400 ${font}px ${MONO}`;
  pen.textAlign = "center";
  pen.textBaseline = "middle";
  pen.fillStyle = color;
  pen.fillText(glyph, box / 2, box / 2);
  return canvas;
}

function buildSprites() {
  spriteDpr = dpr;
  boneSprites = GLYPHS.map((glyph) => sprite(glyph, BONE));
  warmSprites = GLYPHS.map((glyph) => sprite(glyph, WARM));
  hanSprites = HAN.map((glyph) => sprite(glyph, BONE));
}

function buildMotes() {
  const count = Math.round(clamp((w * h) / 300, 700, 3000));
  const bands = [0.34, 0.56, 0.76, 0.94];
  const next: Mote[] = [];
  for (let i = 0; i < count; i += 1) {
    const han = Math.random() < 0.011;
    const depth = Math.random();
    // 一部分点落在同心带上，其余散成尘埃，形成被刻过的光学表面。
    const banded = Math.random() < 0.34;
    const band = bands[Math.floor(Math.random() * bands.length)] ?? 0.6;
    const r = banded
      ? band + (Math.random() - 0.5) * 0.032
      : 0.12 + Math.sqrt(Math.random()) * 1.03;
    const edge = r > 1 ? Math.max(0, 1 - (r - 1) / 0.16) : 1;
    const base = han
      ? 0.035 + Math.random() * 0.04
      : banded
        ? 0.05 + Math.pow(Math.random(), 2) * 0.26
        : 0.025 + Math.pow(Math.random(), 2.6) * 0.19;
    next.push({
      angle: Math.random() * TAU,
      radius: r,
      depth,
      glyph: Math.floor(Math.random() * GLYPHS.length),
      alpha: base * (0.45 + depth * 0.55) * edge,
      phase: Math.random() * TAU,
      speed: 0.5 + Math.random() * 1.1,
      dir: Math.random() < 0.5 ? -1 : 1,
      hot: !han && Math.random() < 0.008,
      han,
      size: han ? 14 + depth * 6 : 7.4 + depth * 4,
    });
  }
  motes = next;
}

function measure() {
  const box = host.value?.getBoundingClientRect();
  const canvas = surface.value;
  if (!box || !canvas) return;
  const nextDpr = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
  w = Math.max(1, box.width);
  h = Math.max(1, box.height);
  if (nextDpr !== spriteDpr) {
    dpr = nextDpr;
    buildSprites();
  }
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  const pen = canvas.getContext("2d");
  if (!pen) return;
  ctx = pen;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // 横向的短条带（手机顶部）与竖向大面板用不同的孔径比例。
  if (w > h * 1.15) {
    radius = Math.min(w * 0.38, h * 0.62);
    cx = w * 0.63;
    cy = h * 0.5;
  } else {
    radius = Math.min(w * 0.36, h * 0.46);
    cx = w * 0.63;
    cy = h * 0.42;
  }
  buildMotes();
}

function circle(x: number, y: number, r: number, color: string, width: number) {
  if (!ctx) return;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, TAU);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.stroke();
}

function drawRings(t: number, now: number) {
  if (!ctx) return;
  const intro = reduced ? 1 : Math.min(1, (now - started) / 1200);
  const ox = pointer.inside ? clamp((pointer.x - cx) * 0.018, -9, 9) : 0;
  const oy = pointer.inside ? clamp((pointer.y - cy) * 0.018, -9, 9) : 0;
  ctx.save();
  ctx.translate(cx + ox, cy + oy);

  const glow = ctx.createRadialGradient(0, 0, radius * 0.04, 0, 0, radius);
  glow.addColorStop(0, "rgba(127,191,160,0.062)");
  glow.addColorStop(0.42, "rgba(127,191,160,0.018)");
  glow.addColorStop(1, "rgba(127,191,160,0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(0, 0, radius, 0, TAU);
  ctx.fill();

  ctx.globalAlpha = intro;
  circle(0, 0, radius, "rgba(235,230,217,0.17)", 1);
  circle(0, 0, radius * 0.93, "rgba(235,230,217,0.055)", 1);

  ctx.setLineDash([1.5, 6.5]);
  circle(0, 0, radius * 0.79, "rgba(235,230,217,0.11)", 1);
  ctx.setLineDash([]);

  for (let i = 0; i < 4; i += 1) {
    const from = -Math.PI / 2 + i * (Math.PI / 2) + 0.16;
    ctx.beginPath();
    ctx.arc(0, 0, radius * 0.56, from, from + Math.PI / 2 - 0.32);
    ctx.strokeStyle = "rgba(235,230,217,0.09)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  ctx.beginPath();
  ctx.strokeStyle = "rgba(235,230,217,0.1)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 72; i += 1) {
    if (i % 6 === 0) continue;
    const a = (i / 72) * TAU;
    ctx.moveTo(Math.cos(a) * radius * 1.012, Math.sin(a) * radius * 1.012);
    ctx.lineTo(Math.cos(a) * radius * 1.034, Math.sin(a) * radius * 1.034);
  }
  ctx.stroke();

  ctx.beginPath();
  ctx.strokeStyle = "rgba(235,230,217,0.24)";
  for (let i = 0; i < 72; i += 6) {
    const a = (i / 72) * TAU;
    ctx.moveTo(Math.cos(a) * radius * 1.012, Math.sin(a) * radius * 1.012);
    ctx.lineTo(Math.cos(a) * radius * 1.056, Math.sin(a) * radius * 1.056);
  }
  ctx.stroke();

  const label = Math.max(7, Math.round(radius * 0.027));
  ctx.font = `500 ${label}px ${MONO}`;
  ctx.fillStyle = "rgba(235,230,217,0.3)";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const marks: Array<[string, number]> = [
    ["000", -Math.PI / 2],
    ["090", 0],
    ["180", Math.PI / 2],
    ["270", Math.PI],
  ];
  for (const [text, a] of marks) {
    const r = radius * 1.092;
    ctx.fillText(text, Math.cos(a) * r, Math.sin(a) * r);
  }

  // 一圈很慢的扫描弧，像仪器在自检。
  const sweep = t * 0.24;
  for (let i = 0; i < 8; i += 1) {
    const end = sweep - i * 0.03;
    ctx.beginPath();
    ctx.arc(0, 0, radius * 0.9, end - 0.05, end);
    ctx.strokeStyle = `rgba(127,191,160,${(0.2 * (1 - i / 8) * intro).toFixed(3)})`;
    ctx.lineWidth = 1.2;
    ctx.stroke();
  }

  ctx.beginPath();
  ctx.strokeStyle = "rgba(235,230,217,0.16)";
  ctx.lineWidth = 1;
  ctx.moveTo(-radius * 0.1, 0);
  ctx.lineTo(-radius * 0.03, 0);
  ctx.moveTo(radius * 0.03, 0);
  ctx.lineTo(radius * 0.1, 0);
  ctx.moveTo(0, -radius * 0.1);
  ctx.lineTo(0, -radius * 0.03);
  ctx.moveTo(0, radius * 0.03);
  ctx.lineTo(0, radius * 0.1);
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(0, 0, 2.2, 0, TAU);
  ctx.fillStyle = "rgba(127,191,160,0.5)";
  ctx.fill();
  ctx.restore();
  ctx.globalAlpha = 1;
}

function drawMotes(t: number) {
  if (!ctx) return;
  const px = pointer.x;
  const py = pointer.y;
  const parX = pointer.inside ? clamp(px - cx, -460, 460) : 0;
  const parY = pointer.inside ? clamp(py - cy, -460, 460) : 0;
  const near = pointer.inside ? 1 : 0;
  const intro = reduced ? 1 : Math.min(1, (performance.now() - started) / 1400);

  for (const mote of motes) {
    const band = radius * mote.radius;
    const rr =
      band * (1 + 0.012 * Math.sin(t * 0.32 * mote.speed + mote.phase));
    const angle =
      mote.angle + t * (0.055 - 0.035 * Math.min(1, mote.radius)) * mote.dir;
    let x = cx + Math.cos(angle) * rr;
    let y = cy + Math.sin(angle) * rr * 0.94;
    x += parX * (0.006 + 0.05 * mote.depth);
    y += parY * (0.006 + 0.05 * mote.depth);

    let warmth = 0;
    if (near) {
      const dx = x - px;
      const dy = y - py;
      const span = 132;
      const distance2 = dx * dx + dy * dy;
      if (distance2 < span * span) {
        const distance = Math.sqrt(distance2) || 1;
        const pull = (1 - distance / span) ** 2 * 17;
        x += (dx / distance) * pull;
        y += (dy / distance) * pull;
        warmth = (1 - distance / span) ** 2;
      }
    }

    const wave =
      0.8 + 0.2 * Math.sin(t * 0.45 - mote.radius * 3.2 + mote.phase * 0.2);
    let alpha = mote.alpha * wave * (0.75 + warmth * 1.4) * intro;
    if (mote.hot)
      alpha = Math.min(
        0.62,
        alpha + 0.14 + 0.08 * Math.sin(t * 0.9 + mote.phase),
      );
    if (alpha < 0.01) continue;
    alpha = Math.min(0.5, alpha);

    const box = mote.size * 1.6;
    const half = box / 2;
    const source = mote.han
      ? hanSprites[mote.glyph % hanSprites.length]
      : boneSprites[mote.glyph];
    if (!source) continue;
    ctx.globalAlpha = alpha;
    ctx.drawImage(source, x - half, y - half, box, box);
    if (!mote.han && warmth > 0.18) {
      const hot = warmSprites[mote.glyph];
      if (hot) {
        ctx.globalAlpha = Math.min(1, warmth * 0.82);
        ctx.drawImage(hot, x - half, y - half, box, box);
      }
    }
  }
  ctx.globalAlpha = 1;
}

function drawRipples(now: number) {
  if (!ctx || !ripples.length) return;
  ripples = ripples.filter((item) => now - item.born < 1700);
  for (const item of ripples) {
    const age = (now - item.born) / 1700;
    const grow = 8 + age * radius * 1.05;
    const fade = (1 - age) ** 2 * 0.34 * item.strength;
    if (fade < 0.004) continue;
    ctx.beginPath();
    ctx.arc(item.x, item.y, grow, 0, TAU);
    ctx.strokeStyle = `rgba(127,191,160,${fade.toFixed(3)})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

function drawReticle(now: number) {
  if (!ctx) return;
  const beat = 0.82 + 0.18 * Math.sin(now / 640);
  if (reticle > 0.01) {
    const x = pointer.x;
    const y = pointer.y;
    ctx.globalAlpha = reticle;
    ctx.strokeStyle = "rgba(235,230,217,0.075)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();

    ctx.strokeStyle = `rgba(235,230,217,${(0.46 * beat).toFixed(3)})`;
    for (let i = 0; i < 4; i += 1) {
      const from = (i / 4) * TAU + 0.22;
      ctx.beginPath();
      ctx.arc(x, y, 13, from, from + (TAU / 4) * 0.56);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(x - 22, y);
    ctx.lineTo(x - 17, y);
    ctx.moveTo(x + 17, y);
    ctx.lineTo(x + 22, y);
    ctx.moveTo(x, y - 22);
    ctx.lineTo(x, y - 17);
    ctx.moveTo(x, y + 17);
    ctx.lineTo(x, y + 22);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(x, y, 1.5, 0, TAU);
    ctx.fillStyle = "rgba(127,191,160,0.9)";
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  // 右下角的实时坐标读数：让准星看起来确实在测量。
  const pad = (value: number) => String(Math.round(value)).padStart(4, "0");
  ctx.textAlign = "right";
  ctx.textBaseline = "bottom";
  ctx.font = `500 8.5px ${MONO}`;
  ctx.fillStyle = `rgba(235,230,217,${(0.1 + reticle * 0.3).toFixed(3)})`;
  ctx.fillText(
    pointer.inside
      ? `X ${pad(pointer.x)}   Y ${pad(pointer.y)}`
      : "X ----   Y ----",
    w - 34,
    h - 30,
  );
  ctx.font = `500 7px ${MONO}`;
  ctx.fillStyle = `rgba(235,230,217,${(0.08 + reticle * 0.14).toFixed(3)})`;
  ctx.fillText("RETICLE", w - 34, h - 44);
}

function render(t: number, now: number) {
  if (!ctx) return;
  ctx.clearRect(0, 0, w, h);
  drawRings(t, now);
  drawMotes(t);
  drawRipples(now);
  drawReticle(now);
}

function frame(now: number) {
  frameId = requestAnimationFrame(frame);
  const dt = lastFrame ? Math.min(0.05, (now - lastFrame) / 1000) : 0.016;
  lastFrame = now;
  const follow = Math.min(1, dt * 14);
  pointer.x += (target.x - pointer.x) * follow;
  pointer.y += (target.y - pointer.y) * follow;
  pointer.inside = target.inside;
  reticle += ((target.inside ? 1 : 0) - reticle) * Math.min(1, dt * 9);
  render(now / 1000, now);
}

function start() {
  if (frameId || reduced) return;
  lastFrame = 0;
  frameId = requestAnimationFrame(frame);
}

function stop() {
  if (!frameId) return;
  cancelAnimationFrame(frameId);
  frameId = 0;
}

function onPointerMove(event: PointerEvent) {
  if (event.pointerType === "touch") return;
  const box = host.value?.getBoundingClientRect();
  if (!box) return;
  const x = event.clientX - box.left;
  const y = event.clientY - box.top;
  const inside = x >= 0 && y >= 0 && x <= box.width && y <= box.height;
  target.inside = inside;
  if (inside) {
    target.x = x;
    target.y = y;
    pointer.x = pointer.x || x;
    pointer.y = pointer.y || y;
  }
}

function onPointerDown(event: PointerEvent) {
  if (event.pointerType === "touch") return;
  const box = host.value?.getBoundingClientRect();
  if (!box) return;
  const x = event.clientX - box.left;
  const y = event.clientY - box.top;
  if (x < 0 || y < 0 || x > box.width || y > box.height) return;
  ripples.push({ x, y, born: performance.now(), strength: 1 });
  if (ripples.length > 5) ripples.shift();
}

function onVisibility() {
  if (document.hidden) stop();
  else start();
}

/** 输入框每敲一下，视场中心扩散一圈波纹，把两张屏连起来。 */
function pulse() {
  ripples.push({ x: cx, y: cy, born: performance.now(), strength: 0.42 });
  if (ripples.length > 5) ripples.shift();
}

defineExpose({ pulse });

onMounted(() => {
  reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  started = performance.now();
  measure();
  render(0, started);
  if (reduced) return;
  start();
  watching = new ResizeObserver(() => {
    measure();
  });
  if (host.value) watching.observe(host.value);
  window.addEventListener("pointermove", onPointerMove, { passive: true });
  window.addEventListener("pointerdown", onPointerDown, { passive: true });
  document.addEventListener("visibilitychange", onVisibility);
});

onBeforeUnmount(() => {
  stop();
  watching?.disconnect();
  watching = null;
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerdown", onPointerDown);
  document.removeEventListener("visibilitychange", onVisibility);
});
</script>

<template>
  <div ref="host" class="glyph-field" aria-hidden="true">
    <canvas ref="surface"></canvas>
  </div>
</template>

<style scoped>
.glyph-field {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}
.glyph-field canvas {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
