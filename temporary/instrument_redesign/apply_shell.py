from pathlib import Path
root=Path('.')
out=Path('temporary/instrument_redesign/before');out.mkdir(exist_ok=True)
for base in ['apps/web/src','apps/mobile/src']:
 for p in Path(base).rglob('*'):
  if p.suffix in ('.vue','.css','.json','.ts'):
   q=out/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
def put(path,s):Path(path).write_bytes(s.encode('utf-8'))
p=Path('apps/web/src/App.vue');s=p.read_text(encoding='utf-8');s=s.replace('expanded = ref<string[]>([]);','expanded = ref<string[]>(navItems.map((item) => String(item.name)));')
s=s.replace('<RouterLink to="/" class="brand">视觉物联网平台</RouterLink>','<RouterLink to="/" class="brand"><span>视觉物联网平台</span><small>边缘视觉 · 设备工作站</small></RouterLink>')
s=s.replace('<template v-for="entry in sidebarItems"','<template v-for="(entry, navIndex) in sidebarItems"')
s=s.replace('{{ entry.item.meta.title\n              }}<span','<span class="nav-number">{{ String(navIndex + 1).padStart(2, "0") }}</span>{{ entry.item.meta.title\n              }}<span')
s=s.replace('>{{ entry.item.meta?.title }}</RouterLink','><span class="nav-number">{{ String(navIndex + 1).padStart(2, "0") }}</span>{{ entry.item.meta?.title }}</RouterLink')
s=s.replace('<main id="main" tabindex="-1">','<main id="main" tabindex="-1" :data-page="String(route.name)" :data-tab="String(route.params.tab || route.meta.defaultTab || \'\')">')
put(p,s)
p=Path('apps/web/src/main.ts');s=p.read_text().replace('import "./workspace.css";','import "./workspace.css";\nimport "./instrument.css";');put(p,s)
p=Path('apps/web/src/views/Operations.vue');s=p.read_text();script=s[:s.index('</script>')]
script=script.replace('import ImageViewer','import type { Preview } from "../stores/devices";\nimport Sparkline from "../components/Sparkline.vue";\nimport ImageViewer')
script=script.replace('const detections = computed(() => preview.value?.detections ?? null);','''const frames = ref<Preview[]>([]), held = ref<Preview | null>(null);
let lastFilmstripAt = 0;
watch(() => device.value?.id, () => { frames.value = []; held.value = null; lastFilmstripAt = 0; });
watch(preview, (frame) => {
  if (!frame || Date.now() - lastFilmstripAt < 1000) return;
  lastFilmstripAt = Date.now();
  frames.value = [...frames.value, frame].slice(-8);
});
const shown = computed(() => held.value ?? preview.value);
const detections = computed(() => shown.value?.detections ?? null);
const latency = computed(() => devices.history.map(h => h.inferenceUs === null ? null : h.inferenceUs / 1000));
const metric = (v: number | null | undefined) => v == null ? "—" : (v / 1000).toFixed(2);''')
# Keep existing saved-record table and all actions.
recent=s[s.index('  <section class="panel section-space">',s.index('  </div>\n\n  <section class="panel section-space">')):s.index('</template>')]
template='''</script>
<template>
  <div class="page-heading instrument-heading">
    <div><span class="workspace-index">01 / 视觉检测</span><h1>检测工作台<span class="heading-period">.</span></h1></div>
    <div class="heading-actions"><Status :value="device?.connectionState" /><span class="mono instrument-id">{{ device?.type ?? '无设备' }}</span></div>
  </div>
  <div class="device-control console-controls">
    <label>检测设备<select v-model="devices.selected" aria-label="当前设备"><option v-for="d in devices.devices" :key="d.id" :value="d.id">{{ displayName(d.name) }}</option></select></label>
    <span v-if="device?.source === 'SIMULATION'" class="tag simulated">模拟设备</span>
    <div class="control-actions" v-if="auth.engineer">
      <button v-if="device?.connectionState !== 'ONLINE'" class="primary" :disabled="connecting || !device" @click="connect">{{ connecting ? '连接中…' : '连接设备' }}</button>
      <template v-else><button v-if="!inspecting" class="primary" :disabled="connecting" @click="control(true)">开始检测</button><button v-else :disabled="connecting" @click="control(false)">暂停检测</button><RouterLink :to="{ name: 'diagnostics' }" class="text-button">设备设置</RouterLink></template>
    </div>
    <span v-else-if="device?.connectionState !== 'ONLINE'" class="muted">请联系工程师连接设备</span>
  </div>
  <p v-if="device?.error" class="error-box">{{ device.error }}</p>
  <div class="vision-workspace">
    <section class="vision-canvas">
      <div class="canvas-title"><span><i class="signal-dot" :class="{ live: !!preview && !held }"></i>{{ held ? '帧回看' : '实时图像' }}</span><span class="mono">{{ shown ? `${shown.width} × ${shown.height}` : '等待图像源' }}<span v-if="shown"> / #{{ shown.frameId }}</span></span></div>
      <ImageViewer compact :jpeg="shown?.jpeg" :boxes="inspecting ? shown?.detections : undefined" :width="shown?.width" :height="shown?.height" />
      <div class="canvas-footer"><span>{{ device?.connectionState !== 'ONLINE' ? '选择设备并连接以接收画面' : held ? '正在查看缓存在此页面的历史帧' : '设备连续采集' }}</span><button v-if="held" class="return-live" @click="held = null">返回实时画面</button><time class="mono">{{ shown ? new Date(shown.receivedAt).toLocaleTimeString() : '—' }}</time></div>
    </section>
    <aside class="result-inspector">
      <div class="inspector-title"><span>结果检查器</span><span class="mono">02</span></div>
      <div class="live-verdict" :class="{ candidate: inspecting && detections?.length, clear: inspecting && preview && detections?.length === 0 }">
        <span class="verdict-caption">{{ held ? '回看帧 · 候选检测' : '当前帧 · 候选检测' }}</span>
        <strong>{{ !shown ? '等待图像' : !inspecting ? '检测暂停' : detections === null ? '仅图像' : detections.length ? '待复核' : '未检出缺陷' }}</strong>
        <span>{{ !shown ? '等待设备返回完整帧' : !inspecting ? '开始检测后显示候选结果' : detections === null ? '本帧没有推理输出' : detections.length ? `${detections.length} 处候选目标 · 需人工确认` : '本帧没有候选目标' }}</span>
      </div>
      <div class="inspector-section"><h3>检出目标 <span class="mono">{{ String(detections?.length ?? 0).padStart(2, '0') }}</span></h3>
        <div class="detection-list"><div v-for="(box, i) in detections ?? []" :key="i" class="detection-item"><span class="target-number">{{ String(i + 1).padStart(2, '0') }}</span><div><b>{{ displayName(box.label) }}</b><small class="mono">{{ Math.round(box.x1) }},{{ Math.round(box.y1) }} → {{ Math.round(box.x2) }},{{ Math.round(box.y2) }}</small></div><strong class="mono">{{ (box.confidence * 100).toFixed(1) }}<small>%</small></strong></div><p v-if="!detections?.length" class="inspector-empty">{{ shown ? '暂无候选目标' : '等待检测数据' }}</p></div>
      </div>
      <div class="inspector-section model-readout"><h3>运行模型</h3><b class="mono">{{ device?.reportedState.modelVersion ?? '版本未上报' }}</b><small>{{ chinese(device?.runtimeState) }} · {{ chinese(device?.syncState) }}</small></div>
      <div class="inspector-section telemetry-trend"><h3>推理耗时趋势 <span>ms</span></h3><Sparkline :values="latency" label="推理耗时" unit=" ms" /></div>
    </aside>
    <div class="device-telemetry"><div><small>帧率</small><strong>{{ device?.telemetry?.fps?.toFixed(2) ?? '—' }}<em>FPS</em></strong></div><div><small>推理耗时</small><strong>{{ metric(device?.telemetry?.inferenceUs) }}<em>ms</em></strong></div><div><small>采集</small><strong>{{ metric(device?.telemetry?.captureUs) }}<em>ms</em></strong></div><div><small>预处理</small><strong>{{ metric(device?.telemetry?.conversionUs) }}<em>ms</em></strong></div><div><small>传输</small><strong>{{ metric(device?.telemetry?.transferUs) }}<em>ms</em></strong></div><div><small>错误码</small><strong :class="{ 'tone-crit': device?.telemetry?.errorCode }">{{ device?.telemetry?.errorCode ?? '—' }}</strong></div></div>
    <section class="frame-filmstrip"><div class="filmstrip-label"><b>连续帧</b><small>每秒留取 · 最近 8 帧</small><button v-if="held" @click="held = null">实时</button></div><div class="filmstrip-track"><button v-for="frame in frames" :key="frame.frameId" class="frame-thumb" :class="{ selected: held?.frameId === frame.frameId }" @click="held = frame" :aria-label="`回看帧 ${frame.frameId}`"><img :src="`data:image/jpeg;base64,${frame.jpeg}`" alt="检测帧缩略图" /><span><i :class="frame.detections === null ? 'unclassified' : frame.detections.length ? 'has-target' : 'no-target'"></i>#{{ frame.frameId }}</span></button><div v-if="!frames.length" class="filmstrip-empty">完整帧到达后在此连续排列</div></div></section>
    <div class="capture-bar console-capture"><label class="capture-task">采样任务<select v-model="tasks.selected" aria-label="关联采样任务"><option value="">独立采样</option><option v-for="t in tasks.items" :key="t.id" :value="t.id">{{ displayName(t.name) }}</option></select></label><span class="muted capture-hint">{{ captureBlocked || (held ? '采样保存设备当前实时帧' : '保存图像与检测记录') }}</span><button class="primary capture" :class="{ busy }" @click="capture" :disabled="busy || connecting || !!captureBlocked" :title="captureBlocked">{{ busy ? '处理中…' : held ? '采样实时帧' : '采样当前帧' }}</button></div>
  </div>
'''
put(p,script+template+recent+'</template>\n')
# Auth: functional form stays intact; instrument-like typographic front panel.
p=Path('apps/web/src/components/AuthPanel.vue');s=p.read_text().replace('<div class="auth-wrap">','''<section class="auth-faceplate"><span class="workspace-index">边缘视觉 / 设备工作站</span><h2>看见细节。<br />作出判断<span>.</span></h2><div class="auth-instrument"><span>视觉检测</span><span>数据采样</span><span>模型部署</span></div><small>视觉物联网平台</small></section><div class="auth-wrap">''');put(p,s)
