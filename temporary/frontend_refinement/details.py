from pathlib import Path
root=Path(__file__).resolve().parents[2]
def edit(path,pairs):
 p=root/path;s=p.read_text(encoding='utf-8')
 for a,b in pairs:
  if a not in s:print('MISSING',path,a[:50])
  s=s.replace(a,b)
 p.write_text(s,encoding='utf-8')
for filename in ['Devices','Models','Data','System']:
 edit(f'apps/web/src/views/{filename}.vue', [('<script setup lang="ts">','<script setup lang="ts">\nimport InfoFields from "../components/InfoFields.vue";')])
edit('apps/web/src/views/Devices.vue',[
 ('<pre>{{ JSON.stringify(selected.desiredState, null, 2) }}</pre>','<InfoFields :value="selected.desiredState" :fields="[\'modelVersion\', \'planVersion\', \'inspectionEnabled\']" />'),
 ('<pre>{{ JSON.stringify(selected.reportedState, null, 2) }}</pre>','<InfoFields :value="selected.reportedState" :fields="[\'modelVersion\', \'planVersion\', \'inspectionEnabled\']" />'),
 ('<b>{{ r.type }}</b>','<b>{{ chinese(r.type) }}</b>'),
 ('<pre>{{ JSON.stringify(r.payload, null, 2) }}</pre>','<details><summary>事件数据</summary><pre>{{ JSON.stringify(r.payload, null, 2) }}</pre></details>'),
])
edit('apps/web/src/views/Models.vue',[
 ('<div class="panel" style="margin-bottom: 20px">','<div v-if="tab === \'training\'" class="panel" style="margin-bottom: 20px">'),
 ('<span class="mono">{{ text(r, "metrics") }}</span>','<InfoFields :value="r.metrics" :fields="[\'fps\', \'inferenceUs\', \'accuracy\']" />'),
 ('<pre>{{ JSON.stringify(detail, null, 2) }}</pre>','<InfoFields :value="detail" :fields="[\'name\', \'version\', \'source\', \'status\', \'architecture\', \'stage\', \'progress\', \'datasetId\', \'modelId\', \'deviceId\', \'previousVersion\', \'createdAt\', \'error\']" /><details><summary>原始数据</summary><pre>{{ JSON.stringify(detail, null, 2) }}</pre></details>'),
])
edit('apps/web/src/views/Data.vue',[
 ('<pre style="margin: 0">{{\n                JSON.stringify(r.quality, null, 2)\n              }}</pre>','<InfoFields :value="r.quality" :fields="[\'status\']" />'),
 ('<pre>{{ JSON.stringify(dataset, null, 2) }}</pre>','<InfoFields :value="dataset" :fields="[\'name\', \'version\', \'status\', \'createdAt\']" /><details><summary>版本与样本数据</summary><pre>{{ JSON.stringify(dataset, null, 2) }}</pre></details>'),
 (':title="sample.name"',':title="displayName(sample.name)"'),(':title="`${dataset.name} / V${dataset.version}`"',':title="`${displayName(dataset.name)} / V${dataset.version}`"'),
])
edit('apps/web/src/views/System.vue',[
 ('<dl class="key-values">\n            <template v-for="[k, v] in entries(health?.[key])" :key="k"\n              ><dt>{{ fieldLabel(k) }}</dt>\n              <dd>\n                {{ typeof v === "object" ? JSON.stringify(v) : chinese(v) }}\n              </dd></template\n            >\n          </dl>','<InfoFields :value="health?.[key]" />'),
 ('<pre>{{ JSON.stringify(health?.network, null, 2) }}</pre>','<div v-for="(network, index) in networks" :key="index" class="list-line"><span>{{ network.address }}</span><a :href="network.url" target="_blank" rel="noreferrer">{{ network.url }}</a></div><div v-if="!networks.length" class="note">暂无可用网络地址</div>'),
 ('<pre>{{ JSON.stringify(health?.errors, null, 2) }}</pre>','<div v-if="!recentErrors.length" class="note">暂无任务错误</div><div v-for="item in recentErrors" :key="item.id" class="error-box">{{ chinese(item.type) }}：{{ item.error }}</div>'),
 ('{{ r.name ?? r.action ?? r.type }}','{{ r.name ? displayName(r.name) : chinese(r.action ?? r.type) }}'),
 ('const entries = (value: unknown): [string, unknown][] =>\n  value && typeof value === "object" ? Object.entries(value) : [];','const networks = computed(() => (health.value?.network ?? []) as {address: string; url: string}[]);\nconst recentErrors = computed(() => (health.value?.errors ?? []) as {id: string; type: string; error: string}[]);'),
 ('color: { dark: "#244e3c", light: "#fafaf6" }','color: { dark: "#1d2129", light: "#ffffff" }'),
])
edit('apps/web/src/components/AsyncState.vue',[('<p>完成采样或创建记录后，数据会显示在这里。</p>','')])
edit('apps/web/src/components/Drawer.vue',[('<small>详情</small>','')])
edit('apps/web/src/components/AnnotationEditor.vue',[('notices.add(`标注 ${status} 已保存为新版本`);','notices.add(status === "COMPLETE" ? "标注已完成" : "草稿已保存");'),('类别 ID','类别编号'),('#244e3c','#165dff')])
edit('apps/web/index.html',[('视觉采样 / Vision Operations','视觉物联网平台'),('#244e3c','#165dff')])
edit('packages/shared/src/display.ts',[("hard: '困难样本', versionCount: '版本数', brightness: '亮度',", "hard: '困难样本', versionCount: '版本数',")])
edit('apps/mobile/src/pages.json',[('#f4f3ee','#ffffff'),('#818b7b','#86909c'),('#244e3c','#165dff'),('视觉采样 / 现场','现场工作台'),('连接工作空间','账号登录')])
for p in (root/'apps/mobile/src').rglob('*.vue'):
 s=p.read_text(encoding='utf-8')
 for a,b in {'#244e3c':'#165dff','#202b23':'#171c26','#30392e':'#242b38','#2b332b':'#242b38','#40513e':'#3c475c','#aebfa5':'#b2bdd0','#a8b69e':'#aab7ce','#b1c2a5':'#bdc9dd','#9eaf93':'#a5b1c6','#bccab3':'#bbc6d8','#c3cebb':'#c6d1e2','#60735c':'#596b89'}.items():s=s.replace(a,b)
 p.write_text(s,encoding='utf-8')
