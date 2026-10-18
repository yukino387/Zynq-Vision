from pathlib import Path
p=Path('apps/web/src/views/Data.vue'); s=p.read_text(encoding='utf-8')
s=s.replace('    await list.load();\n    notices.add("样本审核已保存");','    if (next) list.page.value = 1;\n    await list.load();\n    notices.add("样本审核已保存");')
s=s.replace('notices.add("当前列表已审核完成");','notices.add("当前没有其他待审核样本");')
s=s.replace('''tab === 'review'
        ? '没有待审核的样本。采样后样本会先落到这里，审核通过才能进数据集。'
        : '还没有样本。用「导入图片」上传，或到移动端做一次板端采样。' ''','''tab === 'tasks' ? '点击“创建任务”开始采样。' : tab === 'datasets' ? '点击“创建数据集”，从样本库选取已审核样本加入。' : tab === 'review' ? '当前没有待审核样本。' : '可导入图片，或前往检测工作台采样。' ''') if False else s
start=s.index('    :hint="'); end=s.index('    @retry=',start)
s=s[:start]+'''    :hint="tab === 'tasks' ? '点击“创建任务”开始采样。' : tab === 'datasets' ? '创建数据集后，从样本库选择已审核样本加入。' : tab === 'review' ? '当前没有待审核样本。' : '可导入图片，或前往检测工作台采样。'"
'''+s[end:]
s=s.replace('v-if="![\'tasks\', \'datasets\'].includes(tab)"','v-if="tab === \'samples\' && auth.engineer"') if False else s
# Only the checkbox column, not the upload/source filters.
s=s.replace('<th v-if="![\'tasks\', \'datasets\'].includes(tab)"></th>','<th v-if="tab === \'samples\' && auth.engineer"></th>')
s=s.replace('<td v-if="![\'tasks\', \'datasets\'].includes(tab)">','<td v-if="tab === \'samples\' && auth.engineer">')
s=s.replace(':aria-label="`选择 ${r.name}`"',':aria-label="`选择 ${displayName(r.name)}`"')
p.write_text(s,encoding='utf-8')
p=Path('apps/web/src/components/ImageViewer.vue');s=p.read_text(encoding='utf-8');b=Path('temporary/frontend_simplify/components_ImageViewer.vue');b.write_text(s,encoding='utf-8')
s=s.replace('  jpeg?: string;','  compact?: boolean;\n  jpeg?: string;')
s=s.replace('const image = ref("")','const toolsOpen = ref(false);\nconst image = ref("")')
s=s.replace('''        ><button
          @click="
            actual = true;''','''        ><button v-if="compact" :aria-expanded="toolsOpen" @click="toolsOpen = !toolsOpen">图像工具</button><template v-if="!compact || toolsOpen"><button
          @click="
            actual = true;''')
s=s.replace('''        </select>
      </div>''','''        </select></template>
      </div>''')
p.write_text(s,encoding='utf-8')
p=Path('apps/web/src/views/Operations.vue');s=p.read_text(encoding='utf-8');b=Path('temporary/frontend_simplify/views_Operations.vue');b.write_text(s,encoding='utf-8')
s=s.replace('''      <ImageViewer
        :jpeg''','''      <ImageViewer compact
        :jpeg''')
s=s.replace(":to=\"{ name: 'records' }\"", ":to=\"{ name: 'records', params: { tab: 'all' } }\"")
p.write_text(s,encoding='utf-8')
