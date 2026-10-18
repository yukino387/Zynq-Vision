from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=root/'apps/web/src/style.css';s=p.read_text(encoding='utf-8')
s=s.replace('grid-template-columns: 208px minmax(0, 1fr)','grid-template-columns: 224px minmax(0, 1fr)').replace('width: 208px','width: 224px')
s=s.replace('  background: var(--surface-2);\n  border-right: 1px solid var(--line);\n  display: flex;', '  background: var(--surface);\n  border-right: 1px solid var(--line);\n  display: flex;',1)
s=s.replace('margin-bottom: 20px;\n  color: var(--ink);','margin-bottom: 6px;\n  color: var(--ink);',1)
s=s.replace('nav {\n  display: grid;\n  gap: 6px;','nav {\n  display: grid;\n  gap: 4px;')
s=s.replace('padding: 13px 18px;\n  border-radius: var(--radius);','padding: 11px 18px;\n  border-radius: var(--radius);',1)
s=s.replace('nav a.selected {\n  background: var(--surface-2);\n  box-shadow: none;\n  color: var(--ink);','nav a.selected {\n  background: color-mix(in srgb, var(--forest) 9%, transparent);\n  box-shadow: none;\n  color: var(--forest);',1)
s=s.replace('  background: var(--surface-2);\n  border-bottom: 1px solid var(--line);\n  font-size: 14px;','  background: var(--surface);\n  border-bottom: 1px solid var(--line);\n  font-size: 14px;',1)
s+='''
/* Workspace navigation and task-oriented screens. */
.nav-group-label {color:var(--muted);font-size:11px;padding:22px 18px 8px;}
.sidebar nav {overflow-y:auto;padding-bottom:20px;}
.workspace-tabs {display:flex;gap:28px;margin:-28px -28px 28px;padding:0 28px;background:var(--surface);border-bottom:1px solid var(--line);overflow-x:auto;white-space:nowrap;}
.workspace-tabs a {padding:17px 0 15px;border-radius:0;font-size:14px;border-bottom:2px solid transparent;}
.workspace-tabs a.active {border-bottom-color:var(--forest);color:var(--forest);font-weight:600;}
.workspace-tabs a:hover {background:transparent;color:var(--forest);}
.text-button {border:0;background:transparent;color:var(--forest);padding:3px 5px;text-decoration:none;cursor:pointer;font-size:13px;}
.button-link {display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line);border-radius:var(--radius);padding:9px 16px;text-decoration:none;background:var(--surface);font-size:14px;}
.button-link.primary {background:var(--forest);border-color:var(--forest);color:var(--forest-ink);}
.auth-wrap {width:420px;max-width:100%;}
.auth-product {font-size:22px;font-weight:650;text-align:center;margin-bottom:26px;}
.auth-wrap .login-form {width:100%;padding:32px 36px;border:1px solid var(--line);border-radius:12px;box-shadow:0 8px 40px #00000006;}
.auth-caption {font-size:13px;margin:12px 0 28px;}
.auth-switch {margin:22px 0 0;text-align:center;font-size:13px;color:var(--muted);}
.login-form>button.text-button {display:block;margin:10px auto 0;}
.overview-metrics {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;}
.metric-card {display:grid;gap:14px;border:1px solid var(--line);border-radius:8px;padding:24px;background:var(--surface);text-decoration:none;}
.metric-card:hover {border-color:var(--forest);}
.metric-card>span {font-size:13px;color:var(--ink-2);}
.metric-card strong {font-size:34px;font-weight:600;line-height:1.2;font-variant-numeric:tabular-nums;}
.metric-card strong em {font-size:16px;font-weight:400;color:var(--muted);font-style:normal;}
.metric-card small {font-size:12px;}
.quick-actions {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));padding:24px 0;}
.quick-actions>a {padding:4px 28px;border-right:1px solid var(--line);text-decoration:none;}
.quick-actions>a:last-child {border:0;}
.quick-actions b {font-size:16px;font-weight:600;}
.quick-actions p {color:var(--muted);font-size:13px;margin:12px 0 20px;}
.quick-actions span {color:var(--forest);font-size:13px;}
.device-control {display:flex;align-items:center;flex-wrap:wrap;gap:18px;padding:16px 20px;margin-bottom:20px;}
.device-control label {display:flex;gap:12px;align-items:center;margin:0;color:var(--ink-2);}
.device-control select {min-width:220px;max-width:320px;}
.control-actions {display:flex;align-items:center;gap:16px;margin-left:auto;}
.connection-guide {display:flex;gap:16px;align-items:center;color:var(--ink-2);font-size:13px;margin:0 0 20px;}
.connection-guide b {font-weight:500;}
.connection-guide span {color:var(--muted);}
.workbench {grid-template-columns:minmax(0,1.8fr) minmax(280px,1fr);}
.workbench .image-stage {aspect-ratio:1.5;max-height:460px;min-height:300px;background:#212631;}
.workbench .image-empty {color:#b6bfcd;}
.workbench .image-empty small {color:#8b98ad;}
.capture-bar {display:flex;gap:16px;align-items:flex-end;padding:16px 20px;}
.capture-task {flex:1;min-width:0;margin:0;font-size:12px;}
.capture-task select {width:100%;}
button.capture {width:auto;min-width:160px;padding:10px 20px;}
.verdict {border:1px solid var(--line);border-radius:8px;padding:24px;}
.verdict .word {font-size:26px;line-height:1.4;font-weight:600;color:var(--ink);}
.verdict .say {margin-bottom:0;font-size:13px;line-height:1.8;}
.advanced-metrics {margin:0 0 20px;}
.advanced-metrics summary {font-size:13px;}
@media(min-width:1700px){.workspace-tabs{margin:-32px -40px 28px;padding:0 40px;}}
@media(max-width:1200px){.workspace-tabs{margin:-24px -24px 24px;padding:0 24px;}.overview-metrics{gap:12px;}.metric-card{padding:20px;}.quick-actions>a{padding:0 20px;}}
@media(max-width:1000px){.overview-metrics{grid-template-columns:repeat(2,minmax(0,1fr));}.workbench{grid-template-columns:1fr;}.quick-actions{grid-template-columns:1fr;padding:0 20px;}.quick-actions>a{border:0;border-bottom:1px solid var(--line);padding:24px 0;}.quick-actions p{margin-bottom:14px;}.device-control select{min-width:160px;}}
@media(max-width:640px){.nav-group-label{display:none;}.sidebar nav{display:flex;padding-bottom:12px;}.workspace-tabs{margin:-20px -16px 20px;padding:0 16px;gap:22px;}.workspace-tabs a{padding:14px 0 12px;}.metric-card{padding:16px;gap:10px;}.metric-card strong{font-size:28px;}.device-control{padding:16px;gap:12px;}.device-control label{width:100%;}.device-control select{width:100%;min-width:0;}.control-actions{margin-left:auto;gap:8px;}.connection-guide{display:block;}.connection-guide span{display:block;margin-top:5px;}.capture-bar{flex-wrap:wrap;}.capture-task{flex-basis:100%;}button.capture{width:100%;}.auth-wrap .login-form{padding:28px 24px;}.workbench .image-stage{aspect-ratio:1;min-height:260px;}.topbar-actions>span{display:none;}}
'''
p.write_text(s,encoding='utf-8')
p=root/'apps/web/src/views/Devices.vue';s=p.read_text(encoding='utf-8')
start=s.index('  <!-- 从工作台搬来的运行遥测');end=s.index('  <AsyncState',start)
chunk=s[start:end];s=s[:start]+'''  <details v-if="tab === 'registry'" class="advanced-metrics"><summary>查看实时运行指标</summary>'''+chunk+'''</details>
'''+s[end:]
s=s.replace('<h1>设备诊断</h1>','<h1>设备与工位</h1>')
s=s.replace('devices.current?.telemetry?.errorCode ?? 0','devices.current?.telemetry?.errorCode ?? "未上报"')
p.write_text(s,encoding='utf-8')
p=root/'apps/web/src/views/Operations.vue';s=p.read_text(encoding='utf-8')
s=s.replace('<section class="panel section-space">\n        <div class="panel-head">\n          <h3>检出目标</h3>','<section v-if="preview && inspecting && detections?.length" class="panel section-space">\n        <div class="panel-head">\n          <h3>检出目标</h3>')
p.write_text(s,encoding='utf-8')
