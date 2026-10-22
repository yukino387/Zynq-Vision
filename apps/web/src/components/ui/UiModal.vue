<script setup lang="ts">
import { watch, nextTick, onMounted, onUnmounted, ref } from "vue";
import Icon from "../Icon.vue";

export interface UiModalProps {
  modelValue?: boolean;
  open?: boolean;
  title?: string;
  subtitle?: string;
  width?: string;
  closeOnEsc?: boolean;
  closeOnClickOutside?: boolean;
}

const props = withDefaults(defineProps<UiModalProps>(), {
  modelValue: false,
  open: undefined,
  title: "",
  subtitle: "",
  width: "560px",
  closeOnEsc: true,
  closeOnClickOutside: true,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "close"): void;
}>();

const modalRef = ref<HTMLElement | null>(null);
const isOpen = () => (props.open !== undefined ? props.open : props.modelValue);

function close() {
  emit("update:modelValue", false);
  emit("close");
}

function onBackdropClick(event: MouseEvent) {
  if (props.closeOnClickOutside && event.target === event.currentTarget) {
    close();
  }
}

function onKeyDown(event: KeyboardEvent) {
  if (props.closeOnEsc && event.key === "Escape" && isOpen()) {
    event.stopPropagation();
    close();
  }
}

let prevBodyOverflow = "";

watch(
  () => isOpen(),
  async (val) => {
    if (val) {
      prevBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      await nextTick();
      modalRef.value?.focus();
    } else {
      document.body.style.overflow = prevBodyOverflow;
    }
  },
  { immediate: true },
);

onMounted(() => {
  window.addEventListener("keydown", onKeyDown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onKeyDown);
  if (isOpen()) {
    document.body.style.overflow = prevBodyOverflow;
  }
});
</script>

<template>
  <Teleport to="body">
    <Transition name="ui-modal-fade">
      <div
        v-if="isOpen()"
        class="ui-modal-backdrop"
        tabindex="-1"
        @click="onBackdropClick"
      >
        <div
          ref="modalRef"
          class="ui-modal-container"
          :style="{ maxWidth: width }"
          role="dialog"
          aria-modal="true"
          :aria-label="title || '对话框'"
          tabindex="-1"
        >
          <header class="ui-modal-header">
            <slot name="header">
              <div class="ui-modal-title-group">
                <h3 v-if="title" class="ui-modal-title">{{ title }}</h3>
                <p v-if="subtitle" class="ui-modal-subtitle">{{ subtitle }}</p>
              </div>
              <button
                type="button"
                class="ui-modal-close"
                aria-label="关闭对话框"
                @click="close"
              >
                <Icon name="close" :size="16" />
              </button>
            </slot>
          </header>

          <div class="ui-modal-body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="ui-modal-footer">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.ui-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: var(--scrim, rgba(0, 0, 0, 0.45));
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  box-sizing: border-box;
}

.ui-modal-container {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius, 10px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.22);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 40px);
  outline: none;
  overflow: hidden;
  box-sizing: border-box;
}

.ui-modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--line);
}

.ui-modal-title-group {
  min-width: 0;
}

.ui-modal-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.35;
}

.ui-modal-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.4;
}

.ui-modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--muted);
  width: 32px;
  height: 32px;
  border-radius: 6px;
  padding: 0;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s ease, color 0.15s ease;
}

.ui-modal-close:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.ui-modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink);
  flex: 1;
}

.ui-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  background: var(--surface-2);
  border-top: 1px solid var(--line);
}

/* 动效 */
.ui-modal-fade-enter-active,
.ui-modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.ui-modal-fade-enter-from,
.ui-modal-fade-leave-to {
  opacity: 0;
}

.ui-modal-fade-enter-active .ui-modal-container {
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
}

.ui-modal-fade-leave-active .ui-modal-container {
  transition: transform 0.15s ease-in, opacity 0.15s ease;
}

.ui-modal-fade-enter-from .ui-modal-container {
  opacity: 0;
  transform: scale(0.97) translateY(8px);
}

.ui-modal-fade-leave-to .ui-modal-container {
  opacity: 0;
  transform: scale(0.97) translateY(8px);
}
</style>
