from pathlib import Path
p=Path('apps/web/src/components/Drawer.vue'); s=p.read_text(encoding='utf-8'); Path('temporary/frontend_simplify/components_Drawer.vue').write_text(s,encoding='utf-8'); s=s.replace('title: string','title: string; wide?: boolean').replace('class="drawer"','class="drawer"\n      :class="{ wide }"');p.write_text(s,encoding='utf-8')
p=Path('apps/web/src/views/Data.vue');s=p.read_text(encoding='utf-8');s=s.replace('''    v-if="sample"
    :title''','''    v-if="sample"
    :wide="!annotating"
    :title''')
s=s.replace('''    /><template v-else
      ><ImageViewer''','''    /><div v-else class="sample-review-workspace"><div><ImageViewer compact''')
s=s.replace('''      <h3>样本审核</h3>''','''      </div><section class="review-panel"><h3>样本审核</h3>''')
s=s.replace('''      </details></template
    ></Drawer''','''      </details></section></div></Drawer''')
p.write_text(s,encoding='utf-8')
p=Path('apps/web/src/workspace.css');s=p.read_text(encoding='utf-8');s+='''
.drawer.wide { width:min(1180px, 96vw); }
.sample-review-workspace { display:grid; grid-template-columns:minmax(0, 1fr) 300px; gap:28px; align-items:start; }
.sample-review-workspace .review-panel { border-left:1px solid var(--line); padding-left:24px; }
.sample-review-workspace .image-stage { aspect-ratio:1.2; max-height:calc(100dvh - 260px); min-height:260px; }
.sample-review-workspace .form-actions { flex-direction:column; }
@media(max-width:850px) { .sample-review-workspace { grid-template-columns:1fr; gap:20px; } .sample-review-workspace .review-panel { padding:0; border:0; } .sample-review-workspace .image-stage { min-height:200px; max-height:36dvh; } }
''';p.write_text(s,encoding='utf-8')
