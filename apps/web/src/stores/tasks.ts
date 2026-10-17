import { defineStore } from "pinia";
import { ref } from "vue";
import type { Page } from "@vision/contracts";
import type { Task } from "../types";
import { api } from "../api";
export const useTaskStore = defineStore("tasks", () => {
  const items = ref<Task[]>([]),
    selected = ref("");
  async function load() {
    items.value = (await api<Page<Task>>("/tasks")).items;
  }
  return { items, selected, load };
});
