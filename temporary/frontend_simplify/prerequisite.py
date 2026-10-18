from pathlib import Path
p=Path('apps/web/src/views/Data.vue');s=p.read_text(encoding='utf-8');s=s.replace('const selectedRows = computed(() => list.items.value);','''const selectedRows = computed(() => list.items.value);
const missingAnnotation = computed(() => list.items.value.find((row) =>
  selectedIds.value.includes(row.id) && !(row.annotations as { status: string }[] | undefined)?.some((annotation) => annotation.status === "COMPLETE"),
));''')
s=s.replace('''    if (!datasetId.value) return;''','''    if (!datasetId.value || missingAnnotation.value) return;''') if False else s
s=s.replace('  if (!datasetId.value) return;','  if (!datasetId.value || missingAnnotation.value) return;')
s=s.replace('''    ><select
      v-model="datasetId"''','''    ><template v-if="missingAnnotation"><span class="tone-warn">所选样本尚未完成标注</span><button @click="open(missingAnnotation, true)">先完成标注</button></template><select
      v-model="datasetId"''')
s=s.replace(':disabled="busy || !datasetId"',':disabled="busy || !datasetId || !!missingAnnotation"')
s=s.replace('从样本库选择已审核样本加入','从样本库选择已完成标注的样本加入')
p.write_text(s,encoding='utf-8')
