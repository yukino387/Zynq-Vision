from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=root/'apps/web/src/views/InspectionDetail.vue';s=p.read_text(encoding='utf-8')
s=s.replace('import { chinese, displayName, reasonLabel } from "@vision/shared";\n','')
start=s.index('    <template v-if="inspection">');end=s.index('    </template>',start)+len('    </template>')
s=s[:start]+'''    <div v-if="inspection" class="panel panel-body"><InspectionDetail :inspection="inspection" @saved="load" /></div>'''+s[end:]
p.write_text(s,encoding='utf-8')
p=root/'apps/web/src/components/InspectionDetail.vue';s=p.read_text(encoding='utf-8')
s=s.replace('<Status :value="inspection.result" />','<span class="muted">设备判定</span><Status :value="inspection.result" /><span v-if="inspection.reviews.length" class="tag ok">已复核</span>')
s=s.replace('<button class="right" @click="raw">','<button class="right" @click="raw" :disabled="!inspection.sample.assets.some(a => a.kind === \'RAW\')">')
s=s.replace('  <ImageViewer','  <div class="inspection-workspace"><div><ImageViewer',1)
s=s.replace('  <dl class="key-values">','  <details class="section-space"><summary>采集与版本信息</summary><dl class="key-values">',1)
s=s.replace('  </dl>\n  <h3 class="section-space">人工复核</h3>','  </dl></details></div><section class="review-panel">\n  <h3>人工复核</h3>',1)
s=s.replace('</template>','</section></div>\n</template>',1)
p.write_text(s,encoding='utf-8')
p=root/'apps/web/src/views/Records.vue';s=p.read_text(encoding='utf-8').replace('<th>复核</th>','<th>人工复核</th>').replace('<th>结果</th>','<th>设备判定</th>')
s=s.replace('label="结果"','label="设备判定"').replace('<td>{{ i.reviews.length }}</td>','<td>{{ i.reviews.length ? "已复核" : i.result === "REVIEW" ? "待复核" : "—" }}</td>')
p.write_text(s,encoding='utf-8')
p=root/'apps/web/src/App.vue';s=p.read_text(encoding='utf-8').replace('return nav.value.filter((item) => names.includes(String(item.name)));','return nav.value.filter((item) => names.includes(String(item.name))).sort((a,b)=>names.indexOf(String(a.name))-names.indexOf(String(b.name)));')
p.write_text(s,encoding='utf-8')
p=root/'apps/server/src/devices/simulator.ts';s=p.read_text(encoding='utf-8').replace('>SIMULATED FRAME ${frameId}</text>',' font-family="Microsoft YaHei, sans-serif">模拟画面 ${frameId}</text>')
p.write_text(s,encoding='utf-8')
p=root/'apps/web/src/style.css';s=p.read_text(encoding='utf-8')+'''
.inspection-workspace {display:grid;grid-template-columns:minmax(0,1.6fr) minmax(280px,1fr);gap:32px;align-items:start;}
.review-panel {border-left:1px solid var(--line);padding-left:28px;}
.inspection-workspace .image-stage {aspect-ratio:1.1;max-height:520px;}
.review-panel .form-grid {display:block;}
.review-panel .form-grid label {margin:16px 0;}
@media(max-width:1000px){.inspection-workspace{grid-template-columns:1fr;}.review-panel{border-left:0;border-top:1px solid var(--line);padding:24px 0 0;}}
'''
p.write_text(s,encoding='utf-8')
