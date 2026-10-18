from pathlib import Path
import json
def put(p,s):Path(p).write_bytes(s.encode('utf-8'))
p=Path('apps/mobile/src/pages/capture/index.vue');s=p.read_text();script=s[:s.index('</script>')];script=script.replace('const pending = computed(','''const sheetExpanded = ref(false);
const posture = computed(() => {
  if (!imuAvailable.value || !motion.value) return { label: "传感器不可用", tone: "unknown" };
  if (Math.abs(motion.value.roll ?? 0) > 15 || Math.abs(motion.value.pitch ?? 0) > 30) return { label: "倾斜", tone: "tilt" };
  return motion.value.captureStability === "STABLE" ? { label: "稳定", tone: "stable" } : { label: "移动中", tone: "motion" };
});
const pending = computed(''')
template='''</script>
<template>
  <view class="capture-page">
    <view class="capture-header"><view><text class="field-kicker">视觉采样仪</text><text class="field-title">现场采样<span>.</span></text></view><view class="field-link" @click="uni.navigateTo({ url: '/pages/sync/index' })"><text class="link-state" :class="{ online: session.online && session.serverAvailable }">{{ session.online && session.serverAvailable ? '已连接' : '离线模式' }}</text><text class="mono">{{ pending }} 待同步</text></view></view>
    <view class="modes"><text v-for="m in [{ key: 'BOARD', label: '板端' }, { key: 'MOBILE', label: '手机' }, { key: 'SYNC', label: '同步' }]" :key="m.key" :class="{ active: mode === m.key }" @click="mode = m.key as typeof mode">{{ m.label }}采样</text></view>
    <view class="field-camera-label"><text>{{ mode === 'BOARD' ? '设备图像源' : '相机取景' }}</text><text class="mono">{{ mode === 'BOARD' ? device?.type ?? '未选择' : '原图采样' }}</text></view>
    <view class="camera-window">
      <CameraSurface v-if="mode !== 'BOARD' && visible" ref="camera" />
      <view v-else class="board-guide"><text class="board-guide-number">01</text><text>板端采样</text><text>{{ displayName(device?.name ?? '请选择设备') }}</text><text v-if="device?.source === 'SIMULATION'" class="tag">模拟设备</text><text class="board-source-state">{{ chinese(device?.connectionState) }}</text></view>
      <view v-if="mode !== 'BOARD'" class="guide-frame"><text>采样区域</text></view>
    </view>
    <view v-if="mode !== 'BOARD'" class="posture-strip" :class="posture.tone"><view class="posture-label"><view class="posture-dot" /><text>{{ posture.label }}</text></view><view v-if="motion && imuAvailable" class="posture-values"><text class="mono">俯仰 {{ motion.pitch?.toFixed(1) }}°</text><text class="mono">横滚 {{ motion.roll?.toFixed(1) }}°</text></view><text v-else class="posture-values">姿态辅助未启用</text></view>
    <view class="capture-sheet">
      <button class="sheet-toggle" :aria-expanded="sheetExpanded" @click="sheetExpanded = !sheetExpanded"><view class="sheet-grip" /><view><text>任务与设备</text><text>{{ session.taskId ? '已关联任务' : '独立采样' }} · {{ sheetExpanded ? '收起' : '展开' }}</text></view></button>
      <view v-if="sheetExpanded" class="sheet-settings"><picker v-if="mode !== 'MOBILE'" :range="deviceList" range-key="name" :value="deviceIndex" @change="deviceIndex = Number($event.detail.value)"><view class="device-picker"><text>采样设备</text><text>{{ displayName(device?.name ?? '选择设备') }} · {{ chinese(device?.connectionState) }}</text></view></picker><button class="task-picker" @click="uni.switchTab({ url: '/pages/tasks/index' })">{{ session.taskId ? '更换关联任务' : '选择采样任务' }} →</button><text v-if="mode === 'SYNC'" class="capture-note">手机与设备分别采样，关联到同一采样组</text></view>
      <text v-if="mode !== 'MOBILE' && !sheetExpanded" class="selected-device" @click="sheetExpanded = true">{{ displayName(device?.name ?? '点击选择设备') }} / {{ chinese(device?.connectionState) }}</text>
      <text v-if="error" class="capture-error" role="alert">{{ error }}</text><text v-if="lastResult" class="capture-success">{{ lastResult }}</text>
      <view class="shutter-row"><button class="shutter-side" @click="uni.navigateTo({ url: '/pages/sync/index' })"><text class="mono">{{ pending }}</text><text>待同步</text></button><button class="shutter" :disabled="busy" :loading="busy" @click="capture" aria-label="采样快门"><view /></button><button class="shutter-side" @click="uni.switchTab({ url: '/pages/records/index' })"><text class="record-symbol">▤</text><text>检测记录</text></button></view>
      <text class="capture-note">{{ busy ? '正在保存采样…' : mode === 'BOARD' ? '采样设备最近的完整帧' : imuAvailable && motion && posture.tone !== 'stable' ? '调整姿态可改善采样，仍可直接拍摄' : '按下快门，保存原始图像' }}</text>
    </view>
  </view>
</template>
<style scoped>
.capture-page{min-height:100vh;background:#1d211b;color:#eef1e6;padding:env(safe-area-inset-top) 0 16px;}
.capture-header{padding:22px 22px 17px;display:flex;justify-content:space-between;align-items:center;}.field-kicker{display:block;color:#a4b096;font:10px monospace;letter-spacing:2px;margin-bottom:7px;}.field-title{font-size:27px;line-height:1.2;font-weight:550;letter-spacing:-1px;}.field-title span{color:#ee743d;}.field-link{display:flex;flex-direction:column;gap:8px;text-align:right;font-size:10px;min-height:44px;justify-content:center;color:#a4b096;}.link-state{color:#e4b676;}.link-state.online{color:#a0cb87;}.modes{margin:0 20px 15px;display:flex;border:1px solid #525e45;background:#292f23;}.modes text{flex:1;text-align:center;padding:13px 0;font-size:12px;color:#b5c0a6;min-height:44px;border-right:1px solid #525e45;}.modes text:last-child{border-right:0;}.modes text.active{background:#ebece1;color:#272f20;font-weight:600;}.field-camera-label{padding:10px 20px;background:#30392a;display:flex;justify-content:space-between;font-size:9px;color:#b9c6a9;letter-spacing:1px;border-top:1px solid #4c5940;}.camera-window{height:44vh;min-height:275px;max-height:560px;position:relative;overflow:hidden;background:#141910;}.guide-frame{position:absolute;left:11%;top:17%;width:78%;height:66%;border:1px solid #e5ebd65c;pointer-events:none;}.guide-frame text{position:absolute;left:9px;top:9px;font:9px monospace;letter-spacing:1px;color:#dfe7d2;background:#20271bb0;padding:3px 5px;}.board-guide{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:13px;color:#d2dcc4;font-size:14px;}.board-guide .board-guide-number{font:44px monospace;color:#6d7b5c;margin-bottom:7px;}.board-source-state{font-size:10px;color:#a4b38e;}.posture-strip{display:flex;align-items:center;justify-content:space-between;padding:13px 20px;background:#2c3524;border-top:1px solid #515f41;gap:12px;}.posture-label{display:flex;align-items:center;gap:7px;font-size:11px;font-weight:550;}.posture-dot{width:6px;height:6px;background:#a7b596;}.stable .posture-dot{background:#a4d588;}.stable .posture-label{color:#c1e0ab;}.motion .posture-dot,.tilt .posture-dot{background:#efb761;}.motion .posture-label,.tilt .posture-label{color:#efc48a;}.posture-values{display:flex;gap:14px;font-size:9px;color:#b6c3a5;}.capture-sheet{background:#f1f0e8;color:#2c3326;border-radius:16px 16px 0 0;padding:0 20px 18px;position:relative;}.sheet-toggle{border:0;background:transparent;color:#39452d;padding:10px 0 12px;width:100%;min-height:48px;border-radius:0;}.sheet-grip{height:3px;width:30px;background:#b3b9a8;margin:0 auto 13px;border-radius:2px;}.sheet-toggle>view:last-child{display:flex;justify-content:space-between;gap:10px;align-items:center;font-size:11px;}.sheet-toggle>view:last-child text:last-child{font-size:9px;color:#707c63;}.sheet-settings{border-top:1px solid #c9cebf;padding-top:12px;}.device-picker{border:1px solid #b7bfaa;padding:12px;background:#faf9f3;display:flex;flex-direction:column;gap:6px;min-height:55px;}.device-picker text:first-child{font-size:9px;color:#728063;}.device-picker text:last-child{font-size:12px;}.task-picker{border:0;background:transparent;text-align:left;font-size:11px;min-height:44px;padding:12px 0;color:#4d5b3f;}.selected-device{display:block;text-align:center;font:10px monospace;padding:10px 0 2px;min-height:32px;color:#667456;}.shutter-row{display:flex;align-items:center;justify-content:space-around;margin:10px 0 5px;gap:20px;}.shutter-side{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;min-width:70px;min-height:70px;background:transparent;border:0;padding:8px;color:#536146;border-radius:2px;font-size:10px;}.shutter-side .mono{font-size:24px;line-height:1.2;}.record-symbol{font-size:24px;line-height:1.2;color:#536146;}.shutter{width:78px;height:78px;border:2px solid #dc5a2a;border-radius:50%;background:transparent;padding:5px;flex-shrink:0;}.shutter view{width:100%;height:100%;border-radius:50%;background:#df602f;}.shutter:active{background:#f3dbc9;}.capture-note{display:block;color:#69775d;font-size:10px;text-align:center;line-height:1.8;margin-top:8px;}.capture-error,.capture-success{display:block;font-size:11px;line-height:1.7;padding:10px;margin-top:10px;border-left:3px solid;}.capture-error{color:#a93b25;background:#f6e0d5;}.capture-success{color:#3b6c30;background:#e4ecd9;}
@media(min-width:700px){.capture-page{max-width:680px;margin:auto;}.camera-window{height:50vh;}.capture-sheet{padding-left:35px;padding-right:35px;}}
</style>
'''
put(p,script+template)
p=Path('apps/mobile/src/App.vue');s=p.read_text();s=s.replace('</style>','''/* Field instrument surfaces */
page{background:#e9e9df;color:#283023;font-family:"Segoe UI","Microsoft YaHei",sans-serif;}
button{border-radius:2px;background:#dedfd2;color:#3d4c31;min-height:44px;font-size:13px;}
.primary,.large-action{background:#dd5b2a;color:#fff8eb;border-radius:2px;}
.primary:active,.large-action:active{background:#c64b1e;}
.page{padding:25px 20px 32px;}
.title{font-size:27px;font-weight:550;letter-spacing:-1px;}
.card{border:0;border-top:1px solid #b7bda9;border-bottom:1px solid #b7bda9;border-radius:0;background:#f7f6ee;padding:18px;margin-bottom:12px;}
input,textarea,.picker{border-radius:2px;border-color:#b8bfaa;background:#f8f7ef;}
input{height:47px;}
.tag{border-radius:2px;border-color:#c2ab76;background:#f5e7c4;color:#7a5a1c;font-size:10px;}
.muted,.subtitle,.note,.list-caption{color:#6b775e;}
.section-head{border-top:2px solid #404c34;padding-top:14px;margin-top:25px;}
.section-head text:first-child{font-size:13px;}
.large-action{padding:25px 20px;min-height:130px;}
.large-action .title{font-size:29px;}
.large-action .note{color:#ffe8d1;font-size:11px;}
.progress{background:#d0d7c0;height:3px;border-radius:0;}
.progress>view{background:#657d43;}
.list-item{border-bottom-color:#cbd1be;}
.review-options>text{border-radius:2px;min-height:44px;}
.review-options>text.selected{background:#414f33;}
.offline-banner{background:#f0dfb7;color:#806022;font-size:11px;}
.image{border-radius:0;}
.error{border-radius:0;border-color:#d5a28e;}
</style>''');put(p,s)
p=Path('apps/mobile/src/components/CameraSurface.vue');s=p.read_text().replace('#242b38','#1b2117').replace('#3c475c','#424e35').replace('#c6d1e2','#bdc9ad');put(p,s)
p=Path('apps/mobile/src/pages/home/index.vue');s=p.read_text();s=s.replace('<text class="title">{{','<text class="eyebrow">现场任务</text><text class="title">{{',1);put(p,s)
p=Path('apps/mobile/src/pages.json');cfg=json.loads(p.read_text());capture=next(x for x in cfg['pages'] if x['path']=='pages/capture/index');cfg['pages'].remove(capture);cfg['pages'].insert(0,capture);cfg['globalStyle']['navigationBarBackgroundColor']='#f1f0e8';cfg['globalStyle']['backgroundColor']='#e9e9df';cfg['tabBar'].update(color='#738066',selectedColor='#c64b1e',backgroundColor='#f1f0e8');put(p,json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
p=Path('apps/mobile/src/pages/login/index.vue');s=p.read_text().replace('uni.switchTab({ url: "/pages/home/index" });','uni.switchTab({ url: "/pages/capture/index" });');put(p,s)
