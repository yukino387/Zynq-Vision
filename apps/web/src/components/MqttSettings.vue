<script setup lang="ts">
import { computed, onUnmounted, ref } from "vue";
import { mqttConfigSchema, type MqttConfig } from "@vision/contracts";
import { api, post } from "../api";
import { useAuthStore } from "../stores/auth";
const props = defineProps<{ deviceId: string }>();
const auth = useAuthStore();
type BridgeStatus = {
  config: MqttConfig & { hasPassword?: boolean };
  connected: boolean;
  error: string;
  sessionId: string;
  pendingResults: number;
  topics: Record<string, string>;
  actions: { actionId: string; status: string; topic: string }[];
  commands: { requestId: string; status: string }[];
};
const config = ref(mqttConfigSchema.parse({})),
  status = ref<BridgeStatus | null>(null);
const advanced = ref(""),
  broker = ref(""),
  password = ref(""),
  error = ref(""),
  loadError = ref(""),
  saving = ref(false),
  message = ref("");
let timer: ReturnType<typeof setInterval> | undefined;
const connection = computed(() =>
  !status.value?.config.enabled
    ? "未启用"
    : status.value.connected
      ? "已连接"
      : "连接中",
);
async function load(updateConfig = true) {
  try {
    const value = await api<BridgeStatus>(`/devices/${props.deviceId}/mqtt`);
    status.value = value;
    loadError.value = "";
    if (updateConfig) {
      const { hasPassword: _hasPassword, ...configuration } = value.config;
      config.value = mqttConfigSchema.parse(configuration);
      broker.value = config.value.host
        ? `${config.value.tls ? "mqtts" : "mqtt"}://${config.value.host}:${config.value.port}`
        : "";
      advanced.value = JSON.stringify(
        {
          topics: config.value.topics,
          input: config.value.input,
          rules: config.value.rules,
        },
        null,
        2,
      );
    }
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : String(e);
  }
}
async function save(enabled = true) {
  saving.value = true;
  message.value = "";
  try {
    const connection = enabled
      ? new URL(
          broker.value.includes("://")
            ? broker.value
            : `mqtt://${broker.value}`,
        )
      : null;
    if (connection && !["mqtt:", "mqtts:"].includes(connection.protocol))
      throw new Error("连接地址请使用 mqtt:// 或 mqtts://");
    if (
      connection &&
      (connection.username ||
        connection.password ||
        (connection.pathname && connection.pathname !== "/") ||
        connection.search ||
        connection.hash)
    )
      throw new Error("连接地址只填写主机与端口，账号在高级设置中填写");
    const { hasPassword: _storedPassword, ...stored } = status.value!.config;
    const document = mqttConfigSchema.parse(
      enabled
        ? {
            ...config.value,
            ...JSON.parse(advanced.value),
            enabled,
            ...(connection
              ? {
                  host: connection.hostname,
                  port: Number(
                    connection.port ||
                      (connection.protocol === "mqtts:" ? 8883 : 1883),
                  ),
                  tls: connection.protocol === "mqtts:",
                }
              : {}),
            ...(password.value ? { password: password.value } : {}),
          }
        : { ...stored, enabled: false },
    );
    status.value = await post<BridgeStatus>(
      `/devices/${props.deviceId}/mqtt`,
      document,
    );
    const { hasPassword: _hasPassword, ...configuration } = status.value.config;
    config.value = mqttConfigSchema.parse(configuration);
    password.value = "";
    error.value = "";
    message.value = enabled ? "配置已保存，正在连接" : "MQTT 已停用";
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    saving.value = false;
  }
}
function exampleRule() {
  try {
    const document = JSON.parse(advanced.value);
    if (document.rules.some((rule: { id: string }) => rule.id === "reject"))
      return;
    document.rules.push({
      id: "reject",
      when: "FAIL",
      topic: "devices/rejector-1/command",
      payload: {
        command: "REJECT",
        actionId: "${actionId}",
        pieceId: "${pieceId}",
      },
      ackTopic: "devices/rejector-1/reply",
      timeoutMs: 2000,
      expiryMs: 2000,
    });
    advanced.value = JSON.stringify(document, null, 2);
  } catch (e) {
    error.value = String(e);
  }
}
const example = computed(() =>
  JSON.stringify(
    {
      type: "TRIGGER",
      requestId: crypto.randomUUID(),
      pieceId: "P0001",
      sessionId: status.value?.sessionId,
      windowMs: 500,
    },
    null,
    2,
  ),
);
function toggle(event: Event) {
  clearInterval(timer);
  if (!(event.target as HTMLDetailsElement).open) return;
  void load(!status.value);
  timer = setInterval(() => void load(false), 5000);
}
onUnmounted(() => clearInterval(timer));
</script>

<template>
  <details class="section-space" @toggle="toggle">
    <summary>
      MQTT 接入<span v-if="status"> · {{ connection }}</span>
    </summary>
    <p>连接后自动接收检测指令，发布状态与结果。</p>
    <p v-if="error || loadError" role="alert" class="error">
      {{ error || loadError }}
      <button v-if="!status" type="button" @click="load()">重试</button>
    </p>
    <p v-if="status?.error" role="alert">{{ status.error }}</p>
    <form @submit.prevent="save(true)">
      <fieldset :disabled="!auth.admin || saving || !status">
        <div class="mqtt-grid">
          <label
            >连接地址<input
              v-model.trim="broker"
              placeholder="mqtt://192.168.1.10:1883"
              required
          /></label>
          <label>Topic 前缀<input v-model="config.prefix" required /></label>
        </div>
        <details>
          <summary>高级设置</summary>
          <div class="mqtt-grid section-space">
            <label>客户端 ID<input v-model="config.clientId" required /></label>
            <label
              >用户名<input v-model="config.username" autocomplete="off"
            /></label>
            <label
              >密码<input
                v-model="password"
                type="password"
                autocomplete="new-password"
                :placeholder="
                  status?.config.hasPassword ? '已保存；留空保持' : '未设置'
                "
            /></label>
          </div>
          <label
            >Topic、输入字段与输出规则（JSON）<textarea
              v-model="advanced"
              rows="12"
              spellcheck="false"
            />
          </label>
          <p class="note">
            留空的 Topic 使用前缀加
            command/reply/state/result/event。外设输出支持
            ${actionId}、${pieceId}、${result} 和 ${findings} 等字段。
          </p>
          <button type="button" @click="exampleRule">添加不合格输出示例</button>
        </details>
        <div v-if="auth.admin" class="toolbar section-space">
          <button class="primary">
            {{
              saving
                ? "保存中…"
                : status?.config.enabled
                  ? "保存连接"
                  : "保存并连接"
            }}
          </button>
          <button
            v-if="status?.config.enabled"
            type="button"
            @click="save(false)"
          >
            停用
          </button>
        </div>
      </fieldset>
    </form>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="status?.pendingResults">
      待确认结果 {{ status.pendingResults }} 条
    </p>
    <details v-if="status" class="section-space">
      <summary>联调信息</summary>
      <pre>{{ example }}</pre>
      <p class="note">
        触发前读取 state 的 sessionId。requestId 为
        UUID；相同编号重试不会重复检测。外设以 actionId 回报 EXECUTED 或
        FAILED。ACK_RESULT 使用 resultId 确认收到结果。
      </p>
      <dl v-if="status">
        <template v-for="(value, name) in status.topics" :key="name"
          ><dt>{{ name }}</dt>
          <dd class="mono">{{ value }}</dd></template
        >
      </dl>
      <p v-for="action in status?.actions" :key="action.actionId">
        {{ action.topic }} · {{ action.status }}
      </p>
    </details>
  </details>
</template>

<style scoped>
.mqtt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
}
label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 10px;
}
textarea,
pre {
  font-family: monospace;
  width: 100%;
  box-sizing: border-box;
}
dd {
  overflow-wrap: anywhere;
  margin: 0 0 8px;
}
@media (max-width: 600px) {
  .mqtt-grid {
    grid-template-columns: 1fr;
  }
}
</style>
