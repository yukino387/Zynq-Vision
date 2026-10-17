<script setup lang="ts">
import { ref } from "vue";
import { request, setServer, session, notify } from "../../state";
const content = ref(""),
  server = ref(session.server),
  status = ref(""),
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
  busy.value = true;
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
      session.stationId = payload.stationId ?? session.stationId;
      session.deviceId = payload.deviceId ?? payload.defaultDeviceId ?? "";
      uni.setStorageSync("vision.station", session.stationId);
      uni.setStorageSync("vision.device", session.deviceId);
      status.value = "工位/设备已选择。登录后会按权限访问服务器。";
      return;
    }
    if (
      payload.protocolVersion !== 1 ||
      !payload.pairingToken ||
      !/^https?:\/\//.test(payload.serverUrl)
    )
      throw new Error("无效配对内容");
    if (payload.expiry && Date.parse(payload.expiry) < Date.now())
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
  } catch (e) {
    status.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    busy.value = false;
  }
}
function manual() {
  if (!/^https?:\/\//.test(server.value)) {
    notify(new Error("输入有效的 http(s) 服务器地址"));
    return;
  }
  setServer(server.value);
  uni.navigateTo({ url: "/pages/login/index" });
}
</script>
<template>
  <view class="page"
    ><text class="title">服务器与工位配对</text
    ><text class="subtitle">在 Web 端「系统 移动端配对」生成一次性二维码。</text
    ><view class="card" style="padding: 40px; text-align: center"
      ><button class="primary" @click="scan" :loading="busy" :disabled="busy">
        扫描配对码
      </button></view
    ><view class="field"
      ><text>或粘贴配对内容</text
      ><textarea v-model="content" placeholder="粘贴配对信息" /></view
    ><button @click="pair" :loading="busy" :disabled="busy || !content">
        验证配对
      </button
    ><text v-if="status" class="note">{{ status }}</text
    ><view class="field"
      ><text>仅设置服务器地址</text
      ><input v-model="server" placeholder="http://服务器地址:3000" /></view
    ><button @click="manual">前往登录</button
    ><text class="note">服务器配对码 5 分钟内有效。</text></view
  >
</template>
