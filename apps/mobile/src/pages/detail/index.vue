<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { chinese, displayName, reasonLabel } from "@vision/shared";
import type {
  DetectionBox,
  Source,
  InspectionDecision,
} from "@vision/contracts";
import { request, notify } from "../../state";
import RemoteImage from "../../components/RemoteImage.vue";

interface Inspection {
  id: string;
  batchId?: string | null;
  reviewResult?: string | null;
  metadata?: { decision?: InspectionDecision };
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
  error = ref(""),
  verdict = ref("CORRECT"),
  hard = ref(false),
  note = ref(""),
  busy = ref(false),
  saved = ref(false),
  options = [
    ["CORRECT", "正确"],
    ["FALSE_POSITIVE", "误检"],
    ["MISSED", "漏检"],
    ["LOW_CONFIDENCE", "低置信度"],
    ["LIGHTING", "光照异常"],
    ["OCCLUSION", "遮挡"],
    ["OTHER", "其他"],
  ];
const finalResult = ref("");
const outcomes = [
  { value: "", label: "请选择最终处理结论" },
  { value: "PASS", label: "符合要求" },
  { value: "FAIL", label: "不符合要求" },
  { value: "REVIEW", label: "仍待复核" },
];
const outcomeIndex = computed(() =>
  outcomes.findIndex((o) => o.value === finalResult.value),
);
function selectOutcome(event: unknown) {
  finalResult.value =
    outcomes[
      Number((event as { detail: { value: string } }).detail.value)
    ]!.value;
}
const asset = computed(() =>
  inspection.value?.sample.assets.find((a) => a.kind === "PREVIEW"),
);
const assetWidth = computed(() => asset.value?.width ?? 416);
const assetHeight = computed(() => asset.value?.height ?? 416);

onLoad(async (options) => {
  try {
    inspection.value = await request(
      `/inspections/${String(options?.id ?? "")}`,
    );
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  }
});
function setHard(e: unknown) {
  hard.value = (e as { detail: { value: boolean } }).detail.value;
}
function boxStyle(box: DetectionBox) {
  return {
    left: `${(box.x1 / assetWidth.value) * 100}%`,
    top: `${(box.y1 / assetHeight.value) * 100}%`,
    width: `${((box.x2 - box.x1) / assetWidth.value) * 100}%`,
    height: `${((box.y2 - box.y1) / assetHeight.value) * 100}%`,
  };
}
async function save() {
  if (!inspection.value || busy.value) return;
  error.value = "";
  saved.value = false;
  busy.value = true;
  try {
    await request("/reviews", "POST", {
      inspectionId: inspection.value.id,
      verdict: verdict.value,
      note: note.value,
      hard: hard.value,
      ...(finalResult.value ? { finalResult: finalResult.value } : {}),
    });
    uni.showToast({ title: "审核已保存", icon: "success" });
    saved.value = true;
    if (finalResult.value) inspection.value.reviewResult = finalResult.value;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    notify(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <view class="page">
    <view v-if="error" class="error">{{ error }}</view>
    <template v-if="inspection">
      <view class="result-head">
        <view>
          <text class="eyebrow">检测证据</text>
          <text class="title">{{ chinese(inspection.result) }}</text>
        </view>
        <text v-if="inspection.source === 'SIMULATION'" class="tag"
          >模拟推理</text
        >
      </view>
      <text class="subtitle">{{ reasonLabel(inspection.reason) }}</text>
      <text v-if="inspection.reviewResult" class="subtitle"
        >人工结论：{{ chinese(inspection.reviewResult) }} · 机器原判保留</text
      >

      <view
        class="evidence"
        :style="{ aspectRatio: `${assetWidth} / ${assetHeight}` }"
      >
        <RemoteImage :asset-id="asset?.id" mode="aspectFit" label="无预览图" />
        <view class="box-layer">
          <view
            v-for="(b, i) in inspection.detections"
            :key="i"
            class="det-box"
            :style="boxStyle(b)"
          >
            <text class="det-label"
              >{{ displayName(b.label) }}
              {{ (b.confidence * 100).toFixed(0) }}%</text
            >
          </view>
        </view>
        <text class="evidence-caption mono"
          >{{ assetWidth }} × {{ assetHeight }} ·
          {{ inspection.detections.length }} 个目标</text
        >
      </view>

      <view v-if="inspection.detections.length" class="section-head">
        <text>检出目标</text>
        <text class="mono">{{ inspection.detections.length }}</text>
      </view>
      <view v-if="inspection.detections.length" class="detections">
        <view
          v-for="(b, i) in inspection.detections"
          :key="i"
          class="detection"
        >
          <text class="index mono">{{ String(i + 1).padStart(2, "0") }}</text>
          <view class="det-copy">
            <text>{{ displayName(b.label) }}</text>
            <text class="mono det-pos"
              >{{ Math.round(b.x1) }},{{ Math.round(b.y1) }} →
              {{ Math.round(b.x2) }},{{ Math.round(b.y2) }}</text
            >
          </view>
          <text class="score mono">{{ (b.confidence * 100).toFixed(1) }}%</text>
        </view>
      </view>

      <view v-if="inspection.metadata?.decision?.findings.length" class="card">
        <view
          v-for="finding in inspection.metadata.decision.findings"
          :key="finding.classId"
          class="list-item"
          ><text>{{ finding.label }} · {{ chinese(finding.result) }}</text
          ><text class="muted"
            >要求 {{ finding.min }}–{{ finding.max }} 个，确认
            {{ finding.count }} 个，待确认 {{ finding.uncertain }} 个</text
          ></view
        >
      </view>
      <view class="section-head"><text>运行信息</text></view>
      <view class="card">
        <view class="list-item row"
          ><text class="muted">帧编号</text
          ><text class="mono">{{ inspection.frameId ?? "未上报" }}</text></view
        >
        <view class="list-item row"
          ><text class="muted">模型</text
          ><text class="mono">{{
            inspection.modelVersion ?? "未上报"
          }}</text></view
        >
        <view class="list-item row"
          ><text class="muted">固件</text
          ><text class="mono">{{
            inspection.firmwareVersion ?? "未上报"
          }}</text></view
        >
        <view class="list-item row"
          ><text class="muted">推理耗时</text
          ><text class="mono">{{
            inspection.latency === null ? "未上报" : inspection.latency + " ms"
          }}</text></view
        >
      </view>

      <view class="section-head"><text>人工复核</text></view>
      <view v-if="saved" class="success-note"
        >本次复核已保存，可返回记录继续处理。</view
      >
      <view class="review-options">
        <text
          v-for="o in options"
          :key="o[0]"
          :class="{ selected: verdict === o[0] }"
          @click="verdict = o[0]!"
          >{{ o[1] }}</text
        >
      </view>
      <view class="field row">
        <text style="margin: 0">加入困难样本</text>
        <switch color="#087f82" :checked="hard" @change="setHard" />
      </view>
      <view class="field"
        ><text
          >最终处理结论{{ inspection.batchId ? "（作业记录必选）" : "" }}</text
        ><picker
          :range="outcomes"
          range-key="label"
          :value="outcomeIndex"
          @change="selectOutcome"
          ><view class="card">{{ outcomes[outcomeIndex]!.label }}</view></picker
        ></view
      >
      <textarea v-model="note" placeholder="添加现场备注" maxlength="2000" />
      <button
        class="primary"
        style="margin-top: 18px"
        :loading="busy"
        :disabled="busy || (!!inspection.batchId && !finalResult)"
        @click="save"
      >
        保存审核
      </button>
    </template>
    <view v-else-if="!error" class="empty">读取检测证据…</view>
  </view>
</template>

<style scoped>
.result-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.result-head .title {
  margin-bottom: 0;
}
.evidence {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: #1b1f18;
  border: 1px solid #dce6e9;
  overflow: hidden;
  margin-top: 4px;
}
.box-layer {
  position: absolute;
  inset: 0;
}
.det-box {
  position: absolute;
  border: 2px solid #087f82;
  box-sizing: border-box;
}
.det-label {
  position: absolute;
  left: -2px;
  top: -18px;
  padding: 2px 5px;
  background: #087f82;
  color: #fff8eb;
  font-size: 11px;
  line-height: 14px;
  white-space: nowrap;
}
.evidence-caption {
  position: absolute;
  right: 8px;
  bottom: 7px;
  font-size: 11px;
  color: #f0f8fa;
  background: #102b36ba;
  padding: 2px 5px;
}
.detections {
  border-top: 1px solid #dce6e9;
  border-bottom: 1px solid #dce6e9;
}
.detection {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid #e6edef;
}
.detection:last-child {
  border-bottom: 0;
}
.index {
  font-size: 11px;
  color: #8ca4ad;
}
.det-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}
.det-pos {
  font-size: 11px;
  color: #637d87;
}
.score {
  font-size: 13px;
  color: #8a6a24;
}

.evidence {
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid #dce6e9;
}
.detections {
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid #e4ecef;
  background: white;
}
.det-pos {
  font-size: 11px;
}
.card .list-item .mono {
  text-align: right;
  max-width: 66%;
}
</style>
