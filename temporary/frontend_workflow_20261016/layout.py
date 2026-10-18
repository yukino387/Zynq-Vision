from pathlib import Path
import re
root=Path(__file__).resolve().parents[2]
p=root/'apps/web/src/App.vue';s=p.read_text(encoding='utf-8')
s=s.replace('onMounted, watch, watchEffect, ref, computed','onMounted, watch, watchEffect, computed')
s=s.replace('import { errorText } from "./api";','import AuthPanel from "./components/AuthPanel.vue";')
s=s.replace('const origin = location.origin;\nconst username = ref(""),\n  password = ref(""),\n  loginError = ref(""),\n  busy = ref(false);\n','')
s=s.replace('function tabsOf(item: RouteRecordRaw)', 'function tabsOf(item: RouteRecordRaw)')
start=s.index('/** 当前角色看得到的子页。 */');end=s.index('onMounted(',start)
s=s[:start]+'''const currentTabs = computed(() => (route.meta.tabs ?? []).filter(t => canAccess(t.roles, auth.user?.role)));
const activeTab = computed(() => String(route.params.tab || route.meta.defaultTab || ''));
const groups = [
  {label: '工作空间', names: ['overview', 'workbench', 'records', 'data']},
  {label: '管理', names: ['diagnostics', 'models']},
  {label: '设置', names: ['access', 'system']},
];
function entries(names: string[]) { return nav.value.filter(item => names.includes(String(item.name))); }
'''+s[end:]
start=s.index('async function login()');end=s.index('</script>',start);s=s[:start]+s[end:]
start=s.index('  <div v-else-if="!auth.user"');end=s.index('  <div v-else class="shell"',start)
s=s[:start]+'  <AuthPanel v-else-if="!auth.user" />\n'+s[end:]
start=s.index('      <nav aria-label="主导航">');end=s.index('      <div class="session">',start)
s=s[:start]+'''      <nav aria-label="主导航">
        <template v-for="group in groups" :key="group.label">
          <div v-if="entries(group.names).length" class="nav-group-label">{{ group.label }}</div>
          <RouterLink v-for="item in entries(group.names)" :key="String(item.name)" :to="{name: item.name}" :class="{selected: isCurrent(item)}" :aria-current="isCurrent(item) ? 'page' : undefined">{{ item.meta?.title }}</RouterLink>
        </template>
      </nav>
'''+s[end:]
start=s.index('      <main id="main" tabindex="-1">');s=s[:start]+s[start:].replace('      <main id="main" tabindex="-1">','''      <main id="main" tabindex="-1">
        <nav v-if="currentTabs.length" class="workspace-tabs" aria-label="页面导航">
          <RouterLink v-for="tab in currentTabs" :key="tab.tab" :to="{name: route.name!, params: {tab: tab.tab}}" :class="{active: activeTab === tab.tab}" :aria-current="activeTab === tab.tab ? 'page' : undefined">{{ tab.label }}</RouterLink>
        </nav>''',1)
p.write_text(s,encoding='utf-8')

p=root/'apps/web/src/navigation.ts';s=p.read_text(encoding='utf-8')
s=s.replace('import NotFound from "./views/NotFound.vue";','import NotFound from "./views/NotFound.vue";\nimport Access from "./views/Access.vue";')
s=s.replace('title: "产线总览"','title: "工作概览"').replace('title: "检测工作台"','title: "实时检测"').replace('title: "训练与发布"','title: "模型与发布"').replace('title: "设备诊断"','title: "设备与工位"').replace('title: "数据管理"','title: "采样与数据"').replace('title: "系统管理"','title: "系统设置"')
s=s.replace('order: 2,','order: 1,',1).replace('title: "实时检测", nav: true, order: 1','title: "实时检测", nav: true, order: 2')
s=s.replace('discipline: "hmi"','discipline: "business"')
s=s.replace('{ tab: "queue", label: "待办" }','{ tab: "queue", label: "待复核" }').replace('{ tab: "all", label: "全部" }','{ tab: "all", label: "全部记录" }')
s=s.replace('{ tab: "users", label: "用户", roles: ["ADMIN"] },\n','')
pos=s.index('  {\n    path: "/:pathMatch')
s=s[:pos]+'''  {
    path: '/access/:tab?', name: 'access', component: Access,
    meta: {title: '账号与注册', nav: true, order: 8, roles: ['ADMIN'], defaultTab: 'users', tabs: [{tab: 'users', label: '用户管理'}, {tab: 'codes', label: '注册码管理'}]},
  },
'''+s[pos:]
s=s.replace('return role === "ADMIN" || role === "ENGINEER" ? "overview" : "workbench";','return role === "ADMIN" || role === "ENGINEER" ? "overview" : "workbench";')
p.write_text(s,encoding='utf-8')

# Keep familiar user additions (theme, sorting, pagination); reduce visual density.
p=root/'packages/design-tokens/tokens.css';s=p.read_text(encoding='utf-8')
colors={'#f1f0ed':'#f5f7fa','#fbfaf8':'#ffffff','#e4e2dd':'#f7f8fa','#d6d3cc':'#eef1f5','#151715':'#1d2129','#484c49':'#4e5969','#7c807c':'#86909c','#c9c6bf':'#e5e6eb','#adaaa2':'#c9cdd4','#1f4d3a':'#165dff','#2a6349':'#4080ff','#5aa684':'#6b9eff','#6fb894':'#8cb3ff','#0e1a14':'#ffffff'}
for a,b in colors.items():s=s.replace(a,b)
s=s.replace('--radius: 2px','--radius: 6px')
p.write_text(s,encoding='utf-8')

# Remove editorial paragraphs from list screens. Keep decision-specific warnings.
for view in ['Data','Models','Records','System']:
 p=root/f'apps/web/src/views/{view}.vue';s=p.read_text(encoding='utf-8')
 s=re.sub(r'(<div class="page-heading">\s*<div>\s*<h1>[^<]*</h1>)\s*<p>[^<]*</p>',r'\1',s,count=1)
 p.write_text(s,encoding='utf-8')
