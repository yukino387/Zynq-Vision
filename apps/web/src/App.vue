<script setup lang="ts">
import {
  onMounted,
  onUnmounted,
  watch,
  watchEffect,
  computed,
  ref,
  nextTick,
} from "vue";
import { chinese, displayName } from "@vision/shared";
import { useRoute } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { useDeviceStore } from "./stores/devices";
import { useNotificationStore } from "./stores/notifications";
import { useTaskStore } from "./stores/tasks";
import { useAppStore, type Theme } from "./stores/app";
import { canAccess, navItems, roleDuties } from "./navigation";
import type { RouteRecordRaw } from "vue-router";
import AuthPanel from "./components/AuthPanel.vue";
import Icon from "./components/Icon.vue";
const navIcons: Record<string, string> = {
  overview: "dashboard",
  plans: "clipboard",
  production: "scan",
  workbench: "camera",
  records: "audit",
  data: "database",
  models: "layers",
  firmware: "device",
  diagnostics: "activity",
  system: "server",
  access: "users",
  account: "users",
};
const auth = useAuthStore(),
  devices = useDeviceStore(),
  notices = useNotificationStore(),
  tasks = useTaskStore(),
  app = useAppStore(),
  route = useRoute();
function onTheme(event: Event) {
  app.setTheme((event.target as HTMLSelectElement).value as Theme);
}
function focusMain() {
  document.getElementById("main")?.focus();
}
const nav = computed(() =>
  navItems.filter((item) => canAccess(item.meta?.roles, auth.user?.role)),
);
const currentPage = computed(() => {
  const base = route.meta?.title ?? "检测工作台";
  const tabs = route.meta?.tabs ?? [];
  if (!tabs.length) return base;
  const wanted = String(
    route.params.tab || route.meta?.defaultTab || tabs[0]?.tab || "",
  );
  const tab = tabs.find((t) => t.tab === wanted);
  // 顶栏带上子页名，否则 /data/annotation 和 /data/tasks 看起来是同一个地方。
  return tab ? `${base} · ${tab.label}` : base;
});
const discipline = computed(() => route.meta?.discipline ?? "business");
/** 浏览器标签页跟着路由走：开多个页面时能分清哪个是哪个。 */
watchEffect(() => {
  document.title = auth.user
    ? `${currentPage.value} · 视觉物联网平台`
    : "视觉物联网平台";
});
function isCurrent(item: RouteRecordRaw) {
  return route.name === item.name;
}
const menuQuery = ref(""),
  sidebarOpen = ref(false),
  expanded = ref<string[]>([]);
const narrowScreen = window.matchMedia("(max-width: 760px)");
let previousOverflow = "";
function closeWideNavigation() {
  if (!narrowScreen.matches) sidebarOpen.value = false;
}
watch(sidebarOpen, async (open) => {
  if (open) {
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    await nextTick();
    document
      .querySelector<HTMLElement>(".nav-close")
      ?.focus({ preventScroll: true });
  } else {
    document.body.style.overflow = previousOverflow;
    await nextTick();
    document
      .querySelector<HTMLElement>(".menu-toggle")
      ?.focus({ preventScroll: true });
  }
});
function trapNavigation(event: KeyboardEvent) {
  if (!sidebarOpen.value || event.key !== "Tab") return;
  const controls = [
    ...(event.currentTarget as HTMLElement).querySelectorAll<HTMLElement>(
      "a[href], button, input",
    ),
  ].filter((el) => el.getClientRects().length && !el.closest("[inert]"));
  const first = controls[0],
    last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
}
onMounted(() => narrowScreen.addEventListener("change", closeWideNavigation));
onUnmounted(() => {
  narrowScreen.removeEventListener("change", closeWideNavigation);
  if (sidebarOpen.value) document.body.style.overflow = previousOverflow;
});
const matches = (text: string) => text.includes(menuQuery.value.trim());
const sidebarItems = computed(() =>
  nav.value
    .map((item) => ({
      item,
      tabs: (item.meta?.tabs ?? [])
        .filter((tab) => canAccess(tab.roles, auth.user?.role))
        .filter(
          (tab) =>
            !menuQuery.value.trim() ||
            matches(String(item.meta?.title)) ||
            matches(tab.label),
        ),
    }))
    .filter(
      (entry) =>
        !menuQuery.value.trim() ||
        matches(String(entry.item.meta?.title)) ||
        entry.tabs.length,
    ),
);
watch(
  () => route.name,
  (name) => {
    expanded.value = name ? [String(name)] : [];
  },
  { immediate: true },
);
async function toggle(name: string) {
  const closing = expanded.value.includes(name);
  expanded.value = closing
    ? expanded.value.filter((x) => x !== name)
    : [...expanded.value, name];
  if (!closing) {
    await nextTick();
    document
      .getElementById(`menu-${name}`)
      ?.scrollIntoView({ block: "nearest" });
  }
}
function choose() {
  menuQuery.value = "";
  sidebarOpen.value = false;
}
function subCurrent(item: RouteRecordRaw, tab: string) {
  return (
    isCurrent(item) && String(route.params.tab || item.meta?.defaultTab) === tab
  );
}
onMounted(() => auth.restore());
watch(
  () => auth.user,
  async (user, previousUser) => {
    if (user) {
      try {
        await devices.start();
        await tasks.load();
      } catch (e) {
        notices.error(e);
      }
    } else {
      sidebarOpen.value = false;
      devices.stop();
      if (previousUser) {
        tasks.selected = "";
        tasks.items = [];
      }
    }
  },
  { immediate: true },
);
</script>
<template>
  <div v-if="!auth.ready" class="empty">正在连接平台…</div>
  <AuthPanel v-else-if="!auth.user" />
  <div
    v-else
    class="shell"
    :data-discipline="discipline"
    @keydown.esc="sidebarOpen = false"
  >
    <!-- 键盘用户不必每次 Tab 穿过整条侧栏 -->
    <a class="skip" href="#main" @click.prevent="focusMain">跳到主内容</a>
    <Transition name="fade">
      <button
        v-if="sidebarOpen"
        class="nav-backdrop"
        aria-label="关闭导航"
        @click="sidebarOpen = false"
      ></button>
    </Transition>
    <aside
      id="workspace-nav"
      class="sidebar"
      :class="{ open: sidebarOpen }"
      :role="sidebarOpen ? 'dialog' : undefined"
      :aria-modal="sidebarOpen || undefined"
      aria-label="工作区导航"
      @keydown="trapNavigation"
    >
      <div class="brand-row">
        <RouterLink to="/" class="brand" @click="choose">
          <span class="brand-mark"><Icon name="scan" :size="23" /></span>
          <span
            >边缘视觉工作站<small>{{
              roleDuties[auth.user.role].name
            }}</small></span
          >
        </RouterLink>
        <button
          class="nav-close"
          aria-label="关闭导航"
          @click="sidebarOpen = false"
        >
          <Icon name="close" />
        </button>
      </div>
      <div v-if="auth.engineer" class="menu-search-wrap">
        <Icon name="search" :size="16" />
        <input
          v-model="menuQuery"
          class="menu-search"
          type="search"
          aria-label="搜索功能"
          placeholder="搜索功能"
        />
      </div>
      <nav aria-label="主导航">
        <template v-for="entry in sidebarItems" :key="String(entry.item.name)">
          <template v-if="entry.item.meta?.tabs?.length">
            <button
              class="nav-parent"
              :class="{ current: isCurrent(entry.item) }"
              :aria-expanded="
                !!menuQuery.trim() || expanded.includes(String(entry.item.name))
              "
              :aria-controls="`menu-${String(entry.item.name)}`"
              @click="toggle(String(entry.item.name))"
            >
              <Icon
                :name="navIcons[String(entry.item.name)] ?? 'device'"
                :size="18"
              />{{ entry.item.meta.title
              }}<span
                aria-hidden="true"
                class="nav-chevron"
                :class="{
                  expanded:
                    !!menuQuery.trim() ||
                    expanded.includes(String(entry.item.name)),
                }"
              ></span>
            </button>
            <div
              class="nav-collapse"
              :class="{
                expanded:
                  !!menuQuery.trim() ||
                  expanded.includes(String(entry.item.name)),
              }"
              :inert="
                !menuQuery.trim() && !expanded.includes(String(entry.item.name))
              "
              :aria-hidden="
                !menuQuery.trim() && !expanded.includes(String(entry.item.name))
              "
              :id="`menu-${String(entry.item.name)}`"
            >
              <div class="nav-children">
                <RouterLink
                  v-for="tab in entry.tabs"
                  :key="tab.tab"
                  class="sub"
                  :to="{ name: entry.item.name, params: { tab: tab.tab } }"
                  :class="{ selected: subCurrent(entry.item, tab.tab) }"
                  :aria-current="
                    subCurrent(entry.item, tab.tab) ? 'page' : undefined
                  "
                  @click="choose"
                  >{{ tab.label }}</RouterLink
                >
              </div>
            </div>
          </template>
          <RouterLink
            v-else
            :to="{ name: entry.item.name }"
            class="leaf"
            :class="{ selected: isCurrent(entry.item) }"
            :aria-current="isCurrent(entry.item) ? 'page' : undefined"
            @click="choose"
            ><Icon
              :name="navIcons[String(entry.item.name)] ?? 'device'"
              :size="18"
            />{{ entry.item.meta?.title }}</RouterLink
          >
        </template>
        <p v-if="!sidebarItems.length" class="menu-empty">没有找到相关功能</p>
      </nav>
      <div class="session">
        <span class="session-avatar" aria-hidden="true">{{
          displayName(auth.user.name).slice(0, 1)
        }}</span>
        <RouterLink
          class="session-profile"
          to="/account"
          title="账号设置"
          @click="choose"
        >
          {{ displayName(auth.user.name)
          }}<small>{{ chinese(auth.user.role) }}</small>
        </RouterLink>
        <button @click="auth.logout" aria-label="退出登录" title="退出登录">
          <Icon name="logout" :size="17" />
        </button>
      </div>
    </aside>
    <div class="main-shell" :inert="sidebarOpen">
      <header class="topbar">
        <button
          class="menu-toggle"
          @click="sidebarOpen = !sidebarOpen"
          :aria-expanded="sidebarOpen"
          aria-controls="workspace-nav"
          aria-label="打开导航"
        >
          <Icon name="menu" />
        </button>
        <span class="topbar-location"
          ><Icon
            :name="navIcons[String(route.name)] ?? 'clipboard'"
            :size="16"
          />{{ currentPage }}</span
        >
        <div class="topbar-actions">
          <RouterLink
            class="account-link"
            to="/account"
            aria-label="账号设置"
            title="账号设置"
            @click="choose"
            ><Icon name="users" :size="16" /><span>账号设置</span></RouterLink
          >
          <span class="connection-status"
            ><span
              class="connection-dot"
              :class="devices.connected ? 'ok' : 'info'"
            ></span
            >{{ devices.connected ? "平台连接正常" : "平台连接中" }}</span
          ><RouterLink v-if="auth.engineer" to="/system/health"
            >系统状态</RouterLink
          ><select
            v-if="auth.engineer"
            class="theme-select"
            :value="app.theme"
            @change="onTheme"
            aria-label="显示主题"
          >
            <option value="system">跟随系统</option>
            <option value="light">浅色</option>
            <option value="dark">深色</option>
          </select>
        </div>
      </header>
      <main
        id="main"
        tabindex="-1"
        :data-page="String(route.name)"
        :data-tab="String(route.params.tab || route.meta.defaultTab || '')"
      >
        <!-- tab 切换也是路由切换，所以这一个过渡同时覆盖侧栏跳转和子页切换 -->
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <div :key="route.path" class="page-content">
              <component :is="Component" />
            </div>
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
  <TransitionGroup
    name="toast"
    tag="div"
    class="toasts"
    aria-live="polite"
    aria-relevant="additions"
  >
    <button
      v-for="m in notices.messages"
      :key="m.id"
      :class="{ error: m.error }"
      @click="notices.dismiss(m.id)"
    >
      <Icon :name="m.error ? 'alert' : 'check'" :size="19" />
      <span class="toast-message">{{ m.text }}</span
      ><Icon name="close" :size="15" />
    </button>
  </TransitionGroup>
</template>
<style scoped>
.session-profile {
  flex: 1;
  min-width: 0;
  color: inherit;
  text-decoration: none;
  border-radius: 6px;
  padding: 4px;
}
.session-profile:hover {
  background: #30372b;
}
.topbar-actions .account-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 5px 8px;
  border-radius: 6px;
  color: var(--ink-2);
}
.account-link:hover {
  background: var(--surface-2);
}
@media (max-width: 1000px) {
  .account-link span {
    display: none;
  }
}
</style>
