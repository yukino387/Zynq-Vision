<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
defineProps<{ title: string }>();
const emit = defineEmits<{ close: [] }>();
const panel = ref<HTMLElement | null>(null);
let restoreTo: HTMLElement | null = null;
const key = (e: KeyboardEvent) => {
  if (e.key === "Escape") emit("close");
};
onMounted(() => {
  // 打开时把焦点移进对话框，并锁住背景滚动；
  // 关闭时把焦点还回触发它的那个元素，否则键盘用户会掉回页面顶部。
  restoreTo = document.activeElement as HTMLElement | null;
  window.addEventListener("keydown", key);
  document.body.style.overflow = "hidden";
  panel.value?.focus();
});
onUnmounted(() => {
  window.removeEventListener("keydown", key);
  document.body.style.overflow = "";
  restoreTo?.focus?.();
});
</script>
<template>
  <div class="scrim" @click.self="$emit('close')">
    <section
      ref="panel"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      tabindex="-1"
      class="drawer"
    >
      <header>
        <div>
          <h2>{{ title }}</h2>
        </div>
        <button aria-label="关闭" @click="$emit('close')">✕</button>
      </header>
      <div class="drawer-body"><slot /></div>
    </section>
  </div>
</template>
