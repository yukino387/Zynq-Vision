<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
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
  error = ref(""),
  busy = ref(false);
const heading = computed(() =>
  mode.value === "login"
    ? "登录账号"
    : verified.value
      ? "创建账号"
      : "验证注册码",
);
function switchMode(next: "login" | "register") {
  mode.value = next;
  error.value = "";
  password.value = "";
  confirm.value = "";
  verified.value = false;
}
async function submit() {
  busy.value = true;
  error.value = "";
  try {
    if (mode.value === "register" && !verified.value) {
      await post("/auth/registration/verify", { code: code.value });
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
      <span class="workspace-index">边缘视觉 / 设备工作站</span>
      <h2>看见细节。<br />作出判断<span>.</span></h2>
      <div class="auth-instrument">
        <span>产品方案</span><span>引导采样</span><span>审核发布</span>
      </div>
      <small>视觉物联网平台</small>
    </section>
    <div class="auth-wrap">
      <div class="auth-product">视觉物联网平台</div>
      <form class="login-form" @submit.prevent="submit">
        <h1>{{ heading }}</h1>
        <p class="muted auth-caption">
          {{
            mode === "login"
              ? "欢迎回来，请登录以继续工作"
              : verified
                ? "注册码已验证，填写账号信息即可加入"
                : "请输入管理员提供的一次性注册码"
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
              :minlength="mode === 'register' ? 12 : undefined"
              maxlength="100"
              :placeholder="mode === 'register' ? '至少 12 位' : '请输入密码'"
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
