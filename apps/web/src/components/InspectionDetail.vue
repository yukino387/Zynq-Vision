<script setup lang="ts">
import { chinese, reasonLabel } from "@vision/shared";
import { ref, computed } from "vue";
import type { Inspection } from "../types";
import { post, download } from "../api";
import { useNotificationStore } from "../stores/notifications";
import { useAuthStore } from "../stores/auth";
import Status from "./Status.vue";
import ImageViewer from "./ImageViewer.vue";
const props = defineProps<{ inspection: Inspection; queue?: boolean }>();
const emit = defineEmits<{ saved: [next: boolean] }>();
const auth = useAuthStore(),
  notices = useNotificationStore();
const verdict = ref(""),
  note = ref(""),
  hard = ref(false),
  busy = ref(false),
  appending = ref(false);
const finalResult = ref("");
const decision = computed(() => props.inspection.metadata?.decision);
const positionedRegions = computed(() => {
  const rules = props.inspection.metadata?.snapshot?.rules;
  return (rules?.checks ?? []).flatMap((check) =>
    check.region
      ? [{ ...check.region, label: rules!.classes[check.classId]! }]
      : [],
  );
});
const resolved = computed(() =>
  props.inspection.reviews.find((r) => r.finalResult),
);
const reviewed = computed(() => props.inspection.reviews.length > 0);
const showForm = computed(() => !reviewed.value || appending.value);
const verdicts = computed<[string, string][]>(() =>
  auth.engineer
    ? [
        ["CORRECT", "正确"],
        ["FALSE_POSITIVE", "误检"],
        ["MISSED", "漏检"],
        ["LOW_CONFIDENCE", "低置信度"],
        ["LIGHTING", "光照异常"],
        ["OCCLUSION", "遮挡"],
        ["OTHER", "其他"],
      ]
    : [
        ["CORRECT", "正确"],
        ["FALSE_POSITIVE", "误检"],
        ["MISSED", "漏检"],
        ["OTHER", "其他"],
      ],
);
async function save(next = false) {
  if (!verdict.value || busy.value) return;
  busy.value = true;
  try {
    await post("/reviews", {
      inspectionId: props.inspection.id,
      verdict: verdict.value,
      note: note.value,
      hard: hard.value,
      ...(finalResult.value ? { finalResult: finalResult.value } : {}),
    });
    notices.add(
      reviewed.value
        ? "追加意见已提交"
        : "复核意见已提交；样本取舍与标注在样本库处理",
    );
    const advance =
      next && !!finalResult.value && finalResult.value !== "REVIEW";
    appending.value = false;
    verdict.value = "";
    note.value = "";
    finalResult.value = "";
    emit("saved", advance);
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
    <span class="muted">机器原判</span
    ><Status :value="inspection.metadata?.localResult || inspection.result" />
    <span class="muted">平台核验</span
    ><Status :value="inspection.result" /><span
      v-if="inspection.reviews.length"
      class="tag ok"
      >已提交复核意见</span
    ><span v-if="inspection.source === 'SIMULATION'" class="tag simulated"
      >模拟数据</span
    ><template v-if="auth.engineer"
      ><button
        class="right"
        @click="raw"
        :disabled="!inspection.sample.assets.some((a) => a.kind === 'RAW')"
      >
        下载原始数据
      </button></template
    >
  </div>
  <div class="inspection-workspace">
    <div>
      <ImageViewer
        :operator="!auth.engineer"
        :assets="inspection.sample.assets"
        :boxes="inspection.detections"
        :region="inspection.metadata?.snapshot?.rules.region"
        :regions="positionedRegions"
        :postprocess="inspection.metadata?.postprocess"
      />
      <p class="note">{{ reasonLabel(inspection.reason) }}</p>
      <RouterLink
        v-if="auth.engineer"
        :to="{
          name: 'data',
          params: { tab: 'annotation' },
          query: { sampleId: inspection.sampleId },
        }"
        >用本件证据继续标注与训练</RouterLink
      >
      <div v-if="decision?.findings.length" class="table-wrap">
        <table aria-label="逐项判定依据">
          <thead>
            <tr>
              <th>检查项</th>
              <th>要求数量</th>
              <th>确认数量</th>
              <th>待确认</th>
              <th>判定</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="finding in decision.findings" :key="finding.classId">
              <td>{{ finding.label }}</td>
              <td>
                {{
                  finding.min === finding.max
                    ? finding.min
                    : `${finding.min}–${finding.max}`
                }}
              </td>
              <td>{{ finding.count }}</td>
              <td>{{ finding.uncertain }}</td>
              <td><Status :value="finding.result" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="note">
        机器原判保留。人工最终结论：<Status
          v-if="resolved?.finalResult"
          :value="resolved.finalResult"
        /><span v-else>尚未给出</span>
      </p>
      <details v-if="auth.engineer" class="section-space">
        <summary>技术信息</summary>
        <dl class="key-values">
          <dt>检测记录编号</dt>
          <dd>{{ inspection.id }}</dd>
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
          <dd>{{ inspection.deviceId ?? "未关联设备" }}</dd>
          <dt>记录时间</dt>
          <dd>{{ new Date(inspection.createdAt).toLocaleString() }}</dd>
        </dl>
      </details>
      <p v-else class="note">
        记录时间：{{ new Date(inspection.createdAt).toLocaleString() }}
      </p>
    </div>
    <section class="review-panel">
      <h3>人工复核</h3>
      <template v-if="reviewed && !showForm">
        <p class="note">
          此记录已提交复核意见。如需补充说明，请点击“追加意见”。
        </p>
        <div v-for="(r, i) in inspection.reviews" :key="i" class="list-line">
          <span>{{ chinese(r.verdict) }}</span
          ><span class="muted">{{ r.note }}</span>
        </div>
        <div class="form-actions">
          <button @click="appending = true">追加意见</button>
        </div>
      </template>
      <template v-else>
        <label
          >最终处理结论<UiSelect
            v-model="finalResult"
            aria-label="最终处理结论"
          >
            <option value="">仅追加意见，保持原处理状态</option>
            <option value="PASS">符合要求</option>
            <option value="FAIL">不符合要求</option>
            <option value="REVIEW">仍待复核</option>
          </UiSelect></label
        >
        <div class="form-grid">
          <label
            >审核结论<UiSelect v-model="verdict">
              <option value="" disabled>请选择</option>
              <option
                v-for="[value, label] in verdicts"
                :key="value"
                :value="value"
              >
                {{ label }}
              </option>
            </UiSelect></label
          ><label v-if="auth.engineer" class="check-row"
            ><input type="checkbox" v-model="hard" />加入困难样本</label
          >
        </div>
        <label>备注<textarea v-model="note" rows="2" maxlength="2000" /></label>
        <div class="form-actions">
          <button
            class="primary"
            @click="save(queue)"
            :disabled="busy || !verdict"
          >
            {{
              queue
                ? "提交并查看下一件"
                : reviewed
                  ? "提交追加意见"
                  : "提交复核意见"
            }}
          </button>
        </div>
      </template>
    </section>
  </div>
</template>
