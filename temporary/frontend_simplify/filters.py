from pathlib import Path
p=Path('apps/web/src/views/Records.vue');s=p.read_text(encoding='utf-8');start=s.index('    <div v-if="advanced"');end=s.index('\n    <button',start);s=s[:start]+'''    <div v-if="advanced" class="filter-details">
      <label>来源<select v-model="list.source.value"><option value="">全部来源</option><option value="BOARD">{{ chinese("BOARD") }}</option><option value="SIMULATION">{{ chinese("SIMULATION") }}</option></select></label>
      <label>开始时间<input type="datetime-local" v-model="list.from.value" /></label>
      <label>结束时间<input type="datetime-local" v-model="list.to.value" /></label>
    </div>'''+s[end:];s=s.replace('''                class="table-action"
                :to''','''                class="table-action"
                @click.stop
                :to''');p.write_text(s,encoding='utf-8')
