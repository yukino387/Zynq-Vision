<script setup lang="ts">
import { ref, watch } from "vue";
import { session, login, register, request, setServer } from "../../state";
const server = ref(session.server),
  username = ref(""),
  password = ref(""),
  busy = ref(false),
  error = ref("");
const registering = ref(false),
  verified = ref(false),
  code = ref(""),
  name = ref(""),
  confirm = ref("");
watch(server, () => {
  verified.value = false;
});
function switchMode() {
  registering.value = !registering.value;
  verified.value = false;
  error.value = "";
  password.value = "";
  confirm.value = "";
}
async function submit() {
  busy.value = true;
  error.value = "";
  try {
    setServer(server.value);
    if (registering.value && !verified.value) {
      await request("/auth/registration/verify", "POST", { code: code.value });
      verified.value = true;
      return;
    }
    if (registering.value) {
      if (password.value.length < 12) throw new Error("密码至少需要 12 位");
      if (!/^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,39}$/.test(username.value))
        throw new Error("账号应为 3 至 40 位字母、数字或下划线等字符");
      if (password.value !== confirm.value)
        throw new Error("两次输入的密码不一致");
      if (!name.value.trim()) throw new Error("请输入姓名");
      await register({
        code: code.value,
        name: name.value,
        username: username.value,
        password: password.value,
      });
    } else await login(username.value, password.value);
    password.value = "";
    uni.switchTab({ url: "/pages/capture/index" });
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <view class="login-page">
    <view class="brand">
      <text class="kicker">视觉物联网 / FIELD</text>
      <text class="brand-title">视觉采样<span>.</span></text>
      <text class="brand-note"
        >板端画面、手机原图与检测复核，一台手机完成现场采样。</text
      >
    </view>

    <view class="login-card">
      <view class="mode-head">
        <text class="mode-title">{{
          registering
            ? verified
              ? "创建账号"
              : "验证注册码"
            : "现场账号登录"
        }}</text
        >
        <text class="mode-note">{{
          registering
            ? verified
              ? "填写姓名与账号信息"
              : "注册码由管理员签发"
            : "登录后自动连接实时画面"
        }}</text>
      </view>

      <view class="field">
        <text>服务器地址</text>
        <input v-model="server" placeholder="http://服务器地址:3000" />
      </view>
      <view v-if="registering && !verified" class="field">
        <text>注册码</text>
        <input v-model="code" aria-label="注册码" placeholder="请输入注册码" />
      </view>
      <template v-else>
        <view v-if="registering" class="field">
          <text>姓名</text>
          <input v-model="name" aria-label="姓名" placeholder="请输入姓名" />
        </view>
        <view class="field">
          <text>账号</text>
          <input
            v-model="username"
            aria-label="账号"
            placeholder="请输入账号"
          />
        </view>
        <view class="field">
          <text>密码</text>
          <input
            v-model="password"
            aria-label="密码"
            password
            :placeholder="registering ? '至少 12 位密码' : '输入密码'"
          />
        </view>
        <view v-if="registering" class="field">
          <text>确认密码</text>
          <input
            v-model="confirm"
            aria-label="确认密码"
            password
            placeholder="请再次输入密码"
          />
        </view>
      </template>

      <view v-if="error" class="error">{{ error }}</view>
      <button
        class="primary submit"
        :loading="busy"
        :disabled="busy"
        @click="submit"
      >
        {{ registering ? (verified ? "注册并登录" : "验证注册码") : "登录" }}
      </button>
      <view class="secondary-actions">
        <text @click="switchMode">{{
          registering ? "返回登录" : "凭注册码注册"
        }}</text>
        <text @click="uni.navigateTo({ url: '/pages/pair/index' })"
          >扫码配对服务器</text
        >
      </view>
    </view>

    <text class="foot-note"
      >手机与服务器需处于同一局域网。实时画面来自已连接设备。</text
    >
  </view>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: #161a12;
  color: #eef1e6;
  padding: env(safe-area-inset-top) 20px 28px;
}
.brand {
  padding: 42px 2px 24px;
}
.kicker {
  display: block;
  font: 9px Consolas, monospace;
  letter-spacing: 2px;
  color: #93a08a;
  margin-bottom: 8px;
}
.brand-title {
  display: block;
  font-size: 38px;
  font-weight: 600;
  letter-spacing: -1.5px;
  line-height: 1.1;
  margin-bottom: 12px;
}
.brand-title span {
  color: #ee743d;
}
.brand-note {
  display: block;
  font-size: 12px;
  line-height: 1.8;
  color: #aab6a0;
  max-width: 300px;
}
.login-card {
  background: #f1f0e8;
  color: #2c3326;
  padding: 20px;
  border-radius: 3px;
}
.mode-head {
  border-bottom: 1px solid #c9cebf;
  padding-bottom: 13px;
  margin-bottom: 6px;
}
.mode-title {
  display: block;
  font-size: 19px;
  font-weight: 600;
  margin-bottom: 4px;
}
.mode-note {
  display: block;
  font-size: 10px;
  color: #707c63;
}
.field {
  margin: 14px 0;
}
.field > text {
  display: block;
  font-size: 10px;
  color: #707c63;
  margin-bottom: 7px;
}
.field input {
  height: 46px;
  border-radius: 2px;
  border-color: #b8bfaa;
  background: #fbfaf3;
  color: #2c3326;
  font-size: 14px;
}
.submit {
  width: 100%;
  min-height: 48px;
  margin-top: 8px;
  font-size: 15px;
  border-radius: 2px;
}
.secondary-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: 16px;
  font-size: 11px;
  color: #4d5b3f;
}
.foot-note {
  display: block;
  margin-top: 18px;
  font-size: 10px;
  line-height: 1.8;
  color: #7d8a74;
  text-align: center;
}
</style>
