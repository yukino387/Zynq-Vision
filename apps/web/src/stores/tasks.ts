import { defineStore } from "pinia";
import { ref, watch } from "vue";
import type { Page } from "@vision/contracts";
import type { Task } from "../types";
import { api } from "../api";
export const useTaskStore = defineStore("tasks", () => {
  const items = ref<Task[]>([]),
    selected = ref(sessionStorage.getItem("vision.task") ?? "");
  watch(selected, (id) => {
    if (id) sessionStorage.setItem("vision.task", id);
    else sessionStorage.removeItem("vision.task");
  });
  async function load() {
    items.value = (await api<Page<Task>>("/tasks")).items;
    if (
      selected.value &&
      !items.value.some((task) => task.id === selected.value)
    )
      selected.value = "";
  }
  return { items, selected, load };
});
