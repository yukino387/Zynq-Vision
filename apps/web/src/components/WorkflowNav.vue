<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
const route = useRoute();
const steps = [
  { label: "样本", to: "/data/samples" },
  { label: "标注", to: "/data/annotation" },
  { label: "数据集", to: "/data/datasets" },
  { label: "训练", to: "/models/training" },
  { label: "评估与部署", to: "/models/registry" },
];
const active = computed(() =>
  route.name === "data"
    ? route.params.tab === "annotation"
      ? 1
      : route.params.tab === "datasets"
        ? 2
        : 0
    : route.params.tab === "training"
      ? 3
      : 4,
);
</script>
<template>
  <nav class="workflow-nav" aria-label="建模流程">
    <span>建模流程</span
    ><RouterLink
      v-for="(step, i) in steps"
      :key="step.to"
      :to="step.to"
      :class="{ active: i === active }"
      :aria-current="i === active ? 'step' : undefined"
      ><b>{{ i + 1 }}</b
      >{{ step.label
      }}<span v-if="i < steps.length - 1" aria-hidden="true"
        >›</span
      ></RouterLink
    >
  </nav>
</template>
<style scoped>
.workflow-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 14px;
  font-size: 12px;
}
.workflow-nav > span {
  color: var(--muted);
  margin-right: 8px;
}
.workflow-nav a {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--muted);
  text-decoration: none;
  padding: 6px 0;
}
.workflow-nav b {
  font-size: 10px;
  border: 1px solid var(--line);
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  font-weight: 400;
}
.workflow-nav .active {
  color: var(--forest);
  font-weight: 600;
}
.workflow-nav .active b {
  background: var(--forest);
  color: white;
  border-color: var(--forest);
}
.workflow-nav a > span {
  margin-left: 10px;
  color: var(--muted);
}
@media (max-width: 760px) {
  .workflow-nav {
    gap: 8px;
  }
  .workflow-nav > span {
    display: none;
  }
  .workflow-nav a > span {
    margin-left: 2px;
  }
}
</style>
