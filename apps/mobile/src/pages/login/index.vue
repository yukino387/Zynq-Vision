<script setup lang="ts">
import { ref, watch } from "vue";
import { onShow } from "@dcloudio/uni-app";
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
onShow(() => {
  server.value = session.server;
});
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
  if (busy.value) return;
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
      if (password.value.length < 8) throw new Error("密码至少需要 8 位");
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
    } else {
      if (!username.value.trim() || !password.value)
        throw new Error("请输入账号和密码");
      await login(username.value.trim(), password.value);
    }
    password.value = "";
    uni.switchTab({ url: "/pages/home/index" });
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
      <view class="brand-symbol"><view /></view>
      <text class="kicker">视觉物联网</text>
      <text class="brand-title">视觉采样<text class="brand-dot">.</text></text>
      <text class="brand-note"
        >板端画面、手机原图与检测复核，一台手机完成现场采样。</text
      >
    </view>

    <view class="login-card">
      <view class="mode-head">
        <text class="mode-title">{{
          registering ? (verified ? "创建账号" : "验证注册码") : "现场账号登录"
        }}</text>
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
        <input
          v-model="server"
          aria-label="服务器地址"
          placeholder="http://192.168.1.100:3000"
        />
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
            confirm-type="go"
            @confirm="submit"
            :placeholder="registering ? '至少 8 位密码' : '输入密码'"
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
  background: #102b36;
  color: #f0f8fa;
  padding: env(safe-area-inset-top) 20px 28px;
}
.brand {
  padding: 42px 2px 24px;
}
.kicker {
  display: block;
  font:
    9px Consolas,
    monospace;
  letter-spacing: 2px;
  color: #8db0bd;
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
  color: #f28b61;
}
.brand-note {
  display: block;
  font-size: 12px;
  line-height: 1.8;
  color: #aac6d0;
  max-width: 300px;
}
.login-card {
  background: #ffffff;
  color: #17343e;
  padding: 20px;
  border-radius: 3px;
}
.mode-head {
  border-bottom: 1px solid #dce6e9;
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
  font-size: 11px;
  color: #637d87;
}
.field {
  margin: 14px 0;
}
.field > text {
  display: block;
  font-size: 11px;
  color: #637d87;
  margin-bottom: 7px;
}
.field input {
  height: 46px;
  border-radius: 12px;
  border-color: #dce6e9;
  background: #f7fafb;
  color: #17343e;
  font-size: 14px;
}
.submit {
  width: 100%;
  min-height: 48px;
  margin-top: 8px;
  font-size: 15px;
  border-radius: 12px;
}
.secondary-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: 16px;
  font-size: 11px;
  color: #486571;
}
.foot-note {
  display: block;
  margin-top: 18px;
  font-size: 11px;
  line-height: 1.8;
  color: #8db0bd;
  text-align: center;
}

.login-page {
  background: #102b36;
  padding: calc(env(safe-area-inset-top) + 20px) 24px
    calc(28px + env(safe-area-inset-bottom));
}
.brand {
  padding: 22px 4px 28px;
}
.brand-symbol {
  width: 48px;
  height: 48px;
  border: 2px solid #71ddc8;
  border-radius: 16px;
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 22px;
  transform: rotate(-8deg);
}
.brand-symbol > view {
  width: 18px;
  height: 18px;
  border: 4px solid #71ddc8;
  border-radius: 50%;
}
.kicker {
  color: #8db0bd;
  font-size: 10px;
  letter-spacing: 2px;
}
.brand-title {
  font-size: 36px;
  font-weight: 700;
  margin: 10px 0;
}
.brand-dot {
  color: #71ddc8;
}
.brand-note {
  font-size: 13px;
  color: #aac6d0;
  line-height: 1.8;
}
.login-card {
  border-radius: 22px;
  padding: 24px;
  box-shadow: 0 15px 40px #00000018;
}
.mode-head {
  border: 0;
  margin-bottom: 20px;
  padding-bottom: 0;
}
.mode-title {
  font-size: 21px;
  font-weight: 700;
}
.mode-note {
  font-size: 12px;
  margin-top: 5px;
}
.field {
  margin: 16px 0;
}
.field > text {
  font-size: 12px;
}
.field input {
  border-radius: 12px;
  height: 50px;
  background: #f7fafb;
}
.submit {
  border-radius: 13px;
  margin-top: 22px;
  min-height: 50px;
}
.secondary-actions {
  font-size: 12px;
  flex-wrap: wrap;
  margin-top: 18px;
  gap: 14px;
}
.secondary-actions > text {
  padding: 8px 0;
}
.foot-note {
  color: #8db0bd;
  font-size: 11px;
  margin-top: 22px;
}
</style>
