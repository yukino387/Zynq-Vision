<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { chinese } from "@vision/shared";
import type { Role } from "@vision/contracts";
import { useAuthStore } from "../stores/auth";
import { errorText, post } from "../api";
import { landingFor } from "../navigation";
import GlyphField from "./GlyphField.vue";

/** 局域网工具，用户需要知道自己在连哪台服务器 */
const origin = location.origin;
const auth = useAuthStore(),
  router = useRouter();
const mode = ref<"login" | "register">("login"),
  username = ref(""),
  password = ref(""),
  confirm = ref(""),
  name = ref(""),
  code = ref(""),
  verified = ref(false),
  grantedRole = ref<Role | null>(null),
  error = ref(""),
  busy = ref(false),
  showPassword = ref(false),
  copyState = ref<"" | "copied" | "selected">(""),
  clock = ref("--:--:--"),
  stageLive = ref(false),
  intro = ref(true);
const field = ref<{ pulse: () => void } | null>(null);
const submitEl = ref<HTMLButtonElement | null>(null);
const copyEl = ref<HTMLButtonElement | null>(null);
let clockTimer = 0,
  copyTimer = 0,
  introTimer = 0;

const heading = computed(() =>
  mode.value === "login"
    ? "登录账号"
    : verified.value
      ? "创建账号"
      : "验证注册码",
);
const roleName = computed(() =>
  grantedRole.value ? chinese(grantedRole.value) : "账号",
);
const caption = computed(() => {
  if (mode.value === "login") return "欢迎回来，请登录以继续工作。";
  if (verified.value)
    return `${roleName.value}注册码已验证，填写账号信息即可加入。`;
  return "请输入管理员签发的一次性注册码。";
});
const submitLabel = computed(() => {
  if (busy.value)
    return mode.value === "login"
      ? "验证中"
      : verified.value
        ? "创建中"
        : "校验中";
  if (mode.value === "login") return "登录";
  return verified.value ? "创建并登录" : "验证";
});
function switchMode(next: "login" | "register") {
  mode.value = next;
  error.value = "";
  password.value = "";
  confirm.value = "";
  showPassword.value = false;
  verified.value = false;
  grantedRole.value = null;
}
function resetCode() {
  verified.value = false;
  grantedRole.value = null;
  error.value = "";
}
function tick() {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  clock.value = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}
function typing() {
  field.value?.pulse();
}
/** 磁吸主按钮：轻微跟手 + 暖光跟着指针走，离开时弹回。 */
function onSubmitMove(event: PointerEvent) {
  const el = submitEl.value;
  if (!el || event.pointerType !== "mouse") return;
  const box = el.getBoundingClientRect();
  const x = event.clientX - box.left;
  const y = event.clientY - box.top;
  el.style.setProperty("--mx", `${x}px`);
  el.style.setProperty("--tx", `${(x / box.width - 0.5) * 9}px`);
  el.style.setProperty("--ty", `${(y / box.height - 0.5) * 6}px`);
}
function onSubmitLeave() {
  const el = submitEl.value;
  if (!el) return;
  el.style.setProperty("--tx", "0px");
  el.style.setProperty("--ty", "0px");
  el.style.setProperty("--mx", "50%");
}
async function copyOrigin() {
  let done = false;
  try {
    await navigator.clipboard.writeText(origin);
    done = true;
  } catch {
    const scratch = document.createElement("textarea");
    scratch.value = origin;
    scratch.style.position = "fixed";
    scratch.style.opacity = "0";
    document.body.appendChild(scratch);
    scratch.select();
    try {
      done = document.execCommand("copy");
    } catch {
      done = false;
    }
    document.body.removeChild(scratch);
  }
  if (!done) {
    // 剪贴板不可用时退回选中文本，至少让用户能直接 Ctrl+C
    const label = copyEl.value;
    if (label) {
      const range = document.createRange();
      range.selectNodeContents(label);
      const selection = window.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
    }
  }
  copyState.value = done ? "copied" : "selected";
  window.clearTimeout(copyTimer);
  copyTimer = window.setTimeout(() => (copyState.value = ""), 2000);
}
async function submit() {
  busy.value = true;
  error.value = "";
  try {
    if (mode.value === "register" && !verified.value) {
      const result = await post<{ role: Role }>("/auth/registration/verify", {
        code: code.value,
      });
      grantedRole.value = result.role;
      verified.value = true;
      return;
    }
    if (mode.value === "register") {
      if (password.value !== confirm.value)
        throw new Error("两次输入的密码不一致");
      await auth.register({
        code: code.value,
        name: name.value,
        username: username.value,
        password: password.value,
      });
    } else await auth.login(username.value, password.value);
    password.value = "";
    confirm.value = "";
    await router.replace({ name: landingFor(auth.user?.role) });
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
onMounted(() => {
  tick();
  clockTimer = window.setInterval(tick, 1000);
  stageLive.value = true;
  introTimer = window.setTimeout(() => (intro.value = false), 1500);
});
onBeforeUnmount(() => {
  window.clearInterval(clockTimer);
  window.clearTimeout(copyTimer);
  window.clearTimeout(introTimer);
});
</script>
<template>
  <div class="lg-shell" :class="`mode-${mode}`">
    <section class="lg-stage" :class="{ 'is-live': stageLive }">
      <GlyphField ref="field" />
      <div class="lg-stage-inner">
        <header class="lg-stage-top">
          <div class="lg-brand">
            <svg class="lg-brand-mark" viewBox="0 0 32 32" aria-hidden="true">
              <circle
                cx="16"
                cy="16"
                r="10.4"
                fill="none"
                stroke="currentColor"
                stroke-width="1"
              />
              <circle
                cx="16"
                cy="16"
                r="3.1"
                fill="none"
                stroke="currentColor"
                stroke-width="1"
              />
              <path
                d="M16 2.6v4.1M16 25.3v4.1M2.6 16h4.1M25.3 16h4.1"
                fill="none"
                stroke="currentColor"
                stroke-width="1"
              />
              <circle cx="16" cy="16" r="1" fill="currentColor" />
            </svg>
            <span class="lg-brand-copy"
              >视觉物联网平台<small>VISION IOT PLATFORM</small></span
            >
          </div>
          <div class="lg-stage-status">
            <i class="lg-live" aria-hidden="true"></i>
            <span class="lg-live-label">LOCAL</span>
            <span class="lg-clock">{{ clock }}</span>
          </div>
        </header>

        <div class="lg-stage-copy">
          <p class="lg-eyebrow">
            <span class="lg-eyebrow-index">01</span><i></i>边缘检测 / EDGE
            INSPECTION
          </p>
          <p class="lg-stage-title">
            采集 · 推理<br />判定 · 追溯<span
              class="lg-dot"
              aria-hidden="true"
            ></span>
          </p>
          <p class="lg-stage-lede">
            Zynq-7020 边缘推理，本地完成采集、检测与结果留存；断网时仍可继续判定。
          </p>
          <ul class="lg-stage-spec">
            <li>
              <span class="lg-spec-index">01</span>
              <span class="lg-spec-name">本地推理</span>
              <span class="lg-spec-note">PL 加速器 / INT8</span>
            </li>
            <li>
              <span class="lg-spec-index">02</span>
              <span class="lg-spec-name">现场判定</span>
              <span class="lg-spec-note">产品规则 / 阈值</span>
            </li>
            <li>
              <span class="lg-spec-index">03</span>
              <span class="lg-spec-name">逐件追溯</span>
              <span class="lg-spec-note">记录 / 证据链</span>
            </li>
          </ul>
        </div>

        <footer class="lg-stage-foot">
          <span>EDGE INFERENCE</span><i></i><span>LOCAL NETWORK</span><i></i
          ><span>逐件可追溯</span>
        </footer>
      </div>
    </section>

    <section class="lg-panel" aria-label="账号登录">
      <div class="lg-marks" aria-hidden="true">
        <i></i><i></i><i></i><i></i>
      </div>
      <header class="lg-panel-top">
        <span class="lg-panel-brand">视觉物联网平台</span>
        <span class="lg-panel-index">02 / ACCESS</span>
      </header>

      <div class="lg-panel-body">
        <form
          class="lg-form"
          :class="{ 'is-intro': intro }"
          @submit.prevent="submit"
        >
          <p class="lg-form-kicker"><i></i>身份验证 / AUTHENTICATION</p>
          <h1 class="lg-form-title">{{ heading }}</h1>
          <p class="lg-form-caption">{{ caption }}</p>

          <p v-if="auth.notice" class="lg-form-notice" role="status">
            {{ auth.notice }}
          </p>

          <div v-if="mode === 'register' && verified" class="lg-granted">
            <span class="lg-granted-mark" aria-hidden="true"></span>
            <span
              >已通过 <b>{{ roleName }}</b> 注册码验证</span
            >
            <button type="button" class="lg-granted-reset" @click="resetCode">
              更换
            </button>
          </div>

          <template v-if="mode === 'register' && !verified">
            <div class="lg-field">
              <label class="lg-field-key" for="auth-code"
                ><span>注册码</span
                ><em aria-hidden="true">REGISTRATION CODE</em></label
              >
              <div class="lg-field-line">
                <input
                  id="auth-code"
                  v-model="code"
                  required
                  autocomplete="off"
                  spellcheck="false"
                  placeholder="请输入注册码"
                  maxlength="100"
                  @input="typing"
                />
              </div>
            </div>
          </template>
          <template v-else>
            <div v-if="mode === 'register'" class="lg-field">
              <label class="lg-field-key" for="auth-name"
                ><span>姓名</span
                ><em aria-hidden="true">DISPLAY NAME</em></label
              >
              <div class="lg-field-line">
                <input
                  id="auth-name"
                  v-model="name"
                  required
                  placeholder="请输入姓名"
                  maxlength="60"
                  autocomplete="name"
                  @input="typing"
                />
              </div>
            </div>
            <div class="lg-field">
              <label class="lg-field-key" for="auth-username"
                ><span>账号</span><em aria-hidden="true">USERNAME</em></label
              >
              <div class="lg-field-line">
                <input
                  id="auth-username"
                  v-model.trim="username"
                  required
                  autocomplete="username"
                  spellcheck="false"
                  placeholder="请输入账号"
                  :pattern="
                    mode === 'register'
                      ? '[a-zA-Z0-9][a-zA-Z0-9_.-]{2,39}'
                      : undefined
                  "
                  :title="
                    mode === 'register'
                      ? '3 至 40 位字母、数字、下划线、短横线或点'
                      : undefined
                  "
                  @input="typing"
                />
              </div>
            </div>
            <div class="lg-field lg-field-secret">
              <label class="lg-field-key" for="auth-password"
                ><span>密码</span><em aria-hidden="true">PASSWORD</em></label
              >
              <div class="lg-field-line">
                <input
                  id="auth-password"
                  v-model="password"
                  required
                  :type="showPassword ? 'text' : 'password'"
                  :autocomplete="
                    mode === 'register' ? 'new-password' : 'current-password'
                  "
                  :minlength="mode === 'register' ? 8 : undefined"
                  maxlength="100"
                  :placeholder="
                    mode === 'register' ? '至少 8 位' : '请输入密码'
                  "
                  @input="typing"
                />
                <button
                  type="button"
                  class="lg-reveal"
                  :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                  :aria-pressed="showPassword"
                  @click="showPassword = !showPassword"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      d="M2.2 12S6 5.6 12 5.6 21.8 12 21.8 12 18 18.4 12 18.4 2.2 12 2.2 12z"
                    />
                    <circle cx="12" cy="12" r="3.1" />
                    <path v-if="!showPassword" d="M4.4 19.6L19.6 4.4" />
                  </svg>
                </button>
              </div>
            </div>
            <div v-if="mode === 'register'" class="lg-field lg-field-secret">
              <label class="lg-field-key" for="auth-confirm"
                ><span>确认密码</span><em aria-hidden="true">CONFIRM</em></label
              >
              <div class="lg-field-line">
                <input
                  id="auth-confirm"
                  v-model="confirm"
                  required
                  type="password"
                  autocomplete="new-password"
                  placeholder="请再次输入密码"
                  @input="typing"
                />
              </div>
            </div>
          </template>

          <p v-if="error" class="lg-form-error" role="alert">
            <span class="lg-form-error-mark" aria-hidden="true">!</span
            >{{ error }}
          </p>

          <button
            ref="submitEl"
            class="lg-submit"
            :class="{ 'is-busy': busy }"
            :disabled="busy"
            :aria-busy="busy"
            @pointermove="onSubmitMove"
            @pointerleave="onSubmitLeave"
          >
            <span class="lg-submit-label">{{ submitLabel }}</span>
            <span class="lg-submit-tail">
              <span class="lg-submit-hint" aria-hidden="true">{{
                busy ? "WAIT" : "ENTER"
              }}</span>
              <svg class="lg-arrow" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4.5 12h14M13 6.2l5.8 5.8-5.8 5.8" />
              </svg>
            </span>
            <span v-if="busy" class="lg-submit-progress"></span>
          </button>

          <p class="lg-form-switch">
            <span>{{ mode === "login" ? "还没有账号？" : "已有账号？" }}</span>
            <button
              type="button"
              class="lg-link"
              @click="switchMode(mode === 'login' ? 'register' : 'login')"
            >
              {{ mode === "login" ? "使用注册码注册" : "返回登录" }}
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h13M12.6 6.2L18.4 12l-5.8 5.8" />
              </svg>
            </button>
          </p>
        </form>
      </div>

      <footer class="lg-panel-foot">
        <span class="lg-foot-key">服务节点</span>
        <button
          ref="copyEl"
          type="button"
          class="lg-origin"
          :title="`复制 ${origin}`"
          @click="copyOrigin"
        >
          {{ origin }}
        </button>
        <span
          class="lg-foot-copy"
          :class="{ shown: !!copyState }"
          aria-live="polite"
          >{{
            copyState === "copied"
              ? "已复制"
              : copyState === "selected"
                ? "已选中"
                : ""
          }}</span
        >
      </footer>
    </section>
  </div>
</template>
<style scoped>
.lg-shell {
  --lg-bone: #f1efe7;
  --lg-ink: #171b16;
  --lg-ink-2: #4b5249;
  --lg-muted: #6b7268;
  --lg-line: rgba(23, 27, 22, 0.17);
  --lg-line-soft: rgba(23, 27, 22, 0.09);
  --lg-accent: #1f4d3a;
  --lg-accent-bright: #7fbfa0;
  --lg-bone-ink: #ece7da;
  --lg-ease: cubic-bezier(0.22, 0.82, 0.2, 1);
  --lg-display: "Noto Sans SC", "Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei", sans-serif;
  --lg-grain: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.82' numOctaves='3' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='0.055'/%3E%3C/svg%3E");
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.28fr) minmax(440px, 0.92fr);
  width: 100%;
  height: 100vh;
  height: 100dvh;
  min-height: 560px;
  overflow: hidden;
  background: var(--lg-bone);
  color: var(--lg-ink);
  font-family:
    "Noto Sans SC", "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei",
    sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.lg-shell *,
.lg-shell *::before,
.lg-shell *::after {
  box-sizing: border-box;
}

/* ─────────────  左：光学视场  ───────────── */
.lg-stage {
  position: relative;
  min-width: 0;
  overflow: hidden;
  background-color: #0a0c0a;
  background-image:
    var(--lg-grain),
    radial-gradient(
      46% 42% at 63% 42%,
      rgba(127, 191, 160, 0.11),
      rgba(127, 191, 160, 0) 70%
    ),
    radial-gradient(
      90% 70% at 88% -6%,
      rgba(255, 255, 255, 0.055),
      rgba(255, 255, 255, 0) 62%
    ),
    linear-gradient(180deg, #0b0d0b 0%, #090b09 58%, #060806 100%);
  background-size:
    140px 140px,
    auto,
    auto,
    auto;
  border-right: 1px solid rgba(127, 191, 160, 0.16);
  isolation: isolate;
  user-select: none;
  -webkit-user-select: none;
}
.lg-stage.is-live {
  cursor: none;
}
.lg-stage-inner {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: clamp(26px, 4.4vh, 46px) clamp(28px, 4.4vw, 64px)
    clamp(24px, 3.6vh, 38px);
  pointer-events: none;
}
.lg-stage-inner::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background:
    radial-gradient(
      78% 62% at 18% 84%,
      rgba(5, 7, 5, 0.86),
      rgba(5, 7, 5, 0.3) 48%,
      rgba(5, 7, 5, 0) 74%
    ),
    linear-gradient(0deg, rgba(5, 7, 5, 0.72), rgba(5, 7, 5, 0) 26%);
}
.lg-stage-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
.lg-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgba(236, 231, 218, 0.84);
}
.lg-brand-mark {
  width: 30px;
  height: 30px;
  flex: none;
  opacity: 0.9;
}
.lg-brand-copy {
  display: flex;
  flex-direction: column;
  font-size: 12.5px;
  font-weight: 500;
  letter-spacing: 0.06em;
  line-height: 1.4;
}
.lg-brand-copy small {
  margin-top: 5px;
  font-family: var(--mono);
  font-size: 7.5px;
  font-weight: 400;
  letter-spacing: 0.24em;
  color: rgba(236, 231, 218, 0.34);
  line-height: 1;
}
.lg-stage-status {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.22em;
  color: rgba(236, 231, 218, 0.42);
  white-space: nowrap;
}
.lg-live {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--lg-accent-bright);
  box-shadow: 0 0 0 0 rgba(127, 191, 160, 0.5);
  animation: lg-pulse 2.8s var(--lg-ease) infinite;
}
@keyframes lg-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(127, 191, 160, 0.45);
  }
  60%,
  100% {
    box-shadow: 0 0 0 7px rgba(127, 191, 160, 0);
  }
}
.lg-live-label {
  color: rgba(236, 231, 218, 0.3);
}
.lg-clock {
  padding-left: 12px;
  border-left: 1px solid rgba(236, 231, 218, 0.16);
  color: rgba(236, 231, 218, 0.68);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.14em;
}
.lg-stage-copy {
  max-width: 720px;
  padding-bottom: clamp(4px, 1.4vh, 16px);
}
.lg-eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 clamp(16px, 2.4vh, 24px);
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  color: rgba(236, 231, 218, 0.42);
}
.lg-eyebrow-index {
  color: var(--lg-accent-bright);
  opacity: 0.8;
}
.lg-eyebrow i {
  width: 22px;
  height: 1px;
  background: currentColor;
  opacity: 0.5;
}
.lg-stage-title {
  margin: 0;
  font-family: var(--lg-display);
  font-size: clamp(38px, 4.3vw, 70px);
  font-weight: 600;
  line-height: 1.22;
  letter-spacing: 0.02em;
  color: var(--lg-bone-ink);
  text-shadow: 0 2px 30px rgba(0, 0, 0, 0.45);
}
.lg-dot {
  display: inline-block;
  width: 0.14em;
  height: 0.14em;
  margin-left: 0.18em;
  border-radius: 50%;
  background: var(--lg-accent-bright);
  vertical-align: 0.04em;
  box-shadow: 0 0 22px rgba(127, 191, 160, 0.45);
}
.lg-stage-lede {
  max-width: 30em;
  margin: clamp(16px, 2.2vh, 24px) 0 0;
  font-size: 12.5px;
  letter-spacing: 0.04em;
  line-height: 1.95;
  color: rgba(236, 231, 218, 0.52);
}
.lg-stage-spec {
  display: flex;
  margin: clamp(26px, 4vh, 40px) 0 0;
  padding: 18px 0 0;
  list-style: none;
  border-top: 1px solid rgba(236, 231, 218, 0.14);
}
.lg-stage-spec li {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-right: 34px;
}
.lg-stage-spec li + li {
  padding-left: 26px;
  border-left: 1px solid rgba(236, 231, 218, 0.1);
}
.lg-spec-index {
  font-family: var(--mono);
  font-size: 7.5px;
  letter-spacing: 0.2em;
  color: rgba(236, 231, 218, 0.3);
}
.lg-spec-name {
  font-size: 11.5px;
  letter-spacing: 0.12em;
  color: rgba(236, 231, 218, 0.8);
}
.lg-spec-note {
  font-size: 9.5px;
  letter-spacing: 0.14em;
  color: rgba(236, 231, 218, 0.32);
}
.lg-stage-foot {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--mono);
  font-size: 7.5px;
  letter-spacing: 0.24em;
  color: rgba(236, 231, 218, 0.3);
}
.lg-stage-foot i {
  width: 16px;
  height: 1px;
  background: currentColor;
  opacity: 0.6;
}

/* ─────────────  右：登录面板  ───────────── */
.lg-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: clamp(24px, 3.2vh, 40px) clamp(28px, 3.4vw, 54px)
    clamp(20px, 2.6vh, 30px);
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background-color: var(--lg-bone);
  background-image:
    var(--lg-grain),
    radial-gradient(
      120% 80% at 100% 0%,
      rgba(255, 255, 255, 0.62),
      rgba(255, 255, 255, 0) 58%
    ),
    linear-gradient(90deg, rgba(47, 107, 74, 0.055), rgba(47, 107, 74, 0) 13%);
  background-size:
    140px 140px,
    auto,
    auto;
  color: var(--lg-ink);
}
.lg-marks {
  position: absolute;
  inset: 15px;
  pointer-events: none;
}
.lg-marks i {
  position: absolute;
  width: 9px;
  height: 9px;
  border: 0 solid rgba(23, 27, 22, 0.22);
}
.lg-marks i:nth-child(1) {
  top: 0;
  left: 0;
  border-top-width: 1px;
  border-left-width: 1px;
}
.lg-marks i:nth-child(2) {
  top: 0;
  right: 0;
  border-top-width: 1px;
  border-right-width: 1px;
}
.lg-marks i:nth-child(3) {
  bottom: 0;
  left: 0;
  border-bottom-width: 1px;
  border-left-width: 1px;
}
.lg-marks i:nth-child(4) {
  bottom: 0;
  right: 0;
  border-bottom-width: 1px;
  border-right-width: 1px;
}
.lg-panel-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.lg-panel-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.16em;
  color: var(--lg-ink-2);
}
.lg-panel-brand::before {
  content: "";
  width: 4px;
  height: 4px;
  background: var(--lg-accent);
  flex: none;
}
.lg-panel-index {
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 0.24em;
  color: rgba(23, 27, 22, 0.45);
  white-space: nowrap;
}
.lg-panel-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px 0;
  scrollbar-width: thin;
}
.lg-form {
  width: 100%;
  max-width: 378px;
  margin: auto;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}
.lg-form.is-intro > * {
  animation: lg-rise 780ms var(--lg-ease) both;
}
.lg-form.is-intro > :nth-child(1) {
  animation-delay: 20ms;
}
.lg-form.is-intro > :nth-child(2) {
  animation-delay: 80ms;
}
.lg-form.is-intro > :nth-child(3) {
  animation-delay: 130ms;
}
.lg-form.is-intro > :nth-child(4) {
  animation-delay: 180ms;
}
.lg-form.is-intro > :nth-child(5) {
  animation-delay: 230ms;
}
.lg-form.is-intro > :nth-child(6) {
  animation-delay: 280ms;
}
.lg-form.is-intro > :nth-child(7) {
  animation-delay: 330ms;
}
.lg-form.is-intro > :nth-child(8) {
  animation-delay: 380ms;
}
@keyframes lg-rise {
  from {
    opacity: 0;
    translate: 0 10px;
  }
  to {
    opacity: 1;
    translate: 0 0;
  }
}
.lg-form-kicker {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 16px;
  font-family: var(--mono);
  font-size: 8.5px;
  font-weight: 500;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  color: rgba(23, 27, 22, 0.42);
}
.lg-form-kicker i {
  width: 16px;
  height: 1px;
  background: currentColor;
  opacity: 0.6;
}
.lg-form-title {
  margin: 0;
  font-family: var(--lg-display);
  font-size: clamp(28px, 2.4vw, 35px);
  font-weight: 400;
  line-height: 1.3;
  letter-spacing: 0.006em;
  color: var(--lg-ink);
}
.lg-form-caption {
  margin: 11px 0 0;
  max-width: 32em;
  font-size: 12.5px;
  letter-spacing: 0.02em;
  line-height: 1.85;
  color: var(--lg-muted);
}
.lg-form-notice {
  display: flex;
  gap: 8px;
  margin: 18px 0 0;
  padding: 9px 12px;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--lg-ink-2);
  background: rgba(23, 27, 22, 0.035);
  border-left: 2px solid rgba(23, 27, 22, 0.28);
}
.lg-granted {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 20px 0 0;
  padding: 10px 12px;
  font-size: 11.5px;
  color: var(--lg-ink-2);
  background: rgba(23, 27, 22, 0.035);
  border: 1px solid var(--lg-line-soft);
}
.lg-granted b {
  font-weight: 600;
  color: var(--lg-ink);
}
.lg-granted-mark {
  width: 5px;
  height: 5px;
  background: var(--lg-accent);
  transform: rotate(45deg);
  flex: none;
}
.lg-granted-reset {
  margin-left: auto;
  min-height: 0;
  padding: 2px 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--lg-muted);
  font-size: 11px;
  letter-spacing: 0.06em;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.lg-granted-reset:hover {
  color: var(--lg-ink);
  background: transparent;
}

/* 输入：只有一条底线，聚焦时从左侧画出墨线 */
.lg-field {
  margin-top: 26px;
}
.lg-field-key {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 4px;
  padding: 0;
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: var(--lg-ink-2);
  transition: color 260ms var(--lg-ease);
}
.lg-field-key > span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.lg-field-key > span::before {
  content: "";
  width: 4px;
  height: 4px;
  background: var(--lg-accent);
  opacity: 0;
  transform: scale(0.4);
  transition:
    opacity 240ms var(--lg-ease),
    transform 320ms var(--lg-ease);
}
.lg-field:focus-within .lg-field-key > span::before {
  opacity: 1;
  transform: none;
}
.lg-field-key em {
  font-family: var(--mono);
  font-style: normal;
  font-size: 7.5px;
  font-weight: 400;
  letter-spacing: 0.2em;
  color: rgba(23, 27, 22, 0.3);
  transition: color 260ms var(--lg-ease);
}
.lg-field-line {
  position: relative;
  display: flex;
  align-items: flex-end;
  border-bottom: 1px solid var(--lg-line);
}
.lg-field-line::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: var(--lg-ink);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 640ms var(--lg-ease);
  pointer-events: none;
}
.lg-field:focus-within .lg-field-line::before {
  transform: scaleX(1);
  height: 1.5px;
}
.lg-field:focus-within .lg-field-key {
  color: var(--lg-ink);
}
.lg-field:focus-within .lg-field-key em {
  color: var(--lg-accent);
}
.lg-field-line input {
  flex: 1;
  width: 100%;
  min-width: 0;
  margin: 0;
  padding: 11px 0 9px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  color: var(--lg-ink);
  font-family: inherit;
  font-size: 15px;
  line-height: 1.4;
  letter-spacing: 0.01em;
  caret-color: var(--lg-accent);
  transition: none;
}
.lg-field-line input::placeholder {
  color: rgba(23, 27, 22, 0.42);
  font-size: 13.5px;
  letter-spacing: 0.02em;
}
/* 浏览器自动填充会把输入框刷成蓝底，这里让它保持纸面 */
.lg-field-line input:-webkit-autofill,
.lg-field-line input:-webkit-autofill:hover,
.lg-field-line input:-webkit-autofill:focus {
  -webkit-text-fill-color: var(--lg-ink);
  -webkit-box-shadow: inset 0 0 0 1000px var(--lg-bone);
  box-shadow: inset 0 0 0 1000px var(--lg-bone);
  caret-color: var(--lg-accent);
  transition: background-color 9999s ease-out;
}
.lg-field-line input:focus,
.lg-field-line input:focus-visible {
  outline: none;
  box-shadow: none;
  border: 0;
}
.lg-field-secret input {
  padding-right: 38px;
}
.lg-reveal {
  position: absolute;
  right: -7px;
  bottom: 1px;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  min-height: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: rgba(23, 27, 22, 0.44);
  transition: color 200ms var(--lg-ease);
}
.lg-reveal:hover {
  background: transparent;
  color: var(--lg-ink);
}
.lg-reveal svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.3;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.lg-reveal:focus-visible {
  outline: 1px solid var(--lg-ink);
  outline-offset: 2px;
}
.lg-form-error {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin: 20px 0 0;
  padding: 10px 12px;
  font-size: 11.5px;
  line-height: 1.7;
  color: #8f3a24;
  background: rgba(47, 107, 74, 0.07);
  border-left: 2px solid var(--lg-accent);
}
.lg-form-error-mark {
  display: grid;
  place-items: center;
  width: 14px;
  height: 14px;
  margin-top: 1px;
  flex: none;
  font-family: var(--mono);
  font-size: 9px;
  color: #fff;
  background: var(--lg-accent);
  border-radius: 50%;
}

/* 主操作：磁吸 + 跟随指针的暖光 */
.lg-submit {
  --tx: 0px;
  --ty: 0px;
  --mx: 50%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
  height: 54px;
  min-height: 54px;
  margin: 30px 0 0;
  padding: 0 18px 0 20px;
  overflow: hidden;
  border: 1px solid #1f4d3a;
  border-radius: 2px;
  background: #1f4d3a;
  color: #f1eee4;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.2em;
  text-align: left;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
  transform: translate(var(--tx), var(--ty));
  transition:
    background 320ms var(--lg-ease),
    border-color 320ms var(--lg-ease),
    box-shadow 320ms var(--lg-ease),
    transform 220ms var(--lg-ease),
    opacity 200ms linear;
}
.lg-submit::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: linear-gradient(
    108deg,
    rgba(255, 244, 232, 0) 38%,
    rgba(255, 244, 232, 0.14) 50%,
    rgba(255, 244, 232, 0) 62%
  );
  background-size: 320px 100%;
  background-repeat: no-repeat;
  background-position: calc(var(--mx) - 160px) 0;
  mix-blend-mode: screen;
  opacity: 0;
  transition: opacity 320ms var(--lg-ease);
  pointer-events: none;
}
.lg-submit:hover {
  background: #2a6349;
  border-color: #2a6349;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 14px 30px -22px rgba(10, 12, 10, 0.9);
}
.lg-submit:hover::before {
  opacity: 1;
}
.lg-submit:active:not(:disabled) {
  transform: translate(var(--tx), calc(var(--ty) + 1px));
}
.lg-submit:disabled {
  opacity: 0.78;
  cursor: progress;
}
.lg-submit-label {
  position: relative;
  z-index: 1;
}
.lg-submit-tail {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 11px;
}
.lg-submit-hint {
  font-family: var(--mono);
  font-size: 7.5px;
  font-weight: 400;
  letter-spacing: 0.24em;
  color: rgba(241, 238, 228, 0.36);
}
.lg-arrow {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.4;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: transform 380ms var(--lg-ease);
}
.lg-submit:hover .lg-arrow {
  transform: translateX(4px);
}
.lg-submit:focus-visible {
  outline: 2px solid var(--lg-accent);
  outline-offset: 3px;
}
.lg-submit-progress {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 100%;
  height: 1.5px;
  background-image: linear-gradient(
    90deg,
    rgba(127, 191, 160, 0) 0%,
    rgba(127, 191, 160, 0.95) 50%,
    rgba(127, 191, 160, 0) 100%
  );
  background-size: 38% 100%;
  background-repeat: no-repeat;
  animation: lg-scan 1.15s linear infinite;
}
@keyframes lg-scan {
  from {
    background-position: -40% 0;
  }
  to {
    background-position: 140% 0;
  }
}
.lg-form-switch {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 24px 0 0;
  font-size: 11.5px;
  letter-spacing: 0.04em;
  color: var(--lg-muted);
}
.lg-link {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 0;
  padding: 0 0 2px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--lg-ink);
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.04em;
}
.lg-link::after {
  content: "";
  position: absolute;
  left: 0;
  right: 15px;
  bottom: 0;
  height: 1px;
  background: currentColor;
  opacity: 0.3;
  transform: scaleX(0.55);
  transform-origin: left center;
  transition:
    transform 460ms var(--lg-ease),
    opacity 240ms var(--lg-ease);
}
.lg-link:hover {
  background: transparent;
  color: var(--lg-ink);
}
.lg-link:hover::after {
  transform: scaleX(1);
  opacity: 1;
}
.lg-link svg {
  width: 13px;
  height: 13px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: transform 360ms var(--lg-ease);
}
.lg-link:hover svg {
  transform: translateX(3px);
}
.lg-link:focus-visible {
  outline: 1px solid var(--lg-ink);
  outline-offset: 3px;
}
.lg-panel-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 16px;
  border-top: 1px solid var(--lg-line-soft);
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 0.2em;
  color: rgba(23, 27, 22, 0.4);
}
.lg-foot-key {
  text-transform: uppercase;
}
.lg-origin {
  min-height: 0;
  padding: 0 0 2px;
  border: 0;
  border-radius: 0;
  border-bottom: 1px dashed rgba(23, 27, 22, 0.26);
  background: transparent;
  color: var(--lg-ink-2);
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.02em;
  cursor: copy;
  overflow-wrap: anywhere;
  text-align: left;
}
.lg-origin:hover {
  background: transparent;
  color: var(--lg-ink);
  border-bottom-color: var(--lg-ink);
}
.lg-origin:focus-visible {
  outline: 1px solid var(--lg-ink);
  outline-offset: 3px;
}
.lg-foot-copy {
  opacity: 0;
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 0.22em;
  color: var(--lg-accent);
  transition: opacity 240ms var(--lg-ease);
}
.lg-foot-copy.shown {
  opacity: 1;
}

/* ─────────────  窄屏  ───────────── */
@media (max-width: 1180px) {
  .lg-shell {
    grid-template-columns: minmax(0, 1.02fr) minmax(418px, 1fr);
  }
  .lg-stage-spec li {
    padding-right: 24px;
  }
  .lg-stage-spec li + li {
    padding-left: 20px;
  }
}
@media (max-width: 960px) {
  .lg-shell {
    display: block;
    height: auto;
    min-height: 100dvh;
    overflow: visible;
  }
  .lg-stage {
    height: clamp(232px, 33dvh, 320px);
    border-right: 0;
    border-bottom: 1px solid rgba(127, 191, 160, 0.14);
  }
  .lg-stage-inner {
    padding: 20px 22px 20px;
  }
  .lg-brand-copy {
    font-size: 11.5px;
  }
  .lg-stage-copy {
    padding-bottom: 0;
  }
  .lg-stage-title {
    font-size: clamp(28px, 8vw, 40px);
    line-height: 1.3;
  }
  .lg-eyebrow {
    margin-bottom: 10px;
    font-size: 8px;
  }
  .lg-stage-lede,
  .lg-stage-spec,
  .lg-stage-foot {
    display: none;
  }
  .lg-stage-status {
    font-size: 8px;
    gap: 8px;
  }
  .lg-panel {
    min-height: calc(100dvh - clamp(232px, 33dvh, 320px));
    padding: 30px 26px 22px;
  }
  .lg-panel-top {
    display: none;
  }
  .lg-panel-body {
    overflow: visible;
    padding: 22px 0;
  }
  .lg-form {
    max-width: 420px;
  }
  .lg-field {
    margin-top: 22px;
  }
}
@media (max-width: 560px) {
  .lg-stage {
    height: clamp(240px, 33dvh, 300px);
  }
  .lg-panel {
    min-height: calc(100dvh - clamp(240px, 33dvh, 300px));
    padding: 26px 20px 18px;
  }
  .lg-panel-top {
    display: none;
  }
  .lg-marks {
    inset: 10px;
  }
  .lg-form-title {
    font-size: 28px;
  }
  .lg-form-caption {
    font-size: 12px;
  }
  .lg-field-line input {
    font-size: 16px;
  }
  .lg-submit {
    height: 52px;
    min-height: 52px;
    margin-top: 26px;
  }
  .lg-submit-hint {
    display: none;
  }
  .lg-panel-foot {
    font-size: 7.5px;
  }
}
@media (max-height: 660px) and (min-width: 961px) {
  .lg-panel {
    padding-top: 20px;
    padding-bottom: 16px;
  }
  .lg-panel-body {
    padding: 8px 0;
  }
  .lg-form-kicker {
    margin-bottom: 10px;
  }
  .lg-form-caption {
    margin-top: 6px;
  }
  .lg-field {
    margin-top: 16px;
  }
  .lg-submit {
    margin-top: 20px;
    height: 46px;
    min-height: 46px;
  }
  .lg-form-switch {
    margin-top: 16px;
  }
}
@media (max-width: 960px) and (max-height: 720px) {
  .lg-stage {
    height: 212px;
  }
  .lg-panel {
    min-height: calc(100dvh - 212px);
    padding: 18px 20px 12px;
  }
  .lg-panel-body {
    padding: 10px 0;
  }
  .lg-form-kicker {
    margin-bottom: 10px;
  }
  .lg-field {
    margin-top: 18px;
  }
  .lg-submit {
    margin-top: 22px;
    height: 50px;
    min-height: 50px;
  }
  .lg-form-switch {
    margin-top: 18px;
  }
}
@media (max-width: 420px) {
  .lg-live-label {
    display: none;
  }
  .lg-stage-status {
    gap: 6px;
  }
  .lg-brand-copy {
    white-space: nowrap;
  }
  .lg-brand-copy small {
    font-size: 7px;
    letter-spacing: 0.16em;
  }
  .lg-clock {
    padding-left: 8px;
  }
}
@media (min-width: 1600px) {
  .lg-form {
    max-width: 400px;
  }
  .lg-stage-lede {
    font-size: 13.5px;
  }
  .lg-stage-spec {
    margin-top: 46px;
  }
}
@media (max-height: 760px) and (min-width: 961px) {
  .lg-stage-title {
    font-size: clamp(34px, 3.9vw, 50px);
  }
  .lg-stage-spec {
    margin-top: 22px;
  }
  .lg-spec-note {
    display: none;
  }
  .lg-field {
    margin-top: 20px;
  }
  .lg-submit {
    margin-top: 24px;
    height: 50px;
    min-height: 50px;
  }
  .lg-stage-inner {
    padding-top: 26px;
    padding-bottom: 22px;
  }
}
/* 错误语义保持红，不要跟强调绿混用 */
.lg-form-error {
  color: #8f3a24;
  background: rgba(165, 50, 26, 0.07);
  border-left-color: #a5321a;
}
.lg-form-error-mark {
  background: #a5321a;
}
</style>
