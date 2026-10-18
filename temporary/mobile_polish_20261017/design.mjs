import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
const root = resolve(import.meta.dirname, '../..');
const src = resolve(root, 'apps/mobile/src');
const read = p => readFileSync(resolve(src,p),'utf8');
const write = (p,s) => writeFileSync(resolve(src,p),s);
// A single palette for both the native and H5 surfaces.
const palette = {
 '#e9e9df':'#f3f6f7','#f1f0ed':'#f3f6f7','#f1f0e8':'#ffffff',
 '#f7f6ee':'#ffffff','#fbfaf8':'#ffffff','#fbfaf3':'#f7fafb','#f8f7ef':'#f7fafb','#faf9f3':'#f7fafb','#fbf8ef':'#eef8f6',
 '#283023':'#17343e','#2c3326':'#17343e','#151715':'#17343e',
 '#6b775e':'#637d87','#707c63':'#637d87','#7c807c':'#637d87','#738066':'#7a9098',
 '#4d5b3f':'#486571','#3d4c31':'#365661','#404c34':'#17343e','#414f33':'#087f82','#1f4d3a':'#087f82',
 '#dd5b2a':'#087f82','#c64b1e':'#076b6e','#b4491f':'#087f82','#ee743d':'#f28b61',
 '#b7bda9':'#dce6e9','#b7bfaa':'#dce6e9','#b8bfaa':'#dce6e9','#c9cebf':'#dce6e9','#c9c6bf':'#dce6e9',
 '#d6d8cc':'#e6edef','#cbd1be':'#e6edef','#cdd0c3':'#e6edef','#d6d3cc':'#e6edef',
 '#dedfd2':'#e8f0f2','#e4e2dd':'#e8f0f2','#d0d7c0':'#e1eded','#657d43':'#18a79b',
 '#10140f':'#102b36','#141810':'#102b36','#161a12':'#102b36','#22281c':'#193b48',
 '#20271b':'#17343e','#1b1e17':'#17343e','#262013':'#3b3326','#0b0e09':'#0b2029',
 '#eef1e6':'#f0f8fa','#eef4e7':'#f0f8fa','#dfe7d5':'#d9e9ed','#cdd6c2':'#c9dfe5',
 '#c3ceb6':'#c9dfe5','#b9c4ae':'#aac6d0','#b5c0a6':'#aac6d0','#aab6a0':'#aac6d0',
 '#93a08a':'#8db0bd','#7d8a74':'#8db0bd','#3d4736':'#315460','#46503e':'#315460',
 '#9bc789':'#71ddc8','#a0cb87':'#71ddc8','#a4d588':'#71ddc8','#4d7a4b':'#087f82',
 '#dcded5':'#e8f0f2','#a4ad98':'#8ca4ad','#8a947f':'#8ca4ad','#d9a388':'#a8d8d3',
};
function files(dir) { return readdirSync(dir,{withFileTypes:true}).flatMap(f=>f.isDirectory()?files(resolve(dir,f.name)):[resolve(dir,f.name)]); }
for(const file of files(src).filter(f=>f.endsWith('.vue'))) {
 let s=readFileSync(file,'utf8');
 s=s.replace(/#[\da-f]{6,8}/gi, color => {
   const six=color.slice(0,7).toLowerCase();
   return palette[six] ? palette[six]+color.slice(7) : color;
 });
 s=s.replace(/font-size: (8|9|10)px/g,'font-size: 11px');
 s=s.replace(/border-radius: 2px/g,'border-radius: 12px');
 writeFileSync(file,s);
}
let app=read('App.vue');
app=app.slice(0,app.indexOf('<style>'))+`<style>
page {
  --ink: #17343e;
  --muted: #637d87;
  --brand: #087f82;
  --line: #dce6e9;
  --surface: #ffffff;
  background: #f3f6f7;
  color: #17343e;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  font-size: 14px;
  line-height: 1.6;
}
view, text, button, input, textarea { box-sizing: border-box; }
button {
  margin: 0;
  padding: 13px 18px;
  min-height: 48px;
  border-radius: 14px;
  background: #e8f0f2;
  color: #365661;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
}
button::after { border: 0; }
button:active:not([disabled]) { opacity: .8; transform: translateY(1px); }
button[disabled] { opacity: .48; }
.primary { background: #087f82; color: white; box-shadow: 0 5px 14px #087f8218; }
.primary:active:not([disabled]) { background: #076b6e; }
.primary[disabled] { box-shadow: none; }
.page { padding: 24px 20px calc(32px + env(safe-area-inset-bottom)); }
.eyebrow { display: block; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; color: #087f82; margin-bottom: 7px; }
.title { display: block; font-size: 27px; font-weight: 700; letter-spacing: -.7px; line-height: 1.35; margin-bottom: 10px; }
.subtitle { display: block; color: #637d87; font-size: 13px; line-height: 1.8; margin: 0 0 24px; }
.muted { color: #637d87; }
.mono { font-family: "SFMono-Regular", Consolas, monospace; font-variant-numeric: tabular-nums; }
.card { padding: 18px; border: 1px solid #e4ecef; background: white; border-radius: 18px; margin-bottom: 14px; box-shadow: 0 4px 18px #17343e04; }
.section-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 26px 0 14px; }
.section-head text:first-child { font-size: 16px; font-weight: 650; }
.section-head .muted { font-size: 13px; padding: 8px 0 8px 12px; }
.row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.row > text { min-width: 0; overflow-wrap: anywhere; }
.stack { display: flex; flex-direction: column; gap: 10px; }
.field { display: block; margin: 18px 0; }
.field > text { display: block; color: #637d87; font-size: 13px; margin-bottom: 8px; }
.field.row { display: flex; }
.field.row > text { margin: 0; }
input, textarea { border: 1px solid #dce6e9; padding: 12px 14px; border-radius: 12px; background: #f7fafb; width: 100%; font-size: 14px; color: #17343e; }
input { height: 50px; }
textarea { height: 112px; line-height: 1.7; }
.tag { display: inline-block; padding: 5px 9px; border: 1px solid #ead7b5; border-radius: 7px; background: #fff5e5; color: #8c651d; font-size: 11px; }
.status { font-size: 12px; color: #637d87; }
.status.ok { color: #087f82; }
.status.info { color: #3679aa; }
.status.warn { color: #9a6a1e; }
.status.crit { color: #c74b45; }
.error { display: block; color: #ab443f; background: #fff0ed; border: 1px solid #f1d2cc; padding: 13px 15px; border-radius: 12px; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; margin-bottom: 12px; }
.success-note { padding: 13px 15px; background: #e7f6f1; border: 1px solid #c8e8df; color: #087f82; font-size: 13px; border-radius: 12px; margin: 14px 0; }
.note { display: block; font-size: 12px; color: #637d87; line-height: 1.8; margin: 12px 0; }
.empty { padding: 36px 20px; color: #486571; font-size: 14px; line-height: 1.8; text-align: center; background: #ffffff; border: 1px dashed #dce6e9; border-radius: 18px; margin: 14px 0; }
.empty text { display: block; }
.empty .hint { margin-top: 6px; color: #7a9098; font-size: 12px; }
.list-item { padding: 16px 0; border-bottom: 1px solid #edf2f4; }
.list-item:last-child { border: 0; }
.list-title { display: block; font-size: 15px; font-weight: 600; margin-bottom: 6px; }
.list-caption { display: block; color: #637d87; font-size: 12px; line-height: 1.7; }
.progress { height: 5px; background: #e1eded; border-radius: 5px; margin-top: 14px; overflow: hidden; }
.progress > view { height: 100%; background: #18a79b; border-radius: 5px; transition: width .2s; }
.picker { padding: 13px; border: 1px solid #dce6e9; border-radius: 12px; background: #f7fafb; }
.offline-banner { padding: 12px 20px; background: #fff1da; color: #8c651d; font-size: 12px; }
.image { width: 100%; border-radius: 12px; background: #e8f0f2; }
.stat-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 18px 0; }
.stat-row > view { padding: 14px 0; }
.stat-row .value { display: block; font-size: 26px; font-weight: 600; margin-bottom: 5px; }
.stat-row .caption { font-size: 12px; color: #637d87; }
.review-options { display: flex; flex-wrap: wrap; gap: 10px; }
.review-options > text { padding: 10px 14px; border: 1px solid #dce6e9; border-radius: 12px; background: white; min-height: 44px; font-size: 13px; }
.review-options > text.selected { background: #e5f5f2; border-color: #087f82; color: #087f82; font-weight: 600; }
.bottom-space { height: 24px; }
</style>
`;
write('App.vue', app);
function append(page,css) {let s=read(page);write(page,s.replace('</style>',css+'\n</style>'));}
append('pages/home/index.vue',`
.welcome-row { margin-bottom: 10px; }
.connection { background: #e5f3ef; border-radius: 20px; padding: 6px 10px; font-size: 11px; }
.welcome .subtitle { margin-bottom: 20px; }
.live-card { border: 0; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 24px #102b3612; }
.live-stage { aspect-ratio: 1.55 / 1; }
.live-foot { padding: 13px 14px; border: 0; }
.live-foot-title { font-size: 13px; }
.live-dot { font-size: 11px; }
.live-foot-note { font-size: 11px; margin-top: 3px; }
.quick-grid { background: transparent; border: 0; gap: 10px; margin-top: 20px; }
.quick { padding: 16px 10px; border: 1px solid #e4ecef; border-radius: 16px; gap: 5px; }
.quick-icon { width: 26px; height: 26px; margin-bottom: 6px; }
.quick-title { font-size: 14px; }
.quick-note { font-size: 11px; }
.task-card.selected { border-left: 3px solid #087f82; padding-left: 16px; }
.task-meta { margin-top: 12px; }
.task-select { font-size: 12px; }
.selected-mark { font-size: 10px; border-radius: 5px; padding: 2px 5px; }
.device-row.selected { border: 0; margin-left: 0; padding-left: 0; }
.device-row.selected .list-title { color: #087f82; }
.footer-links { padding: 18px 0 4px; margin-top: 10px; border-top: 1px solid #dce6e9; font-size: 12px; }
`);
append('pages/tasks/index.vue',`
.task, .independent { border: 1px solid #e4ecef; border-left: 3px solid #e4ecef; }
.task.selected, .independent.selected { border-color: #b4ded8; border-left-color: #087f82; }
.stat-row { border: 0; background: #f5f9fa; padding: 14px 10px; border-radius: 12px; }
.stat-row .value { font-size: 24px; }
.stat-row .caption, .selected-note { font-size: 12px; }
.refresh { padding: 10px; font-size: 13px; }
.independent .list-title { margin-bottom: 0; }
`);
append('pages/records/index.vue',`
.filter-row { flex-wrap: wrap; border: 0; gap: 8px; padding-bottom: 0; margin-bottom: 20px; }
.filter { display: inline-flex; align-items: center; justify-content: center; padding: 10px 14px; min-height: 42px; font-size: 13px; border-radius: 12px; background: white; }
.filter-action { font-size: 12px; padding: 10px 0; }
.record { gap: 11px; border: 1px solid #e4ecef; border-radius: 16px; padding: 12px; margin-bottom: 12px; }
.thumb { width: 64px; height: 76px; border: 0; border-radius: 10px; }
.record-top { flex-wrap: wrap; gap: 2px; }
.record-top .status { font-size: 12px; }
.time { font-size: 10px; }
.record-name { font-size: 13px; font-weight: 600; }
.record-foot { font-size: 11px; }
.total { font-size: 12px; }
`);
append('pages/login/index.vue',`
.login-page { background: #102b36; padding: calc(env(safe-area-inset-top) + 20px) 24px calc(28px + env(safe-area-inset-bottom)); }
.brand { padding: 22px 4px 28px; }
.brand-symbol { width: 48px; height: 48px; border: 2px solid #71ddc8; border-radius: 16px; display: flex; justify-content: center; align-items: center; margin-bottom: 22px; transform: rotate(-8deg); }
.brand-symbol > view { width: 18px; height: 18px; border: 4px solid #71ddc8; border-radius: 50%; }
.kicker { color: #8db0bd; font-size: 10px; letter-spacing: 2px; }
.brand-title { font-size: 36px; font-weight: 700; margin: 10px 0; }
.brand-dot { color: #71ddc8; }
.brand-note { font-size: 13px; color: #aac6d0; line-height: 1.8; }
.login-card { border-radius: 22px; padding: 24px; box-shadow: 0 15px 40px #00000018; }
.mode-head { border: 0; margin-bottom: 20px; padding-bottom: 0; }
.mode-title { font-size: 21px; font-weight: 700; }
.mode-note { font-size: 12px; margin-top: 5px; }
.field { margin: 16px 0; }
.field > text { font-size: 12px; }
.field input { border-radius: 12px; height: 50px; background: #f7fafb; }
.submit { border-radius: 13px; margin-top: 22px; min-height: 50px; }
.secondary-actions { font-size: 12px; flex-wrap: wrap; margin-top: 18px; gap: 14px; }
.secondary-actions > text { padding: 8px 0; }
.foot-note { color: #8db0bd; font-size: 11px; margin-top: 22px; }
`);
append('pages/sync/index.vue',`
.status-card { padding: 18px; border: 1px solid #cbe4e1; border-radius: 18px; background: #eff8f6; margin: 20px 0; flex-wrap: wrap; }
.status-note { font-size: 12px; }
.sync-button { border-radius: 12px; font-size: 13px; min-height: 46px; }
.queue-item { padding: 18px; }
.queue-item .note { margin: 10px 0; }
.item-meta, .time { font-size: 11px; }
.item-actions button { font-size: 13px; min-height: 44px; }
`);
append('pages/detail/index.vue',`
.evidence { border-radius: 18px; overflow: hidden; border: 1px solid #dce6e9; }
.detections { border-radius: 16px; overflow: hidden; border: 1px solid #e4ecef; background: white; }
.det-pos { font-size: 11px; }
.card .list-item .mono { text-align: right; max-width: 66%; }
`);
append('pages/sample/index.vue',`
.image-wrap { border-radius: 18px; }
`);
append('pages/capture/index.vue',`
.capture-page { height: 100vh; height: 100dvh; min-height: 0; }
.task-btn { min-height: 44px; border-radius: 22px; font-size: 12px; }
.close-btn, .round-btn { min-height: 44px; min-width: 44px; }
.source-chip, .posture-chip { border-radius: 20px; padding: 7px 10px; }
.source-chip { max-width: calc(100% - 148px); }
.verdict-overlay { border-radius: 12px; bottom: calc(246px + env(safe-area-inset-bottom)); }
.result-overlay { border-radius: 12px; bottom: calc(306px + env(safe-area-inset-bottom)); }
.result-overlay.error { color: #ab443f; }
.mode-switch { gap: 6px; }
.mode-switch text { border-radius: 22px; min-height: 44px; line-height: 42px; min-width: 70px; font-size: 13px; }
.side-slot { border-radius: 18px; }
.shutter { box-shadow: 0 0 0 6px #f28b6110; }
.shutter[disabled] { background: transparent; }
.shutter-hint { font-size: 12px; min-height: 20px; }
.settings-sheet { border-radius: 24px 24px 0 0; max-height: 82%; overflow-y: auto; }
.sheet-head { padding-bottom: 16px; }
.sheet-done { padding: 8px 0 8px 18px; font-size: 13px; }
.sheet-row { padding: 18px 0; }
.sheet-label, .sheet-note { font-size: 12px; }
.sheet-value, .sheet-action { font-size: 14px; }
.sheet-links { font-size: 13px; gap: 10px 20px; }
.sheet-links > text { padding: 8px 0; }
@media (max-height: 680px) { .guide-frame { top: 21%; width: 66%; left: 17%; } .camera-controls { padding-top: 30px; } }
`);
append('pages/live/index.vue',`
.back { width: 44px; min-height: 44px; height: 44px; border-radius: 14px; }
.heading-title { font-weight: 650; }
.stage { overflow: hidden; border-radius: 18px; margin: 0 16px; }
.stage.full { border-radius: 0; margin: 0; }
.device-switch { border-radius: 12px; }
.readout, .metrics { border-radius: 16px; overflow: hidden; }
.actions button { border-radius: 14px; }
.capture-result { border-radius: 14px; }
`);
// Keep navigation and native tab surfaces aligned with the application palette.
const pages=JSON.parse(read('pages.json'));
pages.pages.sort((a,b)=> a.path==='pages/home/index'?-1:b.path==='pages/home/index'?1:0);
pages.globalStyle={...pages.globalStyle,navigationBarBackgroundColor:'#f3f6f7',backgroundColor:'#f3f6f7'};
pages.pages.find(p=>p.path==='pages/login/index').style.navigationStyle='custom';
pages.tabBar={...pages.tabBar,color:'#7a9098',selectedColor:'#087f82',backgroundColor:'#ffffff',height:'62px',fontSize:'11px',iconWidth:'25px',spacing:'4px'};
write('pages.json',JSON.stringify(pages,null,2)+'\n');
const require=createRequire(resolve(root,'apps/server/package.json'));
const sharp=require('sharp');
const paths={home:'<path d="m3 11 9-8 9 8M6 10v11h5v-7h3v7h5V10"/>',tasks:'<rect x="5" y="4" width="14" height="18" rx="3"/><path d="M9 4V2h6v2M9 10h6M9 14h6M9 18h4"/>',camera:'<path d="M8 6 10 3h4l2 3h4a2 2 0 0 1 2 2v12H2V8a2 2 0 0 1 2-2z"/><circle cx="12" cy="13" r="4"/>',records:'<rect x="5" y="2" width="15" height="20" rx="3"/><path d="M9 7h7M9 11h7M9 15h5M2 6v14"/>',sync:'<path d="M20 8a8 8 0 0 0-14-3L3 8m0-5v5h5M4 16a8 8 0 0 0 14 3l3-3m0 5v-5h-5"/>'};
for(const name of ['home','tasks','camera','records'])for(const on of [false,true]){
 const color=on?'#087f82':'#7a9098';
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
 await sharp(Buffer.from(svg)).png().toFile(resolve(src,`static/tab-${name}${on?'-on':''}.png`));
}
for(const name of ['camera','records','sync']){
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="#087f82" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
 await sharp(Buffer.from(svg)).png().toFile(resolve(src,`static/action-${name}.png`));
}
const icon=`<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect width="512" height="512" rx="112" fill="#102b36"/><g fill="none" stroke="#71ddc8" stroke-width="22" stroke-linecap="round"><path d="M120 204v-55q0-29 29-29h55m104 0h55q29 0 29 29v55m0 104v55q0 29-29 29h-55m-104 0h-55q-29 0-29-29v-55"/><circle cx="256" cy="256" r="65"/></g><circle cx="345" cy="167" r="15" fill="#f28b61"/></svg>`;
for(const size of [48,72,96,144,192,512])await sharp(Buffer.from(icon)).resize(size,size).png().toFile(resolve(src,`static/icon-${size}.png`));
console.log('Applied unified design to all mobile pages and generated PNG icons.');
