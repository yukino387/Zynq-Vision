from pathlib import Path
def put(p,s):Path(p).write_bytes(s.encode('utf-8'))
put('apps/web/src/components/AssetThumbnail.vue','''<script setup lang="ts">
import { ref, watch, onUnmounted } from "vue";
import type { Asset } from "../types";
import { blob } from "../api";
const props = defineProps<{ assets?: Asset[]; alt?: string }>();
const image = ref(""), failed = ref(false);
let generation = 0;
watch(() => props.assets?.find(a => a.kind === "PREVIEW")?.id, async (id) => {
  const attempt = ++generation;
  if (image.value) URL.revokeObjectURL(image.value);
  image.value = ""; failed.value = false;
  if (!id) return;
  try {
    const data = await blob(`/assets/${id}/content`);
    if (attempt !== generation) return;
    image.value = URL.createObjectURL(data);
  } catch { if (attempt === generation) failed.value = true; }
}, { immediate: true });
onUnmounted(() => { generation++; if (image.value) URL.revokeObjectURL(image.value); });
</script>
<template><div class="asset-thumbnail"><img v-if="image" :src="image" :alt="alt ?? '样本图像'" loading="lazy" /><span v-else>{{ failed ? '图像读取失败' : '暂无预览' }}</span></div></template>
''')
p=Path('apps/web/src/views/Data.vue');s=p.read_text();s=s.replace('import ImageViewer','import AssetThumbnail from "../components/AssetThumbnail.vue";\nimport type { Asset } from "../types";\nimport ImageViewer');s=s.replace('const selectedIds = ref<string[]>([]),','const gallery = ref(true);\nconst assets = (row: Named) => (row.assets as Asset[] | undefined) ?? [];\nconst selectedIds = ref<string[]>([]),')
s=s.replace('  <form class="toolbar" @submit.prevent="list.filter">','''  <section v-if="tab === 'datasets'" class="lab-banner dataset-banner"><div><span class="workspace-index">05 / 数据集实验室</span><h2>整理、冻结、复现。</h2></div><div class="lab-index"><b class="mono">{{ list.total.value }}</b><span>数据集版本</span></div><div class="lab-flow"><span>01 整理样本</span><span>02 完成标注</span><span>03 冻结版本</span></div></section>
  <div v-if="['samples', 'review', 'annotation'].includes(tab)" class="library-view-control"><div><span class="workspace-index">{{ tab === 'annotation' ? '04 / 标注工作区' : '03 / 图像资源库' }}</span><span>{{ list.total.value }} 张图像</span></div><div class="segmented" aria-label="样本视图"><button :aria-pressed="gallery" :class="{ active: gallery }" @click="gallery = true">图像</button><button :aria-pressed="!gallery" :class="{ active: !gallery }" @click="gallery = false">表格</button></div></div>
  <form class="toolbar" @submit.prevent="list.filter">''',1)
s=s.replace('    ><span class="right inline-count">{{ list.total.value }} 条记录</span>','''    ><template v-if="gallery && ['samples', 'review', 'annotation'].includes(tab)"><select v-model="list.sort.value" aria-label="排序字段" @change="list.filter"><option value="createdAt">创建时间</option><option value="name">名称</option><option value="status">状态</option></select><select v-model="list.order.value" aria-label="排序方向" @change="list.filter"><option value="desc">降序</option><option value="asc">升序</option></select></template><span class="right inline-count">{{ list.total.value }} 条记录</span>''',1)
s=s.replace('    ><div class="panel table-wrap">','''    ><div v-if="gallery && ['samples', 'review', 'annotation'].includes(tab)" class="sample-gallery" :class="{ 'annotation-library': tab === 'annotation' }"><article v-for="(r, i) in selectedRows" :key="r.id" class="sample-tile" :class="{ selected: selectedIds.includes(r.id) }"><div class="sample-tile-top"><span class="mono">{{ String((list.page.value - 1) * list.pageSize.value + i + 1).padStart(3, '0') }}</span><label v-if="tab === 'samples' && auth.engineer"><input type="checkbox" v-model="selectedIds" :value="r.id" :aria-label="`选择 ${displayName(r.name)}`" />选择</label><Status :value="r.status" /></div><button class="sample-image-button" @click="open(r, tab === 'annotation')" :aria-label="`${tab === 'annotation' ? '标注' : '查看'} ${displayName(r.name)}`"><AssetThumbnail :assets="assets(r)" :alt="displayName(r.name)" /><span class="sample-open">{{ tab === 'annotation' ? '开始标注' : tab === 'review' ? '审核样本' : '查看图像' }}</span></button><div class="sample-caption"><strong>{{ displayName(r.name) }}</strong><div><span class="tag" :class="{ simulated: r.source === 'SIMULATION' }">{{ chinese(r.source) }}</span><small class="mono">{{ r.id.slice(-8) }}</small></div><small>{{ new Date(r.createdAt).toLocaleString() }}{{ r.hard ? ' · 困难样本' : '' }}</small></div></article></div><div v-else class="panel table-wrap">''',1)
s=s.replace(':wide="!annotating"',':wide="true" :class="{ \'annotation-dialog\': annotating }"')
put(p,s)
p=Path('apps/web/src/views/Models.vue');s=p.read_text();s=s.replace('  <form class="toolbar" @submit.prevent="list.filter">','''  <section v-if="tab === 'training'" class="lab-banner experiment-banner"><div><span class="workspace-index">06 / 实验工作区</span><h2>每一次训练，都有迹可循。</h2></div><div class="experiment-register"><span>运行中 <b>{{ list.items.value.filter(r => r.status === 'RUNNING').length }}</b></span><span>排队中 <b>{{ list.items.value.filter(r => r.status === 'QUEUED').length }}</b></span><small>本页任务</small></div></section>
  <section v-else-if="tab === 'deployments'" class="deployment-flow"><div v-for="(step, index) in [{ label: '待执行', states: ['PENDING', 'QUEUED', 'CREATED'] }, { label: '正在部署', states: ['RUNNING', 'DEPLOYING', 'TRANSFERRING', 'VERIFYING'] }, { label: '已生效', states: ['ACTIVE'] }, { label: '需处理', states: ['FAILED', 'ROLLED_BACK'] }]" :key="step.label"><small class="mono">0{{ index + 1 }}</small><span>{{ step.label }}</span><b class="mono">{{ list.items.value.filter(r => step.states.includes(r.status ?? '')).length }}</b></div><small class="flow-caption">本页部署状态</small></section>
  <section v-else-if="tab === 'benchmarks'" class="benchmark-scope"><div><span class="workspace-index">07 / 性能实验室</span><h2>运行表现，逐项对照。</h2></div><div class="benchmark-scale"><span>吞吐 / FPS</span><div v-for="r in list.items.value.slice(0, 5)" :key="r.id" class="benchmark-track"><span>{{ displayName(r.name) }}</span><meter v-if="metricFps(r) !== null" min="0" :max="Math.max(30, ...list.items.value.map(row => metricFps(row) ?? 0))" :value="metricFps(r) ?? 0" :aria-label="`${displayName(r.name)} 帧率`" /><span v-else class="muted">未上报</span><b class="mono">{{ metricFps(r)?.toFixed(2) ?? '—' }}</b></div><small v-if="!list.items.value.length" class="muted">评估完成后显示实际指标</small></div></section>
  <form class="toolbar" @submit.prevent="list.filter">''',1)
s=s.replace('const route =', '''const metricFps = (row: Named): number | null => {
  const value = (row.metrics as { fps?: unknown } | null)?.fps;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
};
const route =''',1)
put(p,s)
p=Path('apps/web/src/views/Overview.vue');s=p.read_text().replace('import Sparkline','import ImageViewer from "../components/ImageViewer.vue";\nimport Sparkline');a=s.index('      <div class="panel section-space">',s.index('<template v-if="data">'));b=s.index('      <!-- 数据闭环',a)
old=s[a:b];old=old.replace('class="panel section-space"','class="control-room-readouts"',1)
new='''      <section class="control-room"><RouterLink to="/workbench" class="control-room-camera"><div class="canvas-title"><span>当前设备 / {{ displayName(current?.name ?? '未选择') }}</span><Status :value="current?.connectionState" /></div><ImageViewer compact :jpeg="current?.connectionState === 'ONLINE' ? devices.previews[current.id]?.jpeg : undefined" :boxes="current?.connectionState === 'ONLINE' ? devices.previews[current.id]?.detections : undefined" /><span class="control-room-enter">打开检测工作台 →</span></RouterLink>'''+old+'''      </section>

'''
# Avoid interactive viewer buttons nested in a link: keep link as footer only.
new=new.replace('<RouterLink to="/workbench" class="control-room-camera">','<div class="control-room-camera">').replace('<span class="control-room-enter">打开检测工作台 →</span></RouterLink>','<RouterLink to="/workbench" class="control-room-enter">打开检测工作台 →</RouterLink></div>')
s=s[:a]+new+s[b:];put(p,s)
p=Path('apps/web/src/views/Devices.vue');s=p.read_text().replace('<details v-if="tab === \'registry\'" class="advanced-metrics">','<details v-if="tab === \'registry\'" class="advanced-metrics" open>');put(p,s)
# Annotation becomes a canvas plus inspector while preserving pointer and save handlers.
p=Path('apps/web/src/components/AnnotationEditor.vue');s=p.read_text();start=s.index('<template>');body=s[start:];body=body.replace('<template>','<template>\n  <div class="annotation-workspace">',1).replace('  <div style="overflow: auto; max-height: 500px; border: 1px solid var(--line)">','  <div class="annotation-canvas-scroll">',1);body=body.replace('  <p class="note">','  <aside class="annotation-inspector"><h3>标注对象 <span class="mono">{{ boxes.length }}</span></h3>\n  <p class="note">',1);body=body.replace('</template>','  </aside></div>\n</template>');put(p,s[:start]+body)
