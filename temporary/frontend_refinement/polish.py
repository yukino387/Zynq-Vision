from pathlib import Path
import re
root=Path(__file__).resolve().parents[2]
def edit(path,pairs):
 p=root/path;s=p.read_text(encoding='utf-8')
 for a,b in pairs:s=s.replace(a,b)
 p.write_text(s,encoding='utf-8')

edit('apps/web/src/views/Operations.vue',[("'CAPTURE'","'采集'"),("'CONVERSION'","'预处理'"),("'INFERENCE'","'推理'"),("'TRANSFER'","'传输'"),("'FRAME CYCLE'","'帧周期'"),('<h3>最近检测 <span class="inline-count"></span></h3>','<h3>最近检测</h3>')])
edit('apps/web/src/components/InspectionDetail.vue',[('<dt>INFERENCE</dt>','<dt>推理耗时</dt>'),('<dt>DEVICE</dt>','<dt>设备编号</dt>')])
edit('apps/web/src/views/Models.vue',[('＋\n',''),('text(r, "stage")','chinese(text(r, "stage"))'),('"任务已提交；最终状态以执行回执为准"','"任务已提交"')])
edit('apps/web/src/views/Devices.vue',[("'网络状态_LOST'","'NETWORK_LOST'"),(':title="selected.name"',':title="displayName(selected.name)"')])
edit('apps/mobile/src/pages/capture/index.vue',[('imuAvailable ? motion?.captureStability : "IMU 不可用"','imuAvailable ? chinese(motion?.captureStability) : "姿态传感器不可用"'),('        · </text','        </text'),('range-key="name"', 'range-key="name"')])
edit('apps/mobile/src/pages/sync/index.vue',[('● 网络状态 AVAILABLE','● 网络可用'),('{{\n          item.status\n        }}','{{ chinese(item.status) }}')])
edit('apps/mobile/src/pages/home/index.vue',[(' · MODEL',' · 模型'),('RUNTIME','运行状态')])
edit('apps/mobile/src/pages/detail/index.vue',[('>SIMULATED</text','>模拟推理</text')])
edit('apps/mobile/src/pages/pair/index.vue',[('在 Web 端「系统 → App 配对」生成一次性二维码。','扫描控制台生成的配对二维码。')])
edit('apps/web/src/components/AnnotationEditor.vue',[("ref(\"defect\")","ref(\"缺陷\")"),('`标注版本已保存 · ${status}`','status === "COMPLETE" ? "标注已完成" : "草稿已保存"')])
# Inline visible values use the same Chinese labels on both clients.
for p in list((root/'apps/mobile/src').rglob('*.vue'))+list((root/'apps/web/src').rglob('*.vue')):
 s=p.read_text(encoding='utf-8')
 s=s.replace('>{{\n          item.status\n        }}','>{{ chinese(item.status) }}')
 s=re.sub(r'{{\s*i\.sample\.name\s*}}','{{ displayName(i.sample.name) }}',s)
 s=re.sub(r'{{\s*t\.status\s*}}','{{ chinese(t.status) }}',s)
 s=re.sub(r'<p class="(?:note|subtitle)"[^>]*>\s*</p>','',s)
 s=re.sub(r'<text class="subtitle">\s*</text\s*>','',s)
 s=re.sub(r'<p class="note">\s*</p>','',s)
 p.write_text(s,encoding='utf-8')

# Replace editorial styling with a compact product layout.
(root/'apps/web/src/style.css').write_text('''button { border:1px solid var(--line); background:#fff; color:var(--ink); border-radius:6px; padding:8px 14px; line-height:1.5; transition:background .15s,border-color .15s; }
button:hover:not(:disabled) { background:#f7f8fa; border-color:#b7c1d1; }
.primary { background:var(--forest); color:#fff; border-color:var(--forest); }
.primary:hover:not(:disabled) { background:#4080ff; border-color:#4080ff; color:#fff; }
.danger { color:var(--red); }
input,select,textarea { border:1px solid #dcdfe6; border-radius:6px; padding:9px 12px; background:#fff; color:var(--ink); min-width:0; }
input:hover,select:hover,textarea:hover { border-color:#a8b2c1; }
input[type=checkbox] { accent-color:var(--forest); }
label { display:grid; gap:8px; margin:16px 0; font-size:13px; }
small,.eyebrow { font-size:12px; color:var(--muted); line-height:1.6; letter-spacing:0; }
.mono { font-family:var(--mono); font-variant-numeric:tabular-nums; }
h1,h2,h3,p { margin-top:0; }
h1 { font-size:24px; font-weight:600; margin-bottom:0; letter-spacing:0; }
h2 { font-size:20px; font-weight:600; }
h3 { font-size:15px; font-weight:600; }
p { line-height:1.7; }
.muted { color:var(--muted); }
.shell { display:grid; grid-template-columns:208px minmax(0,1fr); min-height:100vh; }
.sidebar { position:fixed; inset:0 auto 0 0; width:208px; background:#fff; border-right:1px solid var(--line); display:flex; flex-direction:column; padding:0 12px; z-index:5; }
.brand { display:flex; align-items:center; height:64px; padding:0 14px; margin-bottom:20px; color:#1d2129; text-decoration:none; font-size:18px; font-weight:650; white-space:nowrap; }
nav { display:grid; gap:6px; }
nav a { display:block; text-decoration:none; padding:13px 18px; border-radius:6px; color:#4e5969; font-size:14px; }
nav a:hover { background:#f5f7fa; }
nav a.selected { background:#eaf1ff; color:var(--forest); font-weight:600; }
.session { margin-top:auto; border-top:1px solid var(--line); padding:18px 8px; display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:13px; }
.session>div { min-width:0; overflow-wrap:anywhere; }
.session small { display:block; margin-top:4px; }
.session button { border:0; background:none; color:#86909c; padding:6px; flex-shrink:0; }
.main-shell { grid-column:2; min-width:0; display:flex; flex-direction:column; }
.topbar { height:64px; padding:0 28px; display:flex; align-items:center; justify-content:space-between; background:#fff; border-bottom:1px solid var(--line); font-size:14px; }
.topbar-actions { display:flex; gap:28px; align-items:center; font-size:12px; color:#86909c; }
.topbar a { text-decoration:none; }
.connection-dot { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:7px; background:var(--amber); }
.connection-dot.live { background:var(--green); }
main { flex:1; min-width:0; padding:28px; }
.page-heading { display:flex; justify-content:space-between; align-items:center; gap:20px; min-height:40px; margin-bottom:24px; }
.page-heading p { color:var(--muted); font-size:13px; margin:8px 0 0; }
.heading-actions,.toolbar { display:flex; align-items:center; gap:10px; }
.heading-actions select { max-width:260px; }
.toolbar { flex-wrap:wrap; margin:20px 0; }
.toolbar input { width:220px; }
.toolbar .right { margin-left:auto; }
.tabs { display:flex; gap:28px; border-bottom:1px solid var(--line); margin-bottom:24px; overflow-x:auto; white-space:nowrap; }
.tabs a { padding:0 0 14px; text-decoration:none; color:#4e5969; font-size:14px; }
.tabs a.router-link-active { border-bottom:2px solid var(--forest); color:var(--forest); font-weight:600; }
.panel { background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.panel-head { min-height:55px; padding:16px 20px; border-bottom:1px solid #f0f1f4; display:flex; align-items:center; justify-content:space-between; gap:12px; }
.panel-head h3 { margin:0; }
.panel-body { padding:20px; }
.status { font-family:var(--font); font-size:12px; white-space:nowrap; display:inline-flex; gap:6px; align-items:center; }
.status.positive { color:var(--green); }
.status.negative { color:var(--red); }
.status.neutral { color:var(--amber); }
.status span { font-size:7px; }
.tag { display:inline-block; font:12px var(--font); padding:3px 8px; border:1px solid #e5e6eb; border-radius:4px; color:#4e5969; background:#f7f8fa; }
.tag.simulated { color:#b57600; border-color:#ffe5b5; background:#fff7e8; }
.stat-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); margin-bottom:24px; gap:16px; }
.stat-strip>div { border:1px solid var(--line); border-radius:8px; background:#fff; padding:20px; }
.stat-strip small { display:block; font-size:13px; color:#4e5969; }
.stat-strip strong { display:block; font-family:var(--mono); font-size:28px; font-weight:600; margin:14px 0 8px; }
.stat-strip em { font-style:normal; font-size:12px; color:var(--muted); }
.operation-grid { display:grid; grid-template-columns:minmax(0,1.65fr) minmax(280px,1fr); gap:20px; align-items:start; }
.split { display:grid; grid-template-columns:minmax(0,1fr) 310px; gap:20px; }
.two-columns { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; }
.key-values { display:grid; grid-template-columns:1fr 1fr; margin:0; }
.key-values dt,.key-values dd { margin:0; border-bottom:1px solid #f0f1f4; padding:12px 0; font-size:13px; }
.key-values dt { color:#86909c; }
.key-values dd { text-align:right; overflow-wrap:anywhere; }
.section-space { margin-top:20px; }
.image-toolbar { padding:12px 16px; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; gap:10px; font-size:12px; flex-wrap:wrap; }
.image-toolbar>div { display:flex; align-items:center; gap:6px; }
.image-toolbar button,.image-toolbar select { padding:4px 7px; font-size:12px; }
.image-stage { position:relative; display:flex; align-items:center; justify-content:center; overflow:hidden; aspect-ratio:1.2; background:#eef0f3; touch-action:none; min-height:250px; user-select:none; }
.image-plane { width:100%; max-width:560px; position:relative; transform-origin:center; line-height:0; }
.image-plane img { width:100%; display:block; }
.image-plane svg { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
.image-plane rect { stroke:#165dff; stroke-width:2; fill:none; }
.image-plane rect.box-label { fill:#165dff; stroke:none; }
.image-plane text { fill:#fff; font-family:var(--font); font-size:12px; }
.image-empty { text-align:center; display:grid; gap:12px; color:var(--muted); max-width:80%; line-height:1.8; }
.image-empty>b { font-size:14px; font-weight:500; }
.table-wrap { overflow:auto; }
table { width:100%; border-collapse:collapse; white-space:nowrap; font-size:13px; }
th { text-align:left; font-size:13px; font-weight:500; color:#4e5969; padding:15px 20px; border-bottom:1px solid var(--line); background:#f7f8fa; }
td { padding:18px 20px; border-bottom:1px solid #f0f1f4; }
tbody tr:last-child td { border:0; }
tbody tr:hover { background:#f9fbff; }
td small { display:block; font-size:12px; margin-top:5px; }
td .mono { font-size:12px; }
.table-action { color:var(--forest); padding:4px 6px; font-size:13px; border:0; background:none; }
.empty { padding:55px 24px; color:var(--muted); text-align:center; line-height:1.8; }
.error-box { padding:14px; color:var(--red); background:#fff2f0; border:1px solid #ffccc7; border-radius:6px; font-size:13px; overflow-wrap:anywhere; }
.error-box button { margin-left:10px; }
.scrim { position:fixed; inset:0; background:#1d212966; z-index:20; display:flex; justify-content:flex-end; }
.drawer { width:min(760px,95vw); height:100%; background:#fff; display:flex; flex-direction:column; box-shadow:-8px 0 32px #00000014; }
.drawer>header { padding:22px 24px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); }
.drawer>header h2 { margin:0; }
.drawer>header small { display:none; }
.drawer-body { padding:24px; overflow:auto; flex:1; }
.drawer .image-stage { max-height:440px; }
.toasts { position:fixed; right:24px; bottom:24px; z-index:50; display:grid; gap:8px; max-width:550px; }
.toasts>button { background:#fff; color:var(--ink); box-shadow:0 4px 24px #00000018; text-align:left; padding:15px 20px; overflow-wrap:anywhere; }
.toasts>button.error { color:var(--red); }
.toasts span { float:right; margin-left:18px; color:var(--muted); font-size:12px; }
pre { white-space:pre-wrap; word-break:break-word; background:#f7f8fa; padding:15px; border-radius:6px; font-size:12px; line-height:1.8; }
.list-line { padding:16px 0; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; gap:15px; }
.list-line:last-child { border:0; }
.list-line small { display:block; }
.bar { height:4px; background:#eef0f3; border-radius:2px; overflow:hidden; }
.bar>span { display:block; height:100%; background:var(--forest); }
.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.form-grid label { margin:0; }
.login-screen { min-height:100vh; display:flex; justify-content:center; align-items:center; padding:32px; background:#f5f7fa; }
.login-form { width:400px; max-width:100%; padding:40px; border:1px solid var(--line); border-radius:12px; background:#fff; box-shadow:0 8px 40px #1d212908; }
.login-form h1 { font-size:24px; margin-bottom:12px; }
.login-form>.muted { margin-bottom:32px; }
.login-form input { width:100%; }
.login-form .primary { width:100%; margin-top:16px; padding:11px; }
.check-row { display:flex; gap:8px; align-items:center; }
.check-row input { width:16px; }
.pagination { display:flex; justify-content:flex-end; gap:12px; align-items:center; margin:20px 0; color:#4e5969; font-size:13px; }
.annotation-stage { position:relative; line-height:0; touch-action:none; }
.annotation-stage img { width:100%; }
.annotation-stage svg { position:absolute; inset:0; width:100%; height:100%; cursor:crosshair; }
.annotation-stage rect { stroke:var(--forest); fill:#165dff12; stroke-width:2; }
.annotation-stage text { fill:var(--forest); font-size:12px; }
.result-line { display:flex; justify-content:space-between; align-items:center; padding:16px 0; border-bottom:1px solid #f0f1f4; gap:10px; }
.result-line p { margin:5px 0 0; font-size:14px; }
.pipeline { display:flex; padding:20px 0; }
.pipeline>div { flex:1; border-right:1px solid var(--line); padding:0 20px; }
.pipeline>div:last-child { border:0; }
.pipeline small { font-size:12px; display:block; }
.pipeline b { font:18px var(--mono); display:block; margin-top:10px; }
.pipeline em { font-size:12px; font-style:normal; color:var(--muted); }
.note { font-size:12px; line-height:1.8; color:var(--muted); padding:10px 0; }
.inline-count { font-size:12px; color:var(--muted); }
details>summary { cursor:pointer; color:#4e5969; font-size:13px; padding:10px 0; }
.detail-fields { margin:16px 0; }
.detail-fields dt { max-width:220px; }
@media(min-width:1700px) { main { padding:32px 40px; } .image-stage { max-height:650px; } }
@media(max-width:1200px) { .shell { grid-template-columns:184px minmax(0,1fr); } .sidebar { width:184px; } .brand { font-size:16px; padding:0 10px; } main { padding:24px; } .page-heading { flex-wrap:wrap; } .operation-grid { grid-template-columns:minmax(0,1.2fr) minmax(280px,1fr); } .stat-strip>div { padding:16px; } }
@media(max-width:1000px) { .operation-grid,.split,.two-columns { grid-template-columns:1fr; } .stat-strip { grid-template-columns:repeat(2,minmax(0,1fr)); } .topbar-actions { gap:16px; } .heading-actions { flex-wrap:wrap; } }
@media(max-width:640px) { .shell { display:block; } .sidebar { position:static; width:100%; height:auto; padding:0 16px; border-bottom:1px solid var(--line); } .brand { height:56px; margin:0; } nav { display:flex; overflow:auto; gap:4px; padding:0 0 12px; } nav a { flex-shrink:0; padding:9px 12px; font-size:13px; } .session { display:none; } .topbar { height:48px; padding:0 16px; } main { padding:20px 16px; } h1 { font-size:22px; } .topbar-actions { font-size:11px; } .topbar-actions>a { display:none; } .stat-strip { gap:10px; } .stat-strip>div { padding:14px; } .pipeline { flex-wrap:wrap; gap:20px; } .pipeline>div { flex:1 1 30%; } .login-screen { padding:20px; } .login-form { padding:32px 24px; } }
''',encoding='utf-8')

# Slightly denser mobile typography, consistent Chinese product styling.
p=root/'apps/mobile/src/App.vue';s=p.read_text(encoding='utf-8')
s=s.replace('letter-spacing: 1.8px','letter-spacing: 0').replace('font-size: 29px','font-size: 26px').replace('font-size: 10px','font-size: 12px').replace('font-size: 11px','font-size: 12px')
s=s.replace('border-radius: 14px','border-radius: 10px').replace('border-radius: 12px','border-radius: 10px')
p.write_text(s,encoding='utf-8')
