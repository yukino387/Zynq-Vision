<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useAppStore, type Theme } from "../../stores/app";
import Icon from "../Icon.vue";

const app = useAppStore();
const open = ref(false);
const toggleRef = ref<HTMLElement | null>(null);

interface ThemeOption {
  value: Theme;
  label: string;
  icon: string;
  desc: string;
}

const defaultTheme: ThemeOption = {
  value: "system",
  label: "跟随系统",
  icon: "monitor",
  desc: "自动匹配操作系统",
};

const themes: ThemeOption[] = [
  { value: "light", label: "浅色主题", icon: "sun", desc: "高清晰度明亮环境" },
  { value: "dark", label: "深色主题", icon: "moon", desc: "暗光工位降低疲劳" },
  defaultTheme,
];

const currentTheme = computed<ThemeOption>(() => {
  return themes.find((t) => t.value === app.theme) || defaultTheme;
});

function selectTheme(val: Theme) {
  app.setTheme(val);
  open.value = false;
}

function onClickOutside(event: MouseEvent) {
  if (toggleRef.value && !toggleRef.value.contains(event.target as Node)) {
    open.value = false;
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && open.value) {
    open.value = false;
  }
}

onMounted(() => {
  document.addEventListener("click", onClickOutside);
  window.addEventListener("keydown", onKeydown);
});

onUnmounted(() => {
  document.removeEventListener("click", onClickOutside);
  window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <div ref="toggleRef" class="ui-theme-toggle">
    <button
      type="button"
      class="theme-trigger-btn"
      :class="{ 'is-open': open }"
      :aria-expanded="open"
      aria-haspopup="menu"
      aria-label="选择系统主题"
      :title="`当前主题：${currentTheme.label}（点击切换）`"
      @click="open = !open"
    >
      <span class="theme-icon-wrap" :class="`theme-${app.theme}`">
        <Icon :name="currentTheme.icon" :size="15" />
      </span>
      <span class="theme-label-text">{{ currentTheme.label }}</span>
      <span class="theme-chevron" aria-hidden="true">
        <svg viewBox="0 0 10 6" width="8" height="5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M1 1l4 4 4-4" />
        </svg>
      </span>
    </button>

    <Transition name="theme-menu-pop">
      <div v-if="open" class="theme-dropdown-menu" role="menu" aria-label="主题选项">
        <div class="menu-heading">显示主题</div>
        <button
          v-for="item in themes"
          :key="item.value"
          type="button"
          class="theme-menu-item"
          :class="{ 'is-active': app.theme === item.value }"
          role="menuitem"
          @click="selectTheme(item.value)"
        >
          <span class="item-icon-box" :class="`icon-${item.value}`">
            <Icon :name="item.icon" :size="16" />
          </span>
          <div class="item-text">
            <span class="item-title">{{ item.label }}</span>
            <small class="item-desc">{{ item.desc }}</small>
          </div>
          <span v-if="app.theme === item.value" class="active-check" aria-hidden="true">
            <Icon name="check" :size="14" />
          </span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.ui-theme-toggle {
  position: relative;
  display: inline-flex;
  vertical-align: middle;
}

.theme-trigger-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--ink);
  padding: 5px 10px;
  min-height: 32px;
  border-radius: var(--radius, 6px);
  cursor: pointer;
  user-select: none;
  font-family: inherit;
  font-size: 12px;
  font-weight: 550;
  transition: all 0.15s ease;
  box-sizing: border-box;
}

.theme-trigger-btn:hover {
  background: var(--surface-3);
  border-color: var(--line-strong);
}

.theme-trigger-btn:focus-visible {
  outline: 2px solid var(--forest);
  outline-offset: 2px;
}

.theme-trigger-btn.is-open {
  border-color: var(--forest);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--forest) 15%, transparent);
}

.theme-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  transition: transform 0.2s ease, color 0.15s ease;
}

.theme-icon-wrap.theme-light {
  color: #df8813;
}

.theme-icon-wrap.theme-dark {
  color: #8da4ff;
}

.theme-icon-wrap.theme-system {
  color: var(--forest);
}

.theme-trigger-btn:hover .theme-icon-wrap {
  transform: scale(1.1);
}

.theme-label-text {
  font-size: 12px;
  white-space: nowrap;
}

.theme-chevron {
  display: inline-flex;
  align-items: center;
  color: var(--muted);
  transition: transform 0.18s ease;
}

.theme-trigger-btn.is-open .theme-chevron {
  transform: rotate(180deg);
}

/* 下拉菜单浮层 */
.theme-dropdown-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 100;
  min-width: 200px;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius, 8px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  box-sizing: border-box;
}

.menu-heading {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 6px 10px 4px;
}

.theme-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  border: none;
  background: transparent;
  color: var(--ink);
  padding: 8px 10px;
  border-radius: calc(var(--radius, 8px) - 2px);
  cursor: pointer;
  text-align: left;
  transition: background-color 0.12s ease, color 0.12s ease;
  box-sizing: border-box;
  font-family: inherit;
}

.theme-menu-item:hover {
  background: var(--surface-2);
}

.theme-menu-item:focus-visible {
  outline: 2px solid var(--forest);
  outline-offset: -1px;
}

.theme-menu-item.is-active {
  background: color-mix(in srgb, var(--forest) 10%, var(--surface));
  color: var(--forest);
}

.item-icon-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--muted);
  flex-shrink: 0;
}

.icon-light {
  color: #df8813;
  background: #fbf5e8;
}

.icon-dark {
  color: #7d96f7;
  background: #252836;
}

.icon-system {
  color: var(--forest);
  background: color-mix(in srgb, var(--forest) 12%, transparent);
}

.item-text {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 13px;
  font-weight: 550;
  line-height: 1.3;
}

.item-desc {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.3;
  margin-top: 2px;
}

.theme-menu-item.is-active .item-desc {
  color: color-mix(in srgb, var(--forest) 80%, transparent);
}

.active-check {
  color: var(--forest);
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

/* 动效 */
.theme-menu-pop-enter-active,
.theme-menu-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s cubic-bezier(0.16, 1, 0.3, 1);
}

.theme-menu-pop-enter-from,
.theme-menu-pop-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-4px);
}

@media (max-width: 600px) {
  .theme-label-text {
    display: none;
  }
}
</style>
