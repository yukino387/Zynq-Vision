from pathlib import Path
root = Path(__file__).resolve().parents[2]
def write(path, text):
    (root/path).write_text(text, encoding='utf-8')
write('apps/web/src/App.vue', '''<script setup lang="ts">
import { onMounted, watch, ref, computed } from 'vue';
import { chinese, displayName } from '@vision/shared';
import { useRoute } from 'vue-router';
import { useAuthStore } from './stores/auth';
import { useDeviceStore } from './stores/devices';
import { useNotificationStore } from './stores/notifications';
import { useTaskStore } from './stores/tasks';
import { errorText } from './api';
const auth = useAuthStore(), devices = useDeviceStore(), notices = useNotificationStore(), tasks = useTaskStore(), route = useRoute();
const username = ref('engineer'), password = ref(''), loginError = ref(''), busy = ref(false);
const nav = [
  { path: '/', label: '检测工作台' }, { path: '/inspections', label: '检测记录' },
  { path: '/data', label: '数据管理' }, { path: '/models', label: '模型管理' },
  { path: '/devices', label: '设备管理' }, { path: '/system', label: '系统管理' },
];
const currentPage = computed(() => nav.find(i => i.path === '/' ? route.path === '/' : route.path.startsWith(i.path))?.label ?? '检测工作台');
onMounted(() => auth.restore());
watch(() => auth.user, async user => {
  if (user) {
    try { await devices.start(); await tasks.load(); } catch (e) { notices.error(e); }
  } else devices.stop();
});
async function login() {
  busy.value = true; loginError.value = '';
  try { await auth.login(username.value, password.value); password.value = ''; }
  catch (e) { loginError.value = errorText(e); }
  finally { busy.value = false; }
}
</script>
<template>
  <div v-if="!auth.ready" class="empty">正在连接平台…</div>
  <div v-else-if="!auth.user" class="login-screen">
    <form class="login-form" @submit.prevent="login">
      <h1>视觉物联网平台</h1><p class="muted">账号登录</p>
      <label>账号<input v-model="username" required autocomplete="username" placeholder="请输入账号" /></label>
      <label>密码<input v-model="password" required type="password" autocomplete="current-password" placeholder="请输入密码" /></label>
      <p v-if="loginError" class="error-box">{{ loginError }}</p>
      <button class="primary" :disabled="busy">{{ busy ? '登录中…' : '登录' }}</button>
    </form>
  </div>
  <div v-else class="shell">
    <aside class="sidebar">
      <RouterLink to="/" class="brand">视觉物联网平台</RouterLink>
      <nav aria-label="主导航">
        <RouterLink v-for="item in nav.filter(i => auth.engineer || !['/models', '/system'].includes(i.path))" :key="item.path" :to="item.path" :class="{ selected: item.path === '/' ? $route.path === '/' : $route.path.startsWith(item.path) }">{{ item.label }}</RouterLink>
      </nav>
      <div class="session"><div>{{ displayName(auth.user.name) }}<small>{{ chinese(auth.user.role) }}</small></div><button @click="auth.logout" aria-label="退出登录">退出</button></div>
    </aside>
    <div class="main-shell">
      <header class="topbar"><span>{{ currentPage }}</span><div class="topbar-actions"><span><span class="connection-dot" :class="{ live: devices.connected }"></span>{{ devices.connected ? '实时连接正常' : '实时连接重连中' }}</span><RouterLink v-if="auth.engineer" to="/system/health">系统状态</RouterLink></div></header>
      <main><RouterView /></main>
    </div>
  </div>
  <div class="toasts" aria-live="polite"><button v-for="m in notices.messages" :key="m.id" :class="{ error: m.error }" @click="notices.dismiss(m.id)">{{ m.text }} <span>关闭</span></button></div>
</template>
''')

# Presentation text only: keep API values, filters and protocol enums unchanged.
replacements = {
 'NOT REPORTED':'未上报', 'NOT AVAILABLE':'不可用',
 'SIMULATED INFERENCE':'模拟推理', 'SIMULATED DEVICE':'模拟设备',
 'SIMULATION BOUNDARY':'模拟训练', 'SIMULATED TRAINING':'模拟训练', 'SIMULATED BENCHMARK':'模拟评估',
 'MODEL UPDATE UNAVAILABLE':'不支持模型更新', 'HARD SAMPLE / 困难样本':'困难样本', 'HARD SAMPLE':'困难样本',
 '01 / VISION OPERATIONS':'检测工作台', '01 / INSPECTION ARCHIVE':'检测记录', '02 / DATA WORKSPACE':'数据管理', '03 / MODEL LIFECYCLE':'模型管理', '04 / EDGE DEVICES':'设备管理', '05 / SYSTEM':'系统管理',
 'FIELD / 现场工作空间':'现场工作台', 'FIELD / OPERATOR WORKSPACE':'视觉采样', 'FIELD / CAPTURE':'现场采样', 'INSPECTION / HISTORY':'检测记录', 'SAMPLE EVIDENCE /':'样本来源：', 'LOCAL STORAGE / SYNC':'同步管理', 'TASKS / 采样任务':'采样任务', 'PAIRING / LOCAL NETWORK':'连接管理',
 'INFERENCE / 推理耗时':'推理耗时', 'DEVICE / 网络':'设备连接', 'THROUGHPUT / 帧率':'检测帧率', 'ACTUAL MODEL / 实际模型':'实际模型',
 'Live inspection <span class="muted">/ 视觉现场</span>':'实时画面', 'Data pipeline <span class="muted">/ 数据链路</span>':'处理耗时',
 'DEVICE REPORTED · μs → ms':'单位：毫秒', 'INSPECTION / 检测':'检测编号', '检测证据 / Inspection':'检测详情',
 '/ PERSISTED EVIDENCE':'', ' OBJECTS':' 个目标', ' RECORDS':' 条记录', ' DETECTIONS':' 个检测目标',
 'FRAME ID':'帧编号', 'MODEL VERSION':'模型版本', 'PLAN VERSION':'方案版本', 'SERVER TIME':'记录时间',
 'MODEL UPDATE':'模型更新', 'ERROR CODE':'错误码', 'NETWORK':'网络状态', 'RUNTIME':'运行状态', 'FIRMWARE':'固件版本',
 '人工复核 / Review':'人工复核', 'Desired / 目标':'目标版本', 'Reported / 实际':'实际版本', 'Capabilities':'设备能力',
 'SIMULATED fault':'模拟故障', 'Target model':'目标模型版本', 'Target plan':'目标方案版本', '保存 Desired State':'保存目标版本',
 '连接 / 接管 Preview':'连接设备', '断开本地 Adapter':'断开连接', '>Debug<':'>调试<',
 '>Command<':'>控制命令<', '>Weights<':'>权重文件<', 'Manifest JSON':'模型清单（JSON）',
 '选择 DRAFT 数据集':'选择草稿数据集', '导出 images / labels / manifest':'导出数据集',
 'App 配对':'移动端配对', '>Audit<':'>操作审计<', '实体 / Request ID':'对象编号',
 'ONE-TIME / 5 MIN':'有效期 5 分钟', 'STATION / DEVICE ID':'工位与设备',
 'Server / 一次性配对':'服务器配对', 'Station / 工位':'工位配对', 'Device / 设备':'设备配对',
 '手机可访问的 Server URL':'服务器地址', 'http://HOST-IP:3000':'http://服务器地址:3000',
 'RECONSTRUCTED INPUT':'模型输入预览', 'CAMERA VIEW':'采样图像', 'WAITING FOR FRAME':'等待图像', '>Fit<':'>适应窗口<', '>Preview<':'>预览图<',
 'INSPECTOR':'详情', 'ORIGINAL PRESERVED':'', 'TARGET AREA':'采样区域', 'IMU NOT AVAILABLE':'姿态传感器不可用', 'BOARD CAPTURE':'设备采样',
 'TILT LEFT':'请向左调整', 'TILT RIGHT':'请向右调整', 'Pitch ':'俯仰 ', 'Roll':'横滚',
 'SAMPLES\n    PENDING':'个样本待同步', ' PENDING SERVER ACK':' 等待服务器确认', 'PENDING SERVER ACK':'等待服务器确认', 'ATTEMPTS':'重试次数', 'CAPTURE SET':'采样组',
 'SYSTEM STATUS':'系统状态', 'LOCAL MODE':'离线模式', 'SYNC QUEUE':'同步队列', 'CONNECTED':'已连接',
 ' PENDING':' 待同步', '>Frame<':'>帧编号<', '>MODEL<':'>模型<', 'MODEL {{':'模型 {{', 'DETECTION {{':'目标 {{',
 'SUPPORTED':'支持', 'UNAVAILABLE':'不可用', 'NOT SUPPORTED':'不支持',
}
import re
files = list((root/'apps/web/src').rglob('*.vue')) + list((root/'apps/mobile/src').rglob('*.vue'))
for f in files:
    if f.name == 'App.vue' and 'web' in f.parts: continue
    s = f.read_text(encoding='utf-8')
    # Fixed English labels, not identifiers or enum literals in scripts.
    script, sep, template = s.partition('<template>')
    for a,b in replacements.items(): template = template.replace(a,b)
    template = template.replace(' ↗','').replace('↗','').replace('＋ ','').replace('↑ ','').replace(' ↓','').replace(' →','').replace('← 返回','返回').replace('刷新 ↻','刷新')
    # Explicit option values prevent Chinese labels changing submitted protocol values.
    template = re.sub(r'<option>([A-Z_]+)</option>', lambda m: f'<option value="{m[1]}">{{{{ chinese(\'{m[1]}\') }}}}</option>',template)
    template = re.sub(r'(<option\s[^>]*v-for="[\s\S]*?:key="([sf])")\s*>\s*{{ \2 }}', r'\1 :value="\2">{{ chinese(\2) }}', template)
    for expr in ['t.status','d.connectionState','d.runtimeState','i.result','inspection.result','sample.status','item.status','sample.source','i.source','r.source','d.type','r.verdict','a.kind','m.status']:
        template=template.replace('{{ '+expr+' }}','{{ chinese('+expr+') }}')
    for expr in ['d.name','r.name','t.name','m.name','s.name','sample.name','i.sample.name','device?.name']:
        template=template.replace('{{ '+expr+' }}','{{ displayName('+expr+') }}')
    template=re.sub(r'([ird]|sample)\.source === "SIMULATION"\s*\? "SIMULATED"\s*: ([ird]|sample)\.source',r'chinese(\1.source)',template)
    template=template.replace('d.source === "SIMULATION" ? "SIMULATED" : d.type','chinese(d.type)')
    template=template.replace('inspection.source === "SIMULATION"\n          ? "模拟推理"\n          : inspection.source','chinese(inspection.source)')
    template=template.replace('{{ inspection.reason }}','{{ reasonLabel(inspection.reason) }}')
    template=template.replace('{{ box.label }}','{{ displayName(box.label) }}').replace('{{ b.label }}','{{ displayName(b.label) }}')
    template=template.replace('<span>⌗</span>','')
    template=re.sub(r'<text\s+style="[^"]*"\s*>⌗</text\s*>','',template)
    # Remove page marketing eyebrows and requirement-style introductions.
    if f.parent.name=='views':
        template=re.sub(r'\s*<(?:small|span class="eyebrow")>[^<]*(?:工作台|管理|记录)</(?:small|span)>','',template,count=1)
        template=re.sub(r'\s*<p>[^<]*</p>','',template,count=1)
    if any(x in template for x in ['chinese(', 'displayName(', 'reasonLabel(']):
        used=[x for x in ['chinese','displayName','reasonLabel'] if x+'(' in template]
        # Each file gets precisely the display helpers it uses.
        script=script.replace('<script setup lang="ts">','<script setup lang="ts">\nimport { '+', '.join(used)+' } from "@vision/shared";',1)
    f.write_text(script+sep+template,encoding='utf-8')

def edit(path, pairs):
    f=root/path;s=f.read_text(encoding='utf-8')
    for a,b in pairs:
        if a not in s: print('MISSING', path, a[:65])
        s=s.replace(a,b)
    f.write_text(s,encoding='utf-8')

edit('apps/web/src/components/Status.vue', [('defineProps', 'import { chinese } from "@vision/shared";\ndefineProps'), ('{{ value ?? "未上报" }}','{{ chinese(value) }}')])
edit('apps/web/src/views/Operations.vue', [
 ('device?.runtimeState ?? "UNKNOWN"','chinese(device?.runtimeState)'),('device?.type ?? "NO DEVICE"','chinese(device?.type)'),
 ('device?.syncState ?? "UNKNOWN"','chinese(device?.syncState)'),(' · desired / reported',''),
 ('<small>SYNC</small>','<small>同步状态</small>'),('<dt>SYNC</dt>','<dt>版本同步</dt>'),
 ('FRAME {{','帧编号 {{'),('"CAPTURE"','"采集"'),('"CONVERSION"','"预处理"'),('"INFERENCE"','"推理"'),('"TRANSFER"','"传输"'),('"FRAME CYCLE"','"帧周期"'),
 ('<p class="note" style="margin-bottom: 0">\n            实时预览保留在内存中。点击采样后，才会创建可追溯的样本与检测记录。\n          </p>',''),
 ('设备报告的最近帧','最近一帧'),('由设备帧周期计算','实时帧率'),('未发现候选缺陷。尚无设备验收方案，结果待复核。','未发现候选缺陷，待复核。'),
])
edit('apps/web/src/views/Models.vue', [
 ('["training", "Training"]','["training", "训练任务"]'),('["benchmarks", "Benchmark"]','["benchmarks", "模型评估"]'),('["deployments", "Deployment"]','["deployments", "部署管理"]'),
 ('"运行 Benchmark"','"创建评估"'),
 ('第一版 Training 使用模拟引擎，产生的制品仅供 Simulator 使用。Benchmark\n        记录兼容性和模拟设备当前遥测；accuracy / mAP 未测量。真实 Zynq\n        尚不支持通过当前 UDP 协议更新模型。','模拟训练生成的模型仅可用于模拟设备。'),
 ('服务器会验证能力、输入与输出形状、量化参数、类别、预处理、接口版本和\n        SHA256。','请选择兼容的模型、数据集和设备。'),
])
edit('apps/web/src/views/Devices.vue', [
 ('目标状态不会直接更改 Reported State。设备没有报告的版本保持 UNKNOWN。',''),
 ('暂无事件。完整帧预览不写入事件历史。','暂无事件'),
 ('连接会将板端 UDP 接收目标切换到本服务。当前固件仅保留一个接收端，CNN\n      Studio 不应同时接管。','连接设备会接管图像接收，请先断开其他上位机。'),
 ('{{ key }}','{{ fieldLabel(key) }}'),('"NOT 支持"','"不支持"'),
 ('import { chinese, displayName }','import { chinese, displayName, fieldLabel }'),
 ('<option v-if="selected.type === \'ZYNQ\'">SET_BRIGHTNESS</option>','<option v-if="selected.type === \'ZYNQ\'" value="SET_BRIGHTNESS">调整亮度</option>'),
 ('<option v-if="selected.type === \'SIMULATOR\'">FAULT</option>','<option v-if="selected.type === \'SIMULATOR\'" value="FAULT">模拟故障</option>'),
 ('"操作已执行，状态来自设备回报"','kind === "desired" ? "目标版本已保存" : "操作已完成"'),
])
edit('apps/web/src/views/Data.vue', [
 ('<p class="note">FROZEN 是不可修改的快照。创建新版本以继续迭代。</p>',''),
 ('<pre>{{\n        JSON.stringify(\n          { metadata: sample.metadata, quality: sample.quality },\n          null,\n          2,\n        )\n      }}</pre>','<details class="section-space"><summary>样本原始信息</summary><pre>{{ JSON.stringify({ metadata: sample.metadata, quality: sample.quality }, null, 2) }}</pre></details>'),
])
edit('apps/web/src/views/System.vue', [
 ('系统与可追溯性','系统管理'), ('{{ key.toUpperCase() }}','{{ fieldLabel(key) }}'), ('{{ k }}','{{ fieldLabel(k) }}'),
 ('typeof v === "object" ? JSON.stringify(v) : v','typeof v === "object" ? JSON.stringify(v) : chinese(v)'),
 ('<span class="tag">LOCAL</span>',''),(' PENDING</span>',' 个待处理任务</span>'),
 ('局域网地址来自操作系统网卡。手机与服务器需位于可互通的网络。',''),
 ('Server\n            码包含一次性令牌；工位/设备码仅包含标识及关联信息。所有访问仍需登录并通过服务端权限验证。','使用移动端扫描二维码完成配对。'),
 ('import { chinese, displayName }','import { chinese, displayName, fieldLabel }'),
 ('{{ r.role ?? r.entityId','{{ r.role ? chinese(r.role) : r.entityId'),
])
edit('apps/mobile/src/pages/login/index.vue', [
 ('现场的每一次采样，<br />都有迹可循。','视觉采样'),
 ('连接局域网工作空间，继续你的采样任务。','账号登录'),
 ('<text class="eyebrow" style="margin-top: 40px"\n      >视觉采样</text\n    >',''),
 ('<text class="note"\n      >首次账户密码由本机 .env 提供。配对不会授予管理员权限。</text\n    >',''),
 ('placeholder="operator"','placeholder="请输入账号"'),
])
edit('apps/mobile/src/pages/home/index.vue', [
 ('选好任务，让现场数据进入下一次迭代。',''),
 ('<text style="font-size: 30px"></text>','<text>进入采样</text>'),
 ('在任务页选择后开始采样','未选择'),
 ('session.user?.name ?? "欢迎回来"','displayName(session.user?.name ?? "欢迎回来")'),
])
edit('apps/mobile/src/pages/records/index.vue', [
 ('每一次采样，都有记录。','检测记录'),
 ('板端检测与人工复核。手机采样作为训练证据，不会假装已在 Zynq\n      上推理。',''),
])
edit('apps/mobile/src/pages/sample/index.vue', [
 ('sample.quality?.status ?? "不可用"','chinese(sample.quality?.status ?? "不可用")'),
 ('。手机样本不会自动产生板端推理结果。',''),
])
edit('apps/mobile/src/pages/tasks/index.vue', [
 ('把任务带到现场。','采样任务'),('选择当前采样任务。样本会自动关联，操作员无需管理数据集。',''),
])
edit('apps/mobile/src/pages/sync/index.vue', [
 ('原图已保存在本机。上传失败可以重试，同一幂等键不会重复创建样本。','未同步的样本将在联网后继续上传。'),
 ('● NETWORK AVAILABLE','● 网络可用'),('MOBILE /','手机样本 /'),
 ('本地队列为空。采样后，原图会先保存到这里。','暂无本地样本'),
])
edit('apps/mobile/src/pages/pair/index.vue', [
 ('连接你的工位。','服务器与工位配对'),
 ('在 Web 端「系统 → 移动端配对」生成一次性二维码。','扫描控制台生成的配对二维码。'),
 ('令牌 5 分钟过期，只能使用一次。二维码不包含管理员密码或\n      JWT。连接手机相机时，浏览器可能需要\n      HTTPS；不可用时仍支持系统相机选图。','服务器配对码 5 分钟内有效。'),
 ('当前环境未完成扫码，可粘贴 Web 端的手动配对内容。','扫码未完成，请重试或粘贴配对内容。'),
])
edit('apps/mobile/src/pages/capture/index.vue', [
 ('同步为尽力配对，保留独立采集时间；手机样本离线时仍可保存。','手机与设备分别采样'),
 ('imuAvailable ? motion?.captureStability : "姿态传感器不可用"','imuAvailable ? chinese(motion?.captureStability) : "姿态传感器不可用"'),
 ('device?.connectionState ?? "UNKNOWN"','chinese(device?.connectionState)'),
 ('"SIMULATED "','"模拟设备 "'),('CaptureSet ${captureSet}：','采样组 ${captureSet}：'),
 ('{{ device?.name ?? "选择设备" }}','{{ displayName(device?.name ?? "选择设备") }}'),
 ('<text></text><text>记录</text>','<text>记录</text>'),
])

# Shared visual tokens: familiar neutral surfaces and one restrained accent.
for p in [root/'packages/design-tokens/tokens.css', root/'apps/mobile/src/App.vue']:
    s=p.read_text(encoding='utf-8')
    for a,b in {'#f4f3ee':'#f5f7fa','#fafaf6':'#ffffff','#242a27':'#1d2129','#727a73':'#86909c','#76816f':'#86909c','#d7dcd3':'#e5e6eb','#244e3c':'#165dff','#256647':'#00875a','#8d621d':'#b57600','#b54732':'#d03050','#3d677d':'#165dff','#e9ede3':'#eef3ff','#e0e5d8':'#eef0f3','#dde4d6':'#e5e6eb','#d1ddc9':'#e0e9ff'}.items():s=s.replace(a,b)
    p.write_text(s,encoding='utf-8')

for p in [root/'apps/web/index.html',root/'apps/mobile/index.html',root/'apps/mobile/src/pages.json',root/'apps/mobile/src/manifest.json']:
    s=p.read_text(encoding='utf-8')
    s=s.replace('FIELD / VISION PLATFORM','视觉物联网平台').replace('FIELD / 现场采样','视觉采样').replace('FIELD Vision','视觉采样').replace('FIELD /','视觉采样 /')
    p.write_text(s,encoding='utf-8')
