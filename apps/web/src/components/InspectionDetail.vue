<script setup lang="ts">
import { chinese, reasonLabel } from "@vision/shared";
import { ref } from "vue";
import type { Inspection } from "../types";
import { post, download } from "../api";
import { useNotificationStore } from "../stores/notifications";
import Status from "./Status.vue";
import ImageViewer from "./ImageViewer.vue";
const props = defineProps<{ inspection: Inspection; queue?: boolean }>();
const emit = defineEmits<{ saved: [next: boolean] }>();
const verdict = ref("CORRECT"),
  note = ref(""),
  hard = ref(false),
  busy = ref(false),
  notices = useNotificationStore();
async function save(next = false) {
  busy.value = true;
  try {
    await post("/reviews", {
      inspectionId: props.inspection.id,
      verdict: verdict.value,
      note: note.value,
      hard: hard.value,
    });
    notices.add("审核已保存");
    emit("saved", next);
  } catch (e) {
    notices.error(e);
  } finally {
    busy.value = false;
  }
}
async function raw() {
  const a = props.inspection.sample.assets.find((a) => a.kind === "RAW");
  if (a)
    try {
      await download(`/assets/${a.id}/content`, "original-frame.raw");
    } catch (e) {
      notices.error(e);
    }
}
</script>
<template>
  <div class="toolbar">
    <span class="muted">设备判定</span
    ><Status :value="inspection.result" /><span
      v-if="inspection.reviews.length"
      class="tag ok"
      >已复核</span
    ><span
      class="tag"
      :class="{ simulated: inspection.source === 'SIMULATION' }"
      >{{ chinese(inspection.source) }}</span
    ><span class="mono"># {{ inspection.id.slice(-10) }}</span
    ><button
      class="right"
      @click="raw"
      :disabled="!inspection.sample.assets.some((a) => a.kind === 'RAW')"
    >
      下载原始数据
    </button>
  </div>
  <div class="inspection-workspace">
    <div>
      <ImageViewer
        :assets="inspection.sample.assets"
        :boxes="inspection.detections"
      />
      <p class="note">{{ reasonLabel(inspection.reason) }}</p>
      <details class="section-space">
        <summary>采集与版本信息</summary>
        <dl class="key-values">
          <dt>帧编号</dt>
          <dd>{{ inspection.frameId ?? "未上报" }}</dd>
          <dt>模型版本</dt>
          <dd>{{ inspection.modelVersion ?? "未上报" }}</dd>
          <dt>方案版本</dt>
          <dd>{{ inspection.planVersion ?? "未上报" }}</dd>
          <dt>固件版本</dt>
          <dd>{{ inspection.firmwareVersion ?? "未上报" }}</dd>
          <dt>推理耗时</dt>
          <dd>
            {{
              inspection.latency === null
                ? "未上报"
                : inspection.latency.toFixed(2) + " ms"
            }}
          </dd>
          <dt>设备编号</dt>
          <dd>{{ inspection.deviceId ?? "—" }}</dd>
          <dt>记录时间</dt>
          <dd>{{ new Date(inspection.createdAt).toLocaleString() }}</dd>
        </dl>
      </details>
    </div>
    <section class="review-panel">
      <h3>人工复核</h3>
      <div class="form-grid">
        <label
          >审核结论<select v-model="verdict">
            <option value="CORRECT">正确</option>
            <option value="FALSE_POSITIVE">误检</option>
            <option value="MISSED">漏检</option>
            <option value="LOW_CONFIDENCE">低置信度</option>
            <option value="LIGHTING">光照异常</option>
            <option value="OCCLUSION">遮挡</option>
            <option value="OTHER">其他</option>
          </select></label
        ><label class="check-row"
          ><input type="checkbox" v-model="hard" />加入困难样本</label
        >
      </div>
      <label>备注<textarea v-model="note" rows="2" maxlength="2000" /></label>
      <div class="form-actions">
        <button
          v-if="queue"
          class="primary"
          @click="save(true)"
          :disabled="busy"
        >
          保存并复核下一件</button
        ><button
          :class="{ primary: !queue }"
          @click="save(false)"
          :disabled="busy"
        >
          保存复核
        </button>
      </div>
      <div v-for="(r, i) in inspection.reviews" :key="i" class="list-line">
        <span>{{ chinese(r.verdict) }}</span
        ><span class="muted">{{ r.note }}</span>
      </div>
    </section>
  </div>
</template>
