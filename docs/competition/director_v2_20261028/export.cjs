const fs=require('fs'),path=require('path');
const shots=require('./shots.js');const {renderShot}=require('./art.js');
const root=__dirname;
function embed(svg){return svg.replace(/href="assets\/([^"]+)"/g,(_,name)=>{const b=fs.readFileSync(path.join(root,'assets',name));return `href="data:image/${name.endsWith('.png')?'png':'jpeg'};base64,${b.toString('base64')}"`})}
for(const s of shots)fs.writeFileSync(path.join(root,'frames',`shot_${s.id}.svg`),embed(renderShot(s,s.art==='benchmark'?.75:.62)));
for(const [id,p,name] of [['01',.04,'opening_a'],['01',.6,'opening_b'],['05',.18,'dual_multiply'],['05',.8,'array_expanded'],['07',.2,'row_before'],['07',.8,'row_overlap']])fs.writeFileSync(path.join(root,'frames',name+'.svg'),embed(renderShot(shots.find(x=>x.id===id),p)));
const stamp=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;
let out='# 《在这块板上》逐镜执行稿\n\n总长176秒。镜头画面为预演；计划中的运行响应必须以同次真实拍摄替换。设备示意比例不用于布置电路。\n\n';
for(const s of shots)out+=`## ${s.id}｜${stamp(s.start)}–${stamp(s.end)}｜${s.title}\n\n![镜头${s.id}预演](C:/00_workplace/fpga/cnn_accelerator/docs/competition/director_v2_20261028/frames/shot_${s.id}.svg)\n\n- **镜头形式：** ${s.kind}；${s.lens}。${s.status}。\n- **动作与构图：** ${s.action}\n- **旁白：** ${s.vo}\n- **衔接：** ${s.cut}\n- **声音：** ${s.sound}\n- **已有依据：** ${s.proof}\n- **拍摄/制作准入：** ${s.gate}\n- **来源定位：** ${s.source}\n\n`;
fs.writeFileSync(path.join(root,'shotbook.md'),out);
fs.writeFileSync(path.join(root,'shots.json'),JSON.stringify(shots,null,2));
console.log(JSON.stringify({shots:shots.length,duration:shots.at(-1).end,frames:fs.readdirSync(path.join(root,'frames')).length}));
