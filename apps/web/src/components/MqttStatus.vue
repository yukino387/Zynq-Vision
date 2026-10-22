<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { api, RequestError } from "../api";
import Icon from "./Icon.vue";
import Status from "./Status.vue";

interface BridgeStatus {
  config: {
    enabled: boolean;
    host: string;
    port: number;
    tls: boolean;
    prefix: string;
  };
  connected: boolean;
  error: string;
  sessionId: string;
  pendingResults: number;
  actions: { actionId: string; status: string; topic: string }[];
}

const props = withDefaults(
  defineProps<{ deviceId?: string; compact?: boolean }>(),
  { deviceId: "", compact: false },
);

const status = ref<BridgeStatus | null>(null),
  error = ref(""),
  loading = ref(false);
let timer: ReturnType<typeof setInterval> | undefined,
  revision = 0,
  busy = false;

async function load() {
  if (busy || !props.deviceId) return;
  busy = true;
  const current = ++revision;
  loading.value = true;
  try {
    const value = await api<BridgeStatus>(`/devices/${props.deviceId}/mqtt`);
    if (current !== revision) return;
    status.value = value;
    error.value = "";
  } catch (e) {
    if (current !== revision) return;
    status.value = null;
    error.value = e instanceof Error ? e.message : String(e);
    if (e instanceof RequestError && (e.status === 401 || e.status === 403))
      stop();
  } finally {
    busy = false;
    if (current === revision) loading.value = false;
  }
}

function stop() {
  if (timer) clearInterval(timer);
  timer = undefined;
}

function start() {
  stop();
  revision++;
  status.value = null;
  error.value = "";
  if (!props.deviceId) return;
  void load();
  timer = setInterval(() => void load(), 5000);
}

watch(() => props.deviceId, start, { immediate: true });
onBeforeUnmount(stop);

const tone = computed(() => {
  if (error.value) return "OFFLINE";
  if (!status.value) return loading.value ? "CONNECTING" : "UNKNOWN";
  if (!status.value.config.enabled) return "DISABLED";
  if (status.value.connected) return "ONLINE";
  return status.value.error ? "OFFLINE" : "CONNECTING";
});

const label = computed(() => {
  if (error.value) return "MQTT 不可用";
  if (!status.value) return loading.value ? "MQTT 读取中" : "MQTT 未知";
  if (!status.value.config.enabled) return "MQTT 未启用";
  if (status.value.connected) return "MQTT 已连接";
  return status.value.error ? "MQTT 连接失败" : "MQTT 连接中";
});

const broker = computed(() => {
  const config = status.value?.config;
  if (!config?.host) return "未配置 Broker";
  return `${config.tls ? "mqtts" : "mqtt"}://${config.host}:${config.port}`;
});

const lastAction = computed(() => status.value?.actions?.at(-1));
</script>

<template>
  <section
    v-if="deviceId"
    class="mqtt-card"
    :class="[`tone-${tone.toLowerCase()}`, { 'is-compact': compact }]"
    aria-label="MQTT 外设接入"
  >
    <div class="mqtt-card-head">
      <span class="mqtt-icon" aria-hidden="true">
        <Icon name="link" :size="compact ? 14 : 18" />
      </span>
      <strong v-if="!compact">MQTT 外设联动</strong>
      <Status chip :value="tone" :label="label" />
      <span
        v-if="compact && status?.config.host"
        class="mono mqtt-broker"
        :title="broker"
        >{{ broker }}</span
      >
    </div>
    <template v-if="!compact">
      <div class="mqtt-facts">
        <div>
          <small>Broker</small><b class="mono">{{ broker }}</b>
        </div>
        <div>
          <small>Topic 前缀</small
          ><b class="mono">{{ status?.config.prefix || "—" }}</b>
        </div>
        <div>
          <small>待确认结果</small
          ><b class="mono">{{ status?.pendingResults ?? 0 }}</b>
        </div>
        <div v-if="lastAction">
          <small>最近外设动作</small
          ><b class="mono">{{ lastAction.topic }} · {{ lastAction.status }}</b>
        </div>
      </div>
      <p class="mqtt-caption">
        外设通过 MQTT 触发检测、接收 PASS / FAIL 结果并执行现场动作。
      </p>
      <p v-if="error || status?.error" class="mqtt-error" role="alert">
        {{ error || status?.error }}
      </p>
    </template>
  </section>
</template>

<style scoped>
.mqtt-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-left: 4px solid var(--line-strong);
  border-radius: 10px;
}
.mqtt-card.tone-online {
  border-left-color: var(--green);
}
.mqtt-card.tone-connecting {
  border-left-color: var(--amber);
}
.mqtt-card.tone-offline {
  border-left-color: var(--red);
}
.mqtt-card.is-compact {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 4px 9px;
  border: 1px solid var(--line);
  border-left-width: 1px;
  border-radius: 6px;
  background: var(--surface-2);
}
.mqtt-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.mqtt-icon {
  display: inline-flex;
  color: var(--muted);
}
.tone-online .mqtt-icon {
  color: var(--green);
}
.tone-connecting .mqtt-icon {
  color: var(--amber);
}
.tone-offline .mqtt-icon {
  color: var(--red);
}
.mqtt-broker {
  max-width: 240px;
  overflow: hidden;
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.mqtt-facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px 18px;
}
.mqtt-facts small {
  display: block;
  color: var(--muted);
  font-size: 11px;
}
.mqtt-facts b {
  font-size: 12px;
  font-weight: 550;
  overflow-wrap: anywhere;
}
.mqtt-caption {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.mqtt-error {
  margin: 0;
  color: var(--red);
  font-size: 12px;
}
</style>
