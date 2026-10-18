<script setup lang="ts">
import { ref } from "vue";
import { request, setServer, session, notify } from "../../state";
const content = ref(""),
  server = ref(session.server),
  status = ref(""),
  paired = ref(false),
  busy = ref(false);
async function scan() {
  try {
    const result = await uni.scanCode({ scanType: ["qrCode"] });
    content.value = result.result;
    await pair();
  } catch {
    status.value = "扫码未完成，请重试或粘贴配对内容。";
  }
}
async function pair() {
  if (busy.value) return;
  busy.value = true;
  paired.value = false;
  status.value = "";
  try {
    const payload = JSON.parse(content.value) as {
      serverUrl: string;
      pairingToken?: string;
      expiry?: string;
      protocolVersion?: number;
      stationId?: string;
      type?: "STATION" | "DEVICE";
      deviceId?: string;
      defaultDeviceId?: string;
    };
    if (
      payload.protocolVersion === 1 &&
      ["STATION", "DEVICE"].includes(payload.type ?? "")
    ) {
      if (payload.type === "STATION" && !payload.stationId)
        throw new Error("无效工位二维码");
      if (payload.type === "DEVICE" && !payload.deviceId)
        throw new Error("无效设备二维码");
      if (payload.serverUrl) setServer(payload.serverUrl);
      session.stationId = payload.stationId ?? session.stationId;
      session.deviceId = payload.deviceId ?? payload.defaultDeviceId ?? "";
      uni.setStorageSync("vision.station", session.stationId);
      uni.setStorageSync("vision.device", session.deviceId);
      status.value = "工位/设备已选择。登录后会按权限访问服务器。";
      server.value = session.server;
      paired.value = true;
      return;
    }
    if (
      payload.protocolVersion !== 1 ||
      !payload.pairingToken ||
      !/^https?:\/\//.test(payload.serverUrl)
    )
      throw new Error("无效配对内容");
    if (
      payload.expiry &&
      (!Number.isFinite(Date.parse(payload.expiry)) ||
        Date.parse(payload.expiry) < Date.now())
    )
      throw new Error("配对码已过期");
    setServer(payload.serverUrl);
    const result = await request<{ stationId: string | null }>(
      "/system/pairing/redeem",
      "POST",
      { token: payload.pairingToken },
    );
    session.stationId = result.stationId ?? "";
    uni.setStorageSync("vision.station", session.stationId);
    server.value = session.server;
    status.value = "配对成功。请使用现场账号登录。";
    paired.value = true;
  } catch (e) {
    status.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    busy.value = false;
  }
}
function manual() {
  try {
    setServer(server.value);
    if (session.token) uni.switchTab({ url: "/pages/home/index" });
    else uni.redirectTo({ url: "/pages/login/index" });
  } catch (error) {
    notify(error);
  }
}
</script>
<template>
  <view class="page">
    <text class="eyebrow">连接现场 / CONNECT</text>
    <text class="title">连接你的工作空间</text>
    <text class="subtitle"
      >扫描服务器或工位的二维码，让采样与现场保持同步。</text
    >
    <view class="card scan-card">
      <view class="scan-symbol"><view /></view>
      <text class="scan-title">扫码，一步连接</text>
      <text class="note"
        >在 Web 端「系统 → 移动端配对」生成二维码；连接服务器码 5
        分钟内有效，工位/设备码用于快捷选择。</text
      >
      <button class="primary" @click="scan" :loading="busy" :disabled="busy">
        扫描配对码
      </button>
    </view>
    <view v-if="status" :class="paired ? 'success-note' : 'error'">{{
      status
    }}</view>
    <view class="section-head"
      ><text>手动连接</text><text class="muted">同一局域网</text></view
    >
    <view class="card">
      <view class="field"
        ><text>服务器地址</text
        ><input
          v-model="server"
          aria-label="服务器地址"
          placeholder="http://192.168.1.100:3000"
      /></view>
      <button class="primary" @click="manual">
        {{ session.token ? "返回工作台" : "保存并前往登录" }}
      </button>
    </view>
    <view class="section-head"
      ><text>粘贴配对内容</text><text class="muted">无法扫码时使用</text></view
    >
    <view class="card">
      <textarea v-model="content" placeholder="粘贴完整的配对信息" />
      <button
        class="verify"
        @click="pair"
        :loading="busy"
        :disabled="busy || !content.trim()"
      >
        验证配对内容
      </button>
    </view>
  </view>
</template>
<style scoped>
.scan-card {
  padding: 28px 22px;
  text-align: center;
  background: #edf7f6;
  border-color: #d5eae7;
}
.scan-symbol {
  width: 66px;
  height: 66px;
  border: 2px solid #087f82;
  border-radius: 20px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.scan-symbol > view {
  width: 28px;
  height: 28px;
  border: 6px solid #087f82;
  border-radius: 8px;
}
.scan-title {
  display: block;
  font-size: 19px;
  font-weight: 650;
}
.scan-card .note {
  margin: 10px 0 22px;
}
.card .field {
  margin-top: 0;
}
.verify {
  margin-top: 14px;
}
</style>
