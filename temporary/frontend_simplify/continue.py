from pathlib import Path
r=Path('apps/web/src')
def edit(path,fn):
 p=r/path; old=p.read_text(encoding='utf-8'); b=Path('temporary/frontend_simplify')/path.replace('/','_');
 if not b.exists(): b.write_text(old,encoding='utf-8')
 p.write_text(fn(old),encoding='utf-8')
def component(s):
 s=s.replace('defineProps<{ inspection: Inspection }>()','defineProps<{ inspection: Inspection; queue?: boolean }>()')
 s=s.replace('saved: []','saved: [next: boolean]')
 s=s.replace('async function save() {','async function save(next = false) {')
 s=s.replace('emit("saved");','emit("saved", next);')
 s=s.replace('<button class="primary" @click="save" :disabled="busy">保存审核</button>', '''<div class="form-actions"><button v-if="queue" class="primary" @click="save(true)" :disabled="busy">保存并复核下一件</button><button :class="{ primary: !queue }" @click="save(false)" :disabled="busy">保存复核</button></div>''')
 return s
edit('components/InspectionDetail.vue',component)
def detail(s):
 s=s.replace('onMounted, ref','watch, ref').replace('useRoute }','useRoute, useRouter }')
 s=s.replace('import { api }','import { useNotificationStore } from "../stores/notifications";\nimport { api }')
 s=s.replace('const route = useRoute(),','const route = useRoute(),\n  router = useRouter(),\n  notices = useNotificationStore(),')
 s=s.replace('onMounted(load);','''watch(() => route.params.id, load, { immediate: true });
async function saved(next: boolean) {
  if (!next) return load();
  try {
    const pending = await api<{ items: Inspection[] }>("/inspections?result=REVIEW&reviewed=false&pageSize=1&sort=createdAt&order=desc");
    const item = pending.items[0];
    if (item) await router.replace({ name: "inspection", params: { id: item.id }, query: { queue: "1" } });
    else {
      notices.add("待复核记录已全部处理");
      await router.push({ name: "records", params: { tab: "queue" } });
    }
  } catch (e) {
    notices.error(e);
    await load();
  }
}''')
 s=s.replace('<RouterLink :to="{ name: \'workbench\' }">返回工作台</RouterLink>', '''<RouterLink :to="{ name: 'records', params: { tab: route.query.queue ? 'queue' : 'all' } }">返回记录列表</RouterLink>''')
 s=s.replace('<InspectionDetail :inspection="inspection" @saved="load" />','<InspectionDetail :key="inspection.id" :inspection="inspection" :queue="route.query.queue === \'1\'" @saved="saved" />')
 return s
edit('views/InspectionDetail.vue',detail)
def access(s):
 s=s.replace('computed, ref','computed, ref, watch')
 s=s.replace('async function issue() {','''watch(() => route.query.invite, (invite) => {
  if (invite === "1" && tab.value === "codes") form.value = true;
}, { immediate: true });
async function issue() {''')
 s=s.replace(":to=\"{ name: 'access', params: { tab: 'codes' } }\"", ":to=\"{ name: 'access', params: { tab: 'codes' }, query: { invite: '1' } }\"")
 return s
edit('views/Access.vue',access)
# Respect the existing theme, with clearer form groupings and larger task actions.
p=r/'workspace.css'
s=p.read_text(encoding='utf-8')
s+='''
/* 常用操作保持在当前任务内；展开的条件独占一行。 */
.form-actions { display:flex; flex-wrap:wrap; gap:10px; margin:18px 0; }
.form-actions button { min-height:40px; }
.filter-details { order:10; flex-basis:100%; display:flex; flex-wrap:wrap; gap:12px; padding:16px; background:var(--surface-2); border:1px solid var(--line); }
.filter-details label { margin:0; }
.filter-details input { min-width:180px; }
.toolbar > input[type="search"] { min-width:240px; flex:1; max-width:420px; }
.review-panel > h3 { margin-bottom:20px; }
.review-panel .form-actions { position:sticky; bottom:0; padding:12px 0; background:var(--surface); }
@media(max-width:760px) { .filter-details > * { width:100%; } .form-actions > button { flex:1; } .toolbar > input[type="search"] { min-width:0; max-width:none; width:100%; flex-basis:100%; } }
'''
p.write_text(s,encoding='utf-8')
