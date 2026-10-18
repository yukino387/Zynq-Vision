from pathlib import Path
from zipfile import ZipFile
root=Path(__file__).resolve().parents[2]
with ZipFile(root/'temporary/frontend_workflow_20261016/baseline.zip') as z:
 for name in ['apps/web/src/style.css','packages/design-tokens/tokens.css','apps/web/src/views/Overview.vue','apps/web/src/navigation.ts']:
  (root/name).write_bytes(z.read(name))

p=root/'apps/web/src/navigation.ts';s=p.read_text(encoding='utf-8')
s=s.replace('import NotFound from "./views/NotFound.vue";','import NotFound from "./views/NotFound.vue";\nimport Access from "./views/Access.vue";')
s=s.replace('        { tab: "users", label: "用户", roles: ["ADMIN"] },\n','')
pos=s.index('  {\n    path: "/:pathMatch')
s=s[:pos]+'''  {
    path: '/access/:tab?', name: 'access', component: Access,
    meta: {title: '账号与注册', nav: true, order: 8, roles: ['ADMIN'], defaultTab: 'users', tabs: [{tab: 'users', label: '用户管理'}, {tab: 'codes', label: '注册码管理'}]},
  },
'''+s[pos:]
p.write_text(s,encoding='utf-8')

p=root/'apps/web/src/views/Overview.vue';s=p.read_text(encoding='utf-8')
s=s.replace('import { chinese }','import { chinese, displayName }')
s=s.replace('置信度低于放行阈值，需人工确认后归档','确认检测结果后完成归档')
s=s.replace('data.inspections.review" class="banner','data.pipeline?.pendingReview" class="banner').replace('{{ data.inspections.review }} 件待复核','{{ data.pipeline?.pendingReview }} 件待复核')
s=s.replace('{{ current?.name ?? "（无设备）" }}','{{ displayName(current?.name ?? "（无设备）") }}')
s=s.replace('<div class="heading-actions">','<div class="heading-actions"><RouterLink class="button-link primary" :to="{name:\'workbench\'}">开始检测</RouterLink>',1)
# Telemetry must belong to the selected device; preserve the user's analysis components.
template_at=s.index('<template>');s=s[:template_at]+s[template_at:].replace('data.through?', 'current?.telemetry?').replace('data.through.', 'current?.telemetry?.')
s=s.replace('current?.telemetry?.errorCode ?? 0','current?.telemetry?.errorCode ?? "未上报"')
p.write_text(s,encoding='utf-8')

p=root/'apps/web/src/App.vue';s=p.read_text(encoding='utf-8')
s=s.replace('watchEffect, computed','watchEffect, computed, ref')
start=s.index('const currentTabs = computed(');end=s.index('onMounted(',start)
s=s[:start]+'''const menuQuery = ref(''), sidebarOpen = ref(false), expanded = ref<string[]>([]);
const matches = (text: string) => text.includes(menuQuery.value.trim());
const sidebarItems = computed(() => nav.value.map(item => ({
  item,
  tabs: (item.meta?.tabs ?? []).filter(tab => canAccess(tab.roles, auth.user?.role)).filter(tab => !menuQuery.value.trim() || matches(String(item.meta?.title)) || matches(tab.label)),
})).filter(entry => !menuQuery.value.trim() || matches(String(entry.item.meta?.title)) || entry.tabs.length));
watch(() => route.name, name => { if (name && !expanded.value.includes(String(name))) expanded.value.push(String(name)); }, {immediate:true});
function toggle(name: string) { expanded.value = expanded.value.includes(name) ? expanded.value.filter(x => x !== name) : [...expanded.value, name]; }
function choose() { menuQuery.value = ''; sidebarOpen.value = false; }
function subCurrent(item: RouteRecordRaw, tab: string) {return isCurrent(item) && String(route.params.tab || item.meta?.defaultTab) === tab;}
'''+s[end:]
s=s.replace('<aside class="sidebar">','<button v-if="sidebarOpen" class="nav-backdrop" aria-label="关闭导航" @click="sidebarOpen = false"></button><aside class="sidebar" :class="{open:sidebarOpen}">')
start=s.index('      <nav aria-label="主导航">');end=s.index('      <div class="session">',start)
s=s[:start]+'''      <input v-model="menuQuery" class="menu-search" type="search" aria-label="搜索功能" placeholder="搜索功能，如标注、注册码" />
      <nav aria-label="主导航">
        <template v-for="entry in sidebarItems" :key="String(entry.item.name)">
          <template v-if="entry.item.meta?.tabs?.length">
            <button class="nav-parent" :class="{current:isCurrent(entry.item)}" :aria-expanded="!!menuQuery.trim() || expanded.includes(String(entry.item.name))" @click="toggle(String(entry.item.name))">{{ entry.item.meta.title }}<span aria-hidden="true" class="nav-chevron" :class="{expanded: !!menuQuery.trim() || expanded.includes(String(entry.item.name))}"></span></button>
            <div v-if="menuQuery.trim() || expanded.includes(String(entry.item.name))" class="nav-children">
              <RouterLink v-for="tab in entry.tabs" :key="tab.tab" class="sub" :to="{name:entry.item.name, params:{tab:tab.tab}}" :class="{selected:subCurrent(entry.item,tab.tab)}" :aria-current="subCurrent(entry.item,tab.tab) ? 'page' : undefined" @click="choose">{{ tab.label }}</RouterLink>
            </div>
          </template>
          <RouterLink v-else :to="{name:entry.item.name}" class="leaf" :class="{selected:isCurrent(entry.item)}" :aria-current="isCurrent(entry.item) ? 'page' : undefined" @click="choose">{{ entry.item.meta?.title }}</RouterLink>
        </template>
        <p v-if="!sidebarItems.length" class="menu-empty">没有找到相关功能</p>
      </nav>
'''+s[end:]
s=s.replace('<header class="topbar">','<header class="topbar"><button class="menu-toggle" @click="sidebarOpen = !sidebarOpen" :aria-expanded="sidebarOpen">菜单</button>')
start=s.index('        <nav v-if="currentTabs.length"');end=s.index('        <!-- tab 切换',start);s=s[:start]+s[end:]
p.write_text(s,encoding='utf-8')

# Child-page headings now name the exact operation selected in the sidebar.
for name in ['Data','Models','Devices','System']:
 p=root/f'apps/web/src/views/{name}.vue';s=p.read_text(encoding='utf-8')
 import re
 s=re.sub(r'<h1>[^<]*</h1>', '<h1>{{ route.meta.tabs?.find(t => t.tab === tab)?.label ?? route.meta.title }}</h1>',s,count=1)
 p.write_text(s,encoding='utf-8')

# Reuse the user's base styling; isolate only the new workflow layouts.
p=root/'apps/web/src/main.ts';s=p.read_text(encoding='utf-8').replace('import "./style.css";','import "./style.css";\nimport "./workspace.css";');p.write_text(s,encoding='utf-8')
