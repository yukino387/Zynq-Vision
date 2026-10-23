<script setup lang="ts">
import { watch, ref } from "vue";
import { useRoute } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { api } from "../api";
import type { Inspection } from "../types";
import AsyncState from "../components/AsyncState.vue";
import InspectionDetail from "../components/InspectionDetail.vue";

/** 详情接口比列表接口多带回 device / station / model 三个关联。 */
type InspectionRecord = Inspection & {
  device?: { name: string } | null;
  station?: { name: string } | null;
  model?: { name: string } | null;
};

const route = useRoute(),
  auth = useAuthStore(),
  inspection = ref<InspectionRecord | null>(null),
  loading = ref(false),
  error = ref("");

/** 详情是独立路由：冷启动直接打这个地址必须能自己取到数据，
 *  不依赖任何列表页留下的状态。 */
async function load() {
  loading.value = true;
  error.value = "";
  try {
    inspection.value = await api<InspectionRecord>(
      `/inspections/${route.params.id}`,
    );
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
watch(() => route.params.id, load, { immediate: true });
async function saved() {
  await load();
}
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>单件详情</h1>
      <p v-if="inspection" :class="{ mono: auth.engineer }">
        {{ new Date(inspection.createdAt).toLocaleString("zh-CN") }}
      </p>
    </div>
    <div class="heading-actions">
      <RouterLink
        :to="{
          name: 'records',
          params: { tab: 'all' },
        }"
        >返回记录列表</RouterLink
      >
    </div>
  </div>

  <AsyncState :loading="loading" :error="error" @retry="load">
    <div v-if="inspection" class="panel panel-body">
      <InspectionDetail
        :key="inspection.id"
        :inspection="inspection"
        @saved="saved"
      />
    </div>
  </AsyncState>
</template>
