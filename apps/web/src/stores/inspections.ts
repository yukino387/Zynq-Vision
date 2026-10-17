import { defineStore } from "pinia";
import { ref } from "vue";
import type { Page } from "@vision/contracts";
import type { Inspection } from "../types";
import { api } from "../api";
export const useInspectionStore = defineStore("inspections", () => {
  const items = ref<Inspection[]>([]);
  async function load(query = "") {
    items.value = (await api<Page<Inspection>>(`/inspections${query}`)).items;
  }
  return { items, load };
});
