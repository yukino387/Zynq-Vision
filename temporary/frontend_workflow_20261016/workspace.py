from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=root/'apps/web/src/views/Overview.vue'
p.write_text('''<script setup lang="ts">
import {computed, onMounted, ref, watch} from 'vue';
import {chinese, displayName} from '@vision/shared';
import {api, errorText} from '../api';
import {useDeviceStore} from '../stores/devices';
import {useAuthStore} from '../stores/auth';
import AsyncState from '../components/AsyncState.vue';
import Status from '../components/Status.vue';
interface Overview {
  window: {from:string;to:string};
  inspections:{total:number;pass:number;fail:number;review:number;error:number};
  samples:{pending:number;reviewed:number};
  devices:{total:number;online:number;offline:number;fault:number};
  pipeline:{pendingReview:number;reviewSamples:number;pendingDeployments:number}|null;
}
const devices=useDeviceStore(),auth=useAuthStore(),data=ref<Overview|null>(null),loading=ref(false),error=ref('');
const pending=computed(()=>data.value?.pipeline?.pendingReview??0);
async function load(){loading.value=true;error.value='';try{data.value=await api('/overview');}catch(e){error.value=errorText(e);}finally{loading.value=false;}}
onMounted(load);
watch(()=>devices.recent[0],e=>{if(e&&/inspection.completed|status.changed|review|job./.test(e.type))void load();});
</script>
<template>
  <div class="page-heading"><div><h1>工作概览</h1><p>{{ auth.user?.name }}，欢迎回来</p></div><RouterLink class="button-link primary" :to="{name:'workbench'}">进入实时检测</RouterLink></div>
  <AsyncState :loading="loading" :error="error" @retry="load"><template v-if="data">
    <div class="overview-metrics">
      <RouterLink :to="{name:'records',params:{tab:'all'}}" class="metric-card"><span>近 24 小时检测</span><strong>{{ data.inspections.total }}</strong><small>查看全部记录</small></RouterLink>
      <RouterLink :to="{name:'records',params:{tab:'queue'}}" class="metric-card"><span>待复核记录</span><strong :class="{danger:pending>0}">{{ pending }}</strong><small>{{ pending ? '需要人工确认' : '暂无待办' }}</small></RouterLink>
      <RouterLink :to="{name:'data',params:{tab:'review'}}" class="metric-card"><span>待审核样本</span><strong>{{ data.samples.pending }}</strong><small>进入样本审核</small></RouterLink>
      <RouterLink :to="{name:'diagnostics'}" class="metric-card"><span>在线设备</span><strong>{{ data.devices.online }}<em> / {{ data.devices.total }}</em></strong><small>{{ data.devices.offline }} 台离线</small></RouterLink>
    </div>
    <section class="panel section-space"><div class="panel-head"><h3>从这里开始</h3></div><div class="quick-actions">
      <RouterLink :to="{name:'workbench'}"><b>实时检测</b><p>连接设备，查看画面并保存样本</p><span>进入工作台</span></RouterLink>
      <RouterLink :to="{name:'records',params:{tab:'queue'}}"><b>复核检测结果</b><p>确认疑似缺陷，补充现场备注</p><span>{{ pending ? `处理 ${pending} 条待办` : '查看检测记录' }}</span></RouterLink>
      <RouterLink :to="{name:'data',params:{tab:'tasks'}}"><b>采集训练数据</b><p>选择采样任务，整理样本与标注</p><span>查看采样任务</span></RouterLink>
    </div></section>
    <section class="panel section-space"><div class="panel-head"><h3>设备概况</h3><RouterLink :to="{name:'diagnostics'}">管理设备</RouterLink></div><div class="table-wrap"><table><thead><tr><th>设备</th><th>类型</th><th>连接状态</th><th>检测状态</th><th>操作</th></tr></thead><tbody><tr v-for="d in devices.devices" :key="d.id"><td><strong>{{ displayName(d.name) }}</strong></td><td><span class="tag" :class="{simulated:d.source==='SIMULATION'}">{{ chinese(d.type) }}</span></td><td><Status :value="d.connectionState" /></td><td>{{ d.connectionState !== 'ONLINE' ? '—' : d.reportedState.inspectionEnabled ? '检测中' : '已暂停' }}</td><td><RouterLink class="table-action" :to="{name:'workbench'}" @click="devices.selected=d.id">{{ d.connectionState==='ONLINE' ? '查看画面' : '连接设备' }}</RouterLink></td></tr></tbody></table></div></section>
  </template></AsyncState>
</template>
''',encoding='utf-8')

p=root/'apps/web/src/views/Operations.vue';s=p.read_text(encoding='utf-8')
s=s.replace('const detections = computed','const inspecting = computed(() => device.value?.reportedState.inspectionEnabled === true);\nconst detections = computed')
s=s.replace('device.value ? devices.previews[device.value.id] : null','device.value?.connectionState === "ONLINE" ? devices.previews[device.value.id] : null')
s=s.replace('  if (!device.value.capabilities.capture) return "该设备不支持采集。";','  if (!device.value.capabilities.capture) return "该设备不支持采集。";\n  if (device.value.runtimeState === "READY") return "检测已暂停，请先开始检测。";\n  if (!preview.value) return "正在等待设备画面…";')
s=s.replace('notices.add("采样已保存，原始数据与检测结果已关联");','notices.add("样本与检测记录已保存");')
s=s.replace('    await devices.snapshot();\n  } catch (e) {','    await devices.snapshot();\n    notices.add("设备已连接");\n  } catch (e) {',1)
pos=s.index('</script>')
s=s[:pos]+'''async function control(start: boolean) {
  if (!device.value) return;
  connecting.value = true;
  try {
    if (start && device.value.type === 'ZYNQ') await post(`/devices/${device.value.id}/commands`, {type:'CAMERA_ONLY',value:0});
    await post(`/devices/${device.value.id}/commands`, {type:start?'START_INSPECTION':'STOP_INSPECTION'});
    await devices.snapshot();
    notices.add(start ? '检测已开始' : '检测已暂停');
  } catch(e) {notices.error(e);} finally {connecting.value=false;}
}
'''+s[pos:]
s=s.replace('<h1>检测工作台</h1>','<h1>实时检测</h1>')
start=s.index('      <p class="mono">');end=s.index('    </div>',start)
s=s[:start]+s[end:]
start=s.index('    <div class="heading-actions">');end=s.index('\n  <div class="workbench">',start)
s=s[:start]+'''  </div>
  <div class="device-control panel">
    <label>检测设备<select v-model="devices.selected" aria-label="当前设备"><option v-for="d in devices.devices" :key="d.id" :value="d.id">{{ displayName(d.name) }}</option></select></label>
    <Status :value="device?.connectionState" />
    <span v-if="device?.source === 'SIMULATION'" class="tag simulated">模拟设备</span>
    <div class="control-actions" v-if="auth.engineer">
      <button v-if="device?.connectionState !== 'ONLINE'" class="primary" :disabled="connecting || !device" @click="connect">{{ connecting ? '连接中…' : '连接设备' }}</button>
      <template v-else><button v-if="!inspecting" class="primary" :disabled="connecting" @click="control(true)">开始检测</button><button v-else :disabled="connecting" @click="control(false)">暂停检测</button><RouterLink :to="{name:'diagnostics'}" class="text-button">设备设置</RouterLink></template>
    </div>
    <span v-else-if="device?.connectionState !== 'ONLINE'" class="muted">请联系工程师连接设备</span>
  </div>
  <p v-if="device?.error" class="error-box">{{ device.error }}</p>
  <div v-if="device?.connectionState !== 'ONLINE'" class="connection-guide"><b>连接设备后开始检测</b><span>选择要使用的设备，然后点击“连接设备”。</span></div>
'''+s[end:]
s=s.replace('        <button\n          class="primary capture"','''        <label class="capture-task">采样任务<select v-model="tasks.selected" aria-label="关联采样任务"><option value="">独立采样</option><option v-for="t in tasks.items" :key="t.id" :value="t.id">{{ displayName(t.name) }}</option></select></label>
        <button
          class="primary capture"''')
s=s.replace(':disabled="busy || !!captureBlocked"',':disabled="busy || connecting || !!captureBlocked" :title="captureBlocked"')
s=s.replace('      <div class="panel-head" style="border-top: 1px solid var(--line)">','      <div class="panel-head" style="border-top: 1px solid var(--line)">\n        <span v-if="captureBlocked" class="muted">{{ captureBlocked }}</span>')
s=s.replace('!preview\n              ? "等待数据"','!preview\n              ? "等待设备画面"\n              : !inspecting ? "检测已暂停"')
s=s.replace('!preview\n              ? "尚未收到完整预览帧。"','!preview\n              ? "设备连接后，画面会显示在左侧。"\n              : !inspecting ? "点击开始检测以继续。"')
start=s.index('      <p class="note">\n        采样会把');end=s.index('      </p>',start)+len('      </p>');s=s[:start]+s[end:]
s=s.replace('<span class="tag">待处理在前</span>','')
p.write_text(s,encoding='utf-8')

p=root/'apps/web/src/stores/devices.ts';s=p.read_text(encoding='utf-8').replace('ref, computed','ref, computed, watch')
s=s.replace('selected = ref("")','selected = ref(localStorage.getItem("vision.web.device") ?? "")')
s=s.replace('if (!selected.value) selected.value = devices.value[0]?.id ?? "";','''if (!devices.value.some(d => d.id === selected.value)) selected.value = devices.value.find(d => d.type === 'ZYNQ')?.id ?? devices.value[0]?.id ?? '';''')
s=s.replace('        history.value = [','        if (device.id === current.value?.id) history.value = [')
pos=s.index('  async function snapshot()');s=s[:pos]+'''  watch(selected, id => {localStorage.setItem('vision.web.device', id); history.value=[];});
'''+s[pos:]
p.write_text(s,encoding='utf-8')
