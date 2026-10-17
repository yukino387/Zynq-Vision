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
  <view class="page"
    ><text class="title" style="font-size: 34px; margin-top: 24px"
      >视觉采样</text
    ><text class="subtitle">{{
      registering
        ? verified
          ? "创建账号"
          : "验证管理员签发的注册码"
        : "账号登录"
    }}</text
    ><view class="field"
      ><text>服务器地址</text
      ><input v-model="server" placeholder="http://服务器地址:3000" /></view
    ><view v-if="registering && !verified" class="field"
      ><text>注册码</text
      ><input
        v-model="code"
        aria-label="注册码"
        placeholder="请输入注册码" /></view
    ><template v-else
      ><view v-if="registering" class="field"
        ><text>姓名</text
        ><input
          v-model="name"
          aria-label="姓名"
          placeholder="请输入姓名" /></view
      ><view class="field"
        ><text>账号</text
        ><input
          v-model="username"
          aria-label="账号"
          placeholder="请输入账号" /></view
      ><view class="field"
        ><text>密码</text
        ><input
          v-model="password"
          aria-label="密码"
          password
          :placeholder="registering ? '至少 12 位密码' : '输入密码'" /></view
      ><view v-if="registering" class="field"
        ><text>确认密码</text
        ><input
          v-model="confirm"
          aria-label="确认密码"
          password
          placeholder="请再次输入密码" /></view></template
    ><view v-if="error" class="error">{{ error }}</view
    ><button class="primary" :loading="busy" :disabled="busy" @click="submit">
      {{
        registering ? (verified ? "注册并登录" : "验证注册码") : "登录"
      }}</button
    ><button style="margin-top: 12px" @click="switchMode">
      {{ registering ? "返回登录" : "凭注册码注册" }}</button
    ><button
      style="margin-top: 12px"
      @click="uni.navigateTo({ url: '/pages/pair/index' })"
    >
      扫码 / 手动配对
    </button></view
  >
</template>
