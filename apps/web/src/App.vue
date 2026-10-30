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
import { canAccess, navItems } from "./navigation";
import type { RouteRecordRaw } from "vue-router";
import AuthPanel from "./components/AuthPanel.vue";
import ProductWorkflow from "./components/ProductWorkflow.vue";
import Icon from "./components/Icon.vue";
import { UiBadge, UiButton, UiThemeToggle } from "./components/ui";
const navIcons: Record<string, string> = {
  showcase: "monitor",
  overview: "dashboard",
  plans: "clipboard",
  production: "chart",
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
  route = useRoute();
/** 顶栏的整点脉冲：只显示本地时间，不做联网校时。 */
const clock = ref("--:--:--");
let clockTimer = 0;
function tickClock() {
  const now = new Date(),
    pad = (value: number) => String(value).padStart(2, "0");
  clock.value = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}
/** 页面编号沿用工作流顺序，让页眉与侧栏形成同一套索引。 */
const pageIndex: Record<string, string> = {
  showcase: "00",
  overview: "01",
  plans: "02",
  workbench: "03",
  production: "04",
  records: "05",
  inspection: "05",
  data: "06",
  models: "07",
  diagnostics: "08",
  system: "09",
  access: "10",
  account: "11",
};
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
const menuSearch = ref<HTMLInputElement | null>(null);
function focusSearch(event: KeyboardEvent) {
  if (!auth.engineer || event.metaKey || event.ctrlKey || event.altKey) return;
  const target = event.target as HTMLElement | null;
  if (target?.closest("input, textarea, select, [contenteditable=true]")) return;
  if (event.key !== "/" && event.key !== "?") return;
  event.preventDefault();
  if (narrowScreen.matches) sidebarOpen.value = true;
  nextTick(() => menuSearch.value?.focus());
}
onMounted(() => {
  tickClock();
  clockTimer = window.setInterval(tickClock, 1000);
  narrowScreen.addEventListener("change", closeWideNavigation);
  window.addEventListener("keydown", focusSearch);
});
onUnmounted(() => {
  window.clearInterval(clockTimer);
  narrowScreen.removeEventListener("change", closeWideNavigation);
  window.removeEventListener("keydown", focusSearch);
  if (sidebarOpen.value) document.body.style.overflow = previousOverflow;
});
const matches = (text: string) =>
  text.toLocaleLowerCase().includes(menuQuery.value.trim().toLocaleLowerCase());
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
  <RouterView v-else-if="route.name === 'showcase'" />
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
          <span class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="10.6" stroke="currentColor" />
              <circle cx="16" cy="16" r="4.2" stroke="currentColor" />
              <path
                d="M16 2.4v4.2M16 25.4v4.2M2.4 16h4.2M25.4 16h4.2"
                stroke="currentColor"
              />
              <circle cx="16" cy="16" r="1.2" fill="currentColor" />
            </svg>
          </span>
          <span class="brand-text"
            >视觉物联网平台<small>VISION IOT PLATFORM</small></span
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
        <Icon name="search" :size="15" />
        <input
          ref="menuSearch"
          v-model="menuQuery"
          class="menu-search"
          type="search"
          aria-label="搜索功能"
          placeholder="搜索工作区"
        />
        <kbd aria-hidden="true">/</kbd>
      </div>
      <div class="nav-index-label" aria-hidden="true">
        <span>工作区</span><em>WORKSPACE INDEX</em>
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
        <p v-if="!sidebarItems.length" class="menu-empty">
          没有找到相关功能 <button @click="menuQuery = ''">清空搜索</button>
        </p>
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
        <span class="topbar-location">
          <span class="topbar-index mono">{{
            pageIndex[String(route.name)] ?? "—"
          }}</span>
          <span class="topbar-divider" aria-hidden="true"></span>
          <Icon
            :name="navIcons[String(route.name)] ?? 'clipboard'"
            :size="15"
          />{{ currentPage }}
        </span>
        <div class="topbar-actions">
          <span class="topbar-clock mono" title="本机时间"
            ><i aria-hidden="true"></i>{{ clock }}<em>LOCAL</em></span
          >
          <RouterLink
            class="account-link"
            to="/account"
            aria-label="账号设置"
            title="账号设置"
            @click="choose"
          >
            <Icon name="users" :size="14" />
            <span>账号</span>
          </RouterLink>
          <UiBadge
            :tone="devices.connected ? 'success' : 'warn'"
            variant="outline"
            dot
            :pulse="!devices.connected"
            size="sm"
          >
            {{ devices.connected ? "节点在线" : "节点连接中" }}
          </UiBadge>
          <UiButton
            v-if="auth.engineer"
            variant="ghost"
            size="sm"
            class="topbar-system"
            :to="{ path: '/system/health' }"
          >
            系统
          </UiButton>
          <UiThemeToggle />
        </div>
      </header>
      <main
        id="main"
        tabindex="-1"
        :data-page="String(route.name)"
        :data-tab="String(route.params.tab || route.meta.defaultTab || '')"
      >
        <ProductWorkflow
          v-if="
            auth.engineer &&
            ['plans', 'data', 'models'].includes(String(route.name)) &&
            !(route.name === 'models' && route.params.tab === 'deployments')
          "
        />
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
