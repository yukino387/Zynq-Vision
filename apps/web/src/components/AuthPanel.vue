<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { chinese } from "@vision/shared";
import type { Role } from "@vision/contracts";
import { useAuthStore } from "../stores/auth";
import { errorText, post } from "../api";
import { landingFor } from "../navigation";
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
  busy = ref(false);
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
function switchMode(next: "login" | "register") {
  mode.value = next;
  error.value = "";
  password.value = "";
  confirm.value = "";
  verified.value = false;
  grantedRole.value = null;
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
</script>
<template>
  <div class="login-screen">
    <section class="auth-faceplate">
      <h2>边缘视觉检测平台</h2>
      <p>配置产品规则，连接检测设备，查看单件结果。</p>
      <div class="auth-instrument">
        <span>配置产品</span><span>自动检测</span><span>逐件追溯</span>
      </div>
      <small>视觉物联网平台</small>
    </section>
    <div class="auth-wrap">
      <div class="auth-product">视觉物联网平台</div>
      <form class="login-form" @submit.prevent="submit">
        <h1>{{ heading }}</h1>
        <p v-if="auth.notice" class="banner" role="status">{{ auth.notice }}</p>
        <p class="muted auth-caption">
          {{
            mode === "login"
              ? "欢迎回来，请登录以继续工作"
              : verified
                ? `${roleName}注册码已验证，填写账号信息即可加入`
                : "请输入管理员签发的一次性注册码"
          }}
        </p>
        <template v-if="mode === 'register' && !verified">
          <label
            >注册码<input
              v-model="code"
              required
              autocomplete="off"
              placeholder="请输入注册码"
              maxlength="100"
          /></label>
        </template>
        <template v-else>
          <label v-if="mode === 'register'"
            >姓名<input
              v-model="name"
              required
              placeholder="请输入姓名"
              maxlength="60"
              autocomplete="name"
          /></label>
          <label
            >账号<input
              v-model.trim="username"
              required
              autocomplete="username"
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
          /></label>
          <label
            >密码<input
              v-model="password"
              required
              type="password"
              :autocomplete="
                mode === 'register' ? 'new-password' : 'current-password'
              "
              :minlength="mode === 'register' ? 8 : undefined"
              maxlength="100"
              :placeholder="mode === 'register' ? '至少 8 位' : '请输入密码'"
          /></label>
          <label v-if="mode === 'register'"
            >确认密码<input
              v-model="confirm"
              required
              type="password"
              autocomplete="new-password"
              placeholder="请再次输入密码"
          /></label>
        </template>
        <p v-if="error" class="error-box" role="alert">{{ error }}</p>
        <button class="primary" :class="{ busy }" :disabled="busy">
          {{
            busy
              ? "处理中…"
              : mode === "login"
                ? "登录"
                : verified
                  ? "注册并登录"
                  : "验证注册码"
          }}
        </button>
        <p class="auth-switch">
          <template v-if="mode === 'login'"
            >还没有账号？<button
              type="button"
              class="text-button"
              @click="switchMode('register')"
            >
              凭注册码注册
            </button></template
          ><template v-else
            >已有账号？<button
              type="button"
              class="text-button"
              @click="switchMode('login')"
            >
              返回登录
            </button></template
          >
        </p>
        <button
          v-if="verified"
          type="button"
          class="text-button"
          @click="
            verified = false;
            grantedRole = null;
            error = '';
          "
        >
          更换注册码
        </button>
        <p class="server mono">{{ origin }}</p>
      </form>
    </div>
  </div>
</template>
