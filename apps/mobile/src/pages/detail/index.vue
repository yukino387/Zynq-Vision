<script setup lang="ts">
import { chinese, displayName, reasonLabel } from "@vision/shared";
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import type { DetectionBox, Source } from "@vision/contracts";
import { request, session, notify } from "../../state";
interface Inspection {
  id: string;
  result: string;
  source: Source;
  reason: string;
  frameId: number | null;
  modelVersion: string | null;
  firmwareVersion: string | null;
  latency: number | null;
  sample: {
    assets: {
      id: string;
      kind: string;
      width: number | null;
      height: number | null;
    }[];
  };
  detections: DetectionBox[];
}
const inspection = ref<Inspection | null>(null),
  image = ref(""),
  error = ref(""),
  verdict = ref("CORRECT"),
  hard = ref(false),
  note = ref(""),
  busy = ref(false),
  options = [
    ["CORRECT", "正确"],
    ["FALSE_POSITIVE", "误检"],
    ["MISSED", "漏检"],
    ["LOW_CONFIDENCE", "低置信度"],
    ["LIGHTING", "光照异常"],
    ["OCCLUSION", "遮挡"],
    ["OTHER", "其他"],
  ];
onLoad(async (options) => {
  try {
    inspection.value = await request(
      `/inspections/${String(options?.id ?? "")}`,
    );
    const asset = inspection.value!.sample.assets.find(
      (a) => a.kind === "PREVIEW",
    );
    if (asset) {
      const result = await uni.downloadFile({
        url: `${session.server}/api/assets/${asset.id}/content`,
        header: { authorization: `Bearer ${session.token}` },
      });
      if (result.statusCode === 200) image.value = result.tempFilePath;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  }
});
function setHard(e: unknown) {
  hard.value = (e as { detail: { value: boolean } }).detail.value;
}
async function save() {
  if (!inspection.value) return;
  busy.value = true;
  try {
    await request("/reviews", "POST", {
      inspectionId: inspection.value.id,
      verdict: verdict.value,
      note: note.value,
      hard: hard.value,
    });
    uni.showToast({ title: "审核已保存", icon: "success" });
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <view class="page"
    ><view v-if="error" class="error">{{ error }}</view
    ><template v-if="inspection"
      ><view class="row"
        ><text class="title">{{ chinese(inspection.result) }}</text
        ><text v-if="inspection.source === 'SIMULATION'" class="tag"
          >模拟推理</text
        ></view
      ><text class="subtitle">{{ reasonLabel(inspection.reason) }}</text
      ><view style="position: relative"
        ><image v-if="image" :src="image" class="image" mode="widthFix" /><view
          v-for="(b, i) in inspection.detections"
          :key="i"
          :style="{
            position: 'absolute',
            left: `${(b.x1 / 416) * 100}%`,
            top: `${(b.y1 / 416) * 100}%`,
            width: `${((b.x2 - b.x1) / 416) * 100}%`,
            height: `${((b.y2 - b.y1) / 416) * 100}%`,
            border: '2px solid #1f4d3a',
          }"
          ><text
            style="
              position: absolute;
              top: -20px;
              left: -2px;
              font-size: 10px;
              background: #1f4d3a;
              color: white;
              padding: 3px;
              white-space: nowrap;
            "
            >{{ displayName(b.label) }}
            {{ (b.confidence * 100).toFixed(0) }}%</text
          ></view
        ></view
      ><view class="card" style="margin-top: 20px"
        ><view class="list-item row"
          ><text class="muted">帧编号</text
          ><text class="mono">{{ inspection.frameId ?? "未上报" }}</text></view
        ><view class="list-item row"
          ><text class="muted">模型</text
          ><text class="mono">{{
            inspection.modelVersion ?? "未上报"
          }}</text></view
        ><view class="list-item row"
          ><text class="muted">固件</text
          ><text class="mono">{{
            inspection.firmwareVersion ?? "未上报"
          }}</text></view
        ><view class="list-item row"
          ><text class="muted">推理耗时</text
          ><text class="mono">{{
            inspection.latency === null ? "未上报" : inspection.latency + " ms"
          }}</text></view
        ></view
      ><view class="section-head"><text>人工复核</text></view
      ><view class="review-options"
        ><text
          v-for="o in options"
          :key="o[0]"
          :class="{ selected: verdict === o[0] }"
          @click="verdict = o[0]!"
          >{{ o[1] }}</text
        ></view
      ><view class="field row"
        ><text style="margin: 0">加入困难样本</text
        ><switch color="#1f4d3a" :checked="hard" @change="setHard" /></view
      ><textarea
        v-model="note"
        placeholder="添加现场备注"
        maxlength="2000"
      /><button
        class="primary"
        style="margin-top: 18px"
        :loading="busy"
        :disabled="busy"
        @click="save"
      >
        保存审核
      </button></template
    ><view v-else-if="!error" class="empty">读取检测证据…</view></view
  >
</template>
