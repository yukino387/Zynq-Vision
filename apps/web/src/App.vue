<script setup lang="ts">
import { onMounted, watch, watchEffect, computed, ref, nextTick } from "vue";
import { chinese, displayName } from "@vision/shared";
import { useRoute } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { useDeviceStore } from "./stores/devices";
import { useNotificationStore } from "./stores/notifications";
import { useTaskStore } from "./stores/tasks";
import { useAppStore, type Theme } from "./stores/app";
import { canAccess, navItems } from "./navigation";
import type { RouteRecordRaw } from "vue-router";
import AuthPanel from "./components/AuthPanel.vue";
import WorkflowNav from "./components/WorkflowNav.vue";
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
  async (user) => {
    if (user) {
      try {
        await devices.start();
        await tasks.load();
      } catch (e) {
        notices.error(e);
      }
    } else devices.stop();
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
    <button
      v-if="sidebarOpen"
      class="nav-backdrop"
      aria-label="关闭导航"
      @click="sidebarOpen = false"
    ></button>
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <RouterLink to="/" class="brand"
        ><span>视觉物联网平台</span
        ><small>边缘视觉 · 设备工作站</small></RouterLink
      >
      <input
        v-model="menuQuery"
        class="menu-search"
        type="search"
        aria-label="搜索功能"
        placeholder="搜索功能，如标注、注册码"
      />
      <nav aria-label="主导航">
        <template
          v-for="(entry, navIndex) in sidebarItems"
          :key="String(entry.item.name)"
        >
          <template v-if="entry.item.meta?.tabs?.length">
            <button
              class="nav-parent"
              :class="{ current: isCurrent(entry.item) }"
              :aria-expanded="
                !!menuQuery.trim() || expanded.includes(String(entry.item.name))
              "
              @click="toggle(String(entry.item.name))"
            >
              <span class="nav-number">{{
                String(navIndex + 1).padStart(2, "0")
              }}</span
              >{{ entry.item.meta.title
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
              v-if="
                menuQuery.trim() || expanded.includes(String(entry.item.name))
              "
              class="nav-children"
              :id="`menu-${String(entry.item.name)}`"
            >
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
          </template>
          <RouterLink
            v-else
            :to="{ name: entry.item.name }"
            class="leaf"
            :class="{ selected: isCurrent(entry.item) }"
            :aria-current="isCurrent(entry.item) ? 'page' : undefined"
            @click="choose"
            ><span class="nav-number">{{
              String(navIndex + 1).padStart(2, "0")
            }}</span
            >{{ entry.item.meta?.title }}</RouterLink
          >
        </template>
        <p v-if="!sidebarItems.length" class="menu-empty">没有找到相关功能</p>
      </nav>
      <div class="session">
        <div>
          {{ displayName(auth.user.name)
          }}<small>{{ chinese(auth.user.role) }}</small>
        </div>
        <button @click="auth.logout" aria-label="退出登录">退出</button>
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <button
          class="menu-toggle"
          @click="sidebarOpen = !sidebarOpen"
          :aria-expanded="sidebarOpen"
        >
          菜单
        </button>
        <span>{{ currentPage }}</span>
        <div class="topbar-actions">
          <span
            ><span
              class="connection-dot"
              :class="devices.connected ? 'ok' : 'info'"
            ></span
            >{{ devices.connected ? "服务已连接" : "服务重连中" }}</span
          ><RouterLink v-if="auth.engineer" to="/system/health"
            >系统状态</RouterLink
          ><select
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
        <WorkflowNav
          v-if="
            auth.engineer && ['data', 'models'].includes(String(route.name))
          "
        />
        <!-- tab 切换也是路由切换，所以这一个过渡同时覆盖侧栏跳转和子页切换 -->
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
  <div class="toasts" aria-live="polite">
    <button
      v-for="m in notices.messages"
      :key="m.id"
      :class="{ error: m.error }"
      @click="notices.dismiss(m.id)"
    >
      {{ m.text }} <span>关闭</span>
    </button>
  </div>
</template>
