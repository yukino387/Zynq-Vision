<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useProductStore } from "../stores/product";
const route = useRoute(),
  router = useRouter(),
  product = useProductStore();
const loadError = ref("");
const error = computed(
  () =>
    loadError.value || (product.id && !product.current ? "正在读取产品…" : ""),
);
async function refresh() {
  try {
    await product.load();
    loadError.value = "";
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : String(e);
  }
}
watch(() => route.name, refresh, { immediate: true });
watch(
  () => route.query.planId,
  (id) => {
    if (typeof id === "string") product.select(id);
  },
  { immediate: true },
);
function select(event: Event) {
  product.select((event.target as HTMLSelectElement).value);
  void router.replace({
    query: { ...route.query, planId: product.id || undefined },
  });
}
const steps = [
  { label: "1 产品规则", name: "plans", tab: undefined },
  { label: "2 应用并检测", name: "models", tab: "deployments" },
];
</script>
<template>
  <section class="product-workflow" aria-label="产品准备流程">
    <label
      >准备产品<UiSelect
        aria-label="当前准备产品"
        :model-value="product.id"
        size="sm"
        @change="select"
      >
        <option value="">请选择产品</option>
        <option v-for="plan in product.plans" :key="plan.id" :value="plan.id">
          {{ plan.rules.product }} · V{{ plan.version }}
        </option>
      </UiSelect></label
    >
    <nav aria-label="操作步骤">
      <RouterLink
        v-for="step in steps"
        :key="step.label"
        :to="{
          name: step.name,
          params: step.tab ? { tab: step.tab } : {},
          query: { planId: product.id || undefined },
        }"
        :aria-current="
          route.name === step.name &&
          (!step.tab || route.params.tab === step.tab)
            ? 'step'
            : undefined
        "
        >{{ step.label }}</RouterLink
      >
    </nav>
    <details>
      <summary>需要补充样本或模型？</summary>
      <nav aria-label="样本与模型准备">
        <RouterLink
          :to="{
            name: 'data',
            params: { tab: 'annotation' },
            query: { planId: product.id || undefined },
          }"
          >样本标注</RouterLink
        >
        <RouterLink
          :to="{
            name: 'models',
            params: { tab: 'training' },
            query: { planId: product.id || undefined },
          }"
          >训练模型</RouterLink
        >
      </nav>
    </details>
    <small v-if="error" role="status"
      >{{ error }}
      <button v-if="loadError" type="button" @click="refresh">
        重试
      </button></small
    >
  </section>
</template>
<style scoped>
.product-workflow {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
  padding: 14px 18px;
  margin: 0 0 20px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
}
label,
nav {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
label {
  font-size: 13px;
}
.ui-select {
  max-width: 300px;
}
nav a {
  font-size: 13px;
  padding: 7px 9px;
  text-decoration: none;
  color: var(--muted);
}
nav a[aria-current] {
  color: var(--forest);
  background: var(--surface-2);
  border-radius: 6px;
  font-weight: 600;
}
</style>
