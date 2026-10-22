import { computed, ref } from "vue";
import { defineStore } from "pinia";
import type { InspectionPlan } from "@vision/contracts";
import { api } from "../api";

export const useProductStore = defineStore("product", () => {
  const id = ref(sessionStorage.getItem("vision.product") || "");
  const plans = ref<InspectionPlan[]>([]);
  const current = computed(() =>
    plans.value.find((plan) => plan.id === id.value),
  );
  function select(value: string) {
    id.value = value;
    sessionStorage.setItem("vision.product", value);
  }
  async function load() {
    plans.value = (
      await api<{ items: InspectionPlan[] }>("/plans?pageSize=100")
    ).items.filter((plan) => Array.isArray(plan.rules?.classes));
    if (id.value && !plans.value.some((plan) => plan.id === id.value))
      select("");
    if (!id.value && plans.value.length === 1) select(plans.value[0]!.id);
  }
  return { id, plans, current, select, load };
});
