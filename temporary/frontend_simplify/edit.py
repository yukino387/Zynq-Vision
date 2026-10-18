from pathlib import Path
root=Path('apps/web/src')
def edit(path, fn):
 p=root/path
 old=p.read_text(encoding='utf-8')
 backup=Path('temporary/frontend_simplify')/path.replace('/','_')
 if not backup.exists(): backup.write_text(old,encoding='utf-8')
 p.write_text(fn(old),encoding='utf-8')
def data(s):
 s=s.replace('useRoute }','useRoute, useRouter }')
 s=s.replace('import Status from', 'import { useTaskStore } from "../stores/tasks";\nimport Status from',1)
 s=s.replace('const route = useRoute(),','const route = useRoute(),\n  router = useRouter(),\n  tasks = useTaskStore(),')
 s=s.replace('    list.reviewed.value =', '    selectedIds.value = [];\n    datasetId.value = "";\n    list.source.value = "";\n    list.reviewed.value =',1)
 s=s.replace('async function create() {','async function create(startSampling = false) {')
 s=s.replace('    await post(endpoint.value, {','    const created = await post<Named>(endpoint.value, {',1)
 s=s.replace('    notices.add("记录已创建");','''    notices.add(tab.value === "tasks" ? "采样任务已创建" : "数据集已创建");
    if (tab.value === "tasks") {
      await tasks.load();
      if (startSampling) {
        tasks.selected = created.id;
        await router.push({ name: "workbench" });
      }
    }''')
 s=s.replace('      annotating.value = annotation;','      annotating.value = annotation;\n      reviewVerdict.value = "ACCEPT";\n      reviewNote.value = "";')
 s=s.replace('async function review() {','async function review(next = false) {')
 s=s.replace('    notices.add("样本审核已保存");','''    notices.add("样本审核已保存");
    if (next) {
      const item = list.items.value.find((r) => r.id !== sample.value?.id);
      if (item) await open(item);
      else {
        sample.value = null;
        notices.add("当前列表已审核完成");
      }
    }''')
 s=s.replace('''    <span>已选 {{ selectedIds.length }} 个样本</span
    ><button @click="selectDataset">加入数据集</button
    ><select v-if="datasets.length" v-model="datasetId">''','''    <span>已选 {{ selectedIds.length }} 个样本</span
    ><select v-model="datasetId" aria-label="目标数据集" @focus="selectDataset">''')
 s=s.replace('      v-if="datasetId"\n','')
 s=s.replace(':disabled="busy"\n    >\n      确认加入',':disabled="busy || !datasetId"\n    >\n      加入数据集')
 s=s.replace('''              <RouterLink :to="{ name: 'workbench' }">进入采样</RouterLink>''','''              <RouterLink :to="{ name: 'workbench' }" @click="tasks.selected = r.id">开始采样</RouterLink>''')
 s=s.replace('<form @submit.prevent="create">','<form @submit.prevent="create(tab === \'tasks\')">')
 s=s.replace('><button class="primary" :disabled="busy">创建</button>', '''><div class="form-actions"><button class="primary" :disabled="busy">{{ tab === 'tasks' ? '创建并开始采样' : '创建数据集' }}</button><button v-if="tab === 'tasks'" type="button" :disabled="busy" @click="create(false)">仅创建</button></div>''')
 s=s.replace('<button @click="adjacent(-1)">上一张</button','<button :disabled="list.items.value[0]?.id === sample.id" @click="adjacent(-1)">上一张</button')
 s=s.replace('<button @click="adjacent(1)">下一张</button','<button :disabled="list.items.value.at(-1)?.id === sample.id" @click="adjacent(1)">下一张</button')
 s=s.replace('''      ><button @click="review" class="primary" :disabled="busy">
        保存样本审核
      </button>
      <h3 class="section-space">资产证据</h3>''','''      ><div class="form-actions"><button v-if="tab === 'review'" @click="review(true)" class="primary" :disabled="busy">保存并审核下一张</button><button @click="review(false)" :class="{ primary: tab !== 'review' }" :disabled="busy">保存审核</button></div>
      <details class="section-space"><summary>原始文件与下载</summary>''')
 s=s.replace('''      <RouterLink :to="{ name: 'records' }"
        >前往检测记录审核</RouterLink
      >''','''      </details>''')
 s=s.replace('''                {{ tab === "annotation" ? "标注" : "查看" }}''','''                {{ tab === "annotation" ? "开始标注" : tab === "review" ? "审核" : "查看" }}''')
 return s
edit('views/Data.vue',data)
def records(s):
 s=s.replace('const route = useRoute(),','const advanced = ref(false);\nfunction resetFilters() {\n  list.search.value = "";\n  list.source.value = "";\n  list.from.value = "";\n  list.to.value = "";\n  list.filter();\n}\nconst route = useRoute(),')
 s=s.replace('<h1>检测记录</h1>', '<h1>{{ tab === "queue" ? "待复核记录" : "全部检测记录" }}</h1>')
 s=s.replace('''    /><input
      type="datetime-local"''','''    /><template v-if="advanced"><label>开始时间<input
      type="datetime-local"''',1) if False else s
 # Move source and time controls into an explicit advanced area while keeping one search form.
 start=s.index('    /><select v-model="list.source.value"')
 end=s.index('    /><button',start)
 controls=s[start:end]
 controls=controls.replace('    /><select','<select',1)
 s=s[:start]+'''    /><button type="button" :aria-expanded="advanced" @click="advanced = !advanced">{{ advanced ? '收起筛选' : '更多筛选' }}</button><button v-if="list.search.value || list.source.value || list.from.value || list.to.value" type="button" @click="resetFilters">清空条件</button><div v-if="advanced" class="filter-details">'''+controls+''' /></div><button'''+s[end+len('    /><button'):]
 s=s.replace('      筛选</button','      查询</button')
 s=s.replace('''params: { id: i.id }''','''params: { id: i.id }, query: tab === 'queue' ? { queue: '1' } : {}''')
 s=s.replace('>证据 / 复核</RouterLink','>{{ tab === "queue" ? "立即复核" : "查看详情" }}</RouterLink')
 return s
edit('views/Records.vue', records)
edit('navigation.ts',lambda s:s.replace('{ tab: "queue", label: "待办" }','{ tab: "queue", label: "待复核记录" }').replace('{ tab: "all", label: "全部" }','{ tab: "all", label: "全部记录" }').replace('{ tab: "annotation", label: "标注",','{ tab: "annotation", label: "样本标注",'))
