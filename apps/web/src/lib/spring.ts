/** 规范 6.2/6.3 的最小共享实现：位置、宽度、高度分别使用参考参数。 */
export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface SpringRect extends Rect {
  vx: number;
  vy: number;
  vw: number;
  vh: number;
}

export const SPRING_STEP = 1 / 120;
export const SPRING_MAX_FRAME_MS = 48;

/** 固定子步数，单帧时间差限幅，避免后台恢复时长帧一次性代入弹簧。 */
export function springSubsteps(frameDeltaMs: number) {
  const clamped = Math.min(SPRING_MAX_FRAME_MS, Math.max(1, frameDeltaMs));
  return Math.max(1, Math.min(12, Math.ceil(clamped / 1000 / SPRING_STEP)));
}

export function integrateRect(state: SpringRect, target: Rect, dt: number) {
  const ax = (210 * (target.x - state.x) - 26 * state.vx) / 0.9;
  state.vx += ax * dt;
  state.x += state.vx * dt;
  const ay = (210 * (target.y - state.y) - 26 * state.vy) / 0.9;
  state.vy += ay * dt;
  state.y += state.vy * dt;
  const aw = (235 * (target.width - state.width) - 28 * state.vw) / 0.84;
  state.vw += aw * dt;
  state.width += state.vw * dt;
  const ah = (205 * (target.height - state.height) - 27 * state.vh) / 0.88;
  state.vh += ah * dt;
  state.height += state.vh * dt;
  state.width = Math.max(8, state.width);
  state.height = Math.max(6, state.height);
}

/** 6.5 停稳：主通道误差 <= 0.5px、速度 <= 3px/s。 */
export function rectSettled(state: SpringRect, target: Rect) {
  const position = Math.max(
    Math.abs(state.x - target.x),
    Math.abs(state.y - target.y),
  );
  const size = Math.max(
    Math.abs(state.width - target.width),
    Math.abs(state.height - target.height),
  );
  const speed = Math.max(
    Math.abs(state.vx),
    Math.abs(state.vy),
    Math.abs(state.vw),
    Math.abs(state.vh),
  );
  return position <= 0.5 && size <= 0.5 && speed <= 3;
}
