import { defineStore } from "pinia";
import { ref } from "vue";
import { errorText } from "../api";
export const useNotificationStore = defineStore("notifications", () => {
  const messages = ref<{ id: number; text: string; error: boolean }[]>([]);
  function add(text: string, error = false) {
    const id = Date.now();
    messages.value = [...messages.value, { id, text, error }].slice(-4);
    setTimeout(() => dismiss(id), error ? 12000 : 4000);
  }
  function dismiss(id: number) {
    messages.value = messages.value.filter((m) => m.id !== id);
  }
  return {
    messages,
    add,
    dismiss,
    error: (e: unknown) => add(errorText(e), true),
  };
});
