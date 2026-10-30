import { createApp } from "vue";
import { createPinia } from "pinia";
import { createRouter, createWebHashHistory } from "vue-router";
import App from "./App.vue";
import { routes, canAccess, landingFor } from "./navigation";
import { useAuthStore } from "./stores/auth";
import * as UiComponents from "./components/ui";
import "@vision/design-tokens/tokens.css";
import "./style.css";
import "./workspace.css";
import "./instrument.css";
import "./demo.css";
import "./atelier.css";

const pinia = createPinia();
const router = createRouter({
  history: createWebHashHistory(),
  routes,
});
/** 角色只能在异步恢复之后知道，所以落地页与越权拦截都在守卫里做。
 *  深链到本角色打不开的屏会让整页变成 403 错误框，必须提前挡掉。 */
router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia);
  await auth.restore();
  if (!auth.user) return true; // App 渲染登录页
  if (to.path === "/" || !canAccess(to.meta.roles, auth.user.role))
    return { name: landingFor(auth.user.role) };
  if (to.meta.tabs?.length) {
    const active = String(to.params.tab || to.meta.defaultTab);
    const tab = to.meta.tabs.find((item) => item.tab === active);
    if (!tab || !canAccess(tab.roles, auth.user.role))
      return { name: to.name!, params: { tab: to.meta.defaultTab } };
  }
  return true;
});

const app = createApp(App);
app.use(pinia).use(router);

// 注册设计好的 UI 组件套件
for (const [name, component] of Object.entries(UiComponents)) {
  if (name.startsWith("Ui")) {
    app.component(name, component as any);
  }
}

app.mount("#app");
