<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import Icon from "./Icon.vue";
defineOptions({ inheritAttrs: false });
const props = withDefaults(
  defineProps<{ title: string; wide?: boolean; escapeCloses?: boolean }>(),
  { escapeCloses: true },
);
const emit = defineEmits<{ close: [] }>();
const panel = ref<HTMLElement | null>(null);
let restoreTo: HTMLElement | null = null;
let previousOverflow = "";
const key = (e: KeyboardEvent) => {
  if (e.key === "Escape" && props.escapeCloses) {
    e.preventDefault();
    e.stopPropagation();
    emit("close");
  }
  if (e.key !== "Tab" || !panel.value) return;
  const controls = [
    ...panel.value.querySelectorAll<HTMLElement>(
      'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
    ),
  ].filter((el) => el.getClientRects().length && !el.closest("[inert]"));
  const first = controls[0],
    last = controls.at(-1);
  if (!first) {
    e.preventDefault();
    panel.value.focus();
  } else if (
    e.shiftKey &&
    (document.activeElement === first || document.activeElement === panel.value)
  ) {
    e.preventDefault();
    last?.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
};
onMounted(() => {
  // 打开时把焦点移进对话框，并锁住背景滚动；
  // 关闭时把焦点还回触发它的那个元素，否则键盘用户会掉回页面顶部。
  restoreTo = document.activeElement as HTMLElement | null;
  window.addEventListener("keydown", key, true);
  previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  panel.value?.focus();
});
onUnmounted(() => {
  window.removeEventListener("keydown", key, true);
  document.body.style.overflow = previousOverflow;
  if (restoreTo?.isConnected) restoreTo.focus({ preventScroll: true });
});
</script>
<template>
  <Teleport to="body">
    <Transition name="drawer" appear>
      <div v-bind="$attrs" class="scrim" @click.self="$emit('close')">
        <section
          ref="panel"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          tabindex="-1"
          class="drawer"
          :class="{ wide }"
        >
          <header>
            <div>
              <h2>{{ title }}</h2>
            </div>
            <button
              class="drawer-close"
              aria-label="关闭"
              :title="escapeCloses ? '关闭（Esc）' : '关闭'"
              @click="$emit('close')"
            >
              <Icon name="close" />
            </button>
          </header>
          <div class="drawer-body"><slot /></div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
