from pathlib import Path
p=Path('apps/web/src/views/Data.vue');s=p.read_text(encoding='utf-8');needle='const selectedRows = computed(() => list.items.value);';s=s.replace(needle,'''watch(() => selectedIds.value.length, (count, previous) => {
  if (count > 0 && previous === 0) void selectDataset();
});
'''+needle);s=s.replace('@focus="selectDataset"','');s=s.replace('"/datasets?status=DRAFT"','"/datasets?status=DRAFT&pageSize=100"');p.write_text(s,encoding='utf-8')
