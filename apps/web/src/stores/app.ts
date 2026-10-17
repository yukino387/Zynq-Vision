import { defineStore } from "pinia";
import { ref } from "vue";

export type Theme = "system" | "light" | "dark";
const THEME_KEY = "vision.theme";

function readTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark" || stored === "system")
      return stored;
  } catch {
    /* 禁用存储时回落到跟随系统 */
  }
  return "system";
}

/** 主题只体现在 documentElement 的 data-theme 上；令牌的三段式定义见 design-tokens。 */
function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

export const useAppStore = defineStore("app", () => {
  const theme = ref<Theme>(readTheme());
  applyTheme(theme.value);

  function setTheme(next: Theme) {
    theme.value = next;
    applyTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* 存不下不影响本次会话 */
    }
  }

  return { theme, setTheme };
});
