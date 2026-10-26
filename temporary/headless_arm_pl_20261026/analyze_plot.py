from pathlib import Path
import json,csv,statistics,hashlib,sys,re,platform,importlib.metadata
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
h=Path(__file__).resolve().parent;r=h.parents[1];d=h/'download';figdir=h/'figures';figdir.mkdir(exist_ok=True)
skill=Path('C:/Users/YUKINO/.codex/skills/scientific-visualization');sys.path.insert(0,str(skill/'scripts'))
from style_presets import style_context
from figure_export import export_figure
result=json.loads((d/'fixed_results.json').read_text());plan=json.loads((h/'plan.json').read_text());env=json.loads((d/'environment.json').read_text());restored=json.loads((d/'restored.json').read_text())
assert result['modelSha256']==plan['modelSha256'] and len(result['cases'])==3
assert restored['state']['fresh'] and not restored['newSdIoError'] and not restored['watchdogTriggered']
assert env['captureDmaControl']&1==0 and env['displayDmaControl']&1==0 and not env['runtimeServicePids']
layout=h/'command_layout.json'
commands=json.loads(layout.read_text()) if layout.exists() else [list(map(int,m.split(','))) for m in re.findall(r'^\{([\d,-]+)\},?$',(r/'camera/terminal/build/arm/model_graph.h').read_text(),re.M)]
assert len(commands)==33;commands[0][4]=result['inputChannels']
layout.write_text(json.dumps(commands,indent=2)+'\n')
conv=[i for i,c in enumerate(commands) if c[8] in (1,3)]
assert len(conv)==21 and sum((c[6]//c[7])**2*c[4]*c[5]*c[8]**2 for c in commands if c[8] in (1,3))==result['macs']
rows=[];layer_rows=[];table=[];labels={'photo_23':'纸箱','photo_02':'瓶盖','photo_15':'瓶子'}
for case in result['cases']:
    assert len(case['cpu'])==3 and len(case['pl'])==100 and case['mismatches']==0 and case['comparedBytes']==8085
    assert (d/(case['name']+'.cpu.i8')).read_bytes()==(d/(case['name']+'.pl.i8')).read_bytes()
    for path in ('cpu','pl'):
        for repeat,run in enumerate(case[path]):
            assert run['totalNs']>0 and run['outputSha256']==case['outputSha256']
            rows.append({'input':case['name'],'category':case['category'],'method':path,'repeat':repeat,'total_ms':run['totalNs']/1e6,'conv21_ms':sum(run['layerNs'][i] for i in conv)/1e6,'input_sha256':case['inputSha256'],'output_sha256':run['outputSha256'],'method_order':case['methodOrder']})
            for i,ns in enumerate(run['layerNs']):layer_rows.append({'input':case['name'],'method':path,'repeat':repeat,'layer':i,'kernel':commands[i][8],'latency_ms':ns/1e6})
    a=np.array([v['totalNs']/1e6 for v in case['cpu']]);b=np.array([v['totalNs']/1e6 for v in case['pl']])
    ca=[sum(v['layerNs'][i] for i in conv)/1e6 for v in case['cpu']];cb=[sum(v['layerNs'][i] for i in conv)/1e6 for v in case['pl']]
    table.append({'input':case['name'],'category':case['category'],'arm_median_ms':float(np.median(a)),'arm_min_ms':float(a.min()),'arm_max_ms':float(a.max()),'pl_median_ms':float(np.median(b)),'pl_min_ms':float(b.min()),'pl_max_ms':float(b.max()),'speedup':float(np.median(a)/np.median(b)),'arm_conv21_median_ms':statistics.median(ca),'pl_conv21_median_ms':statistics.median(cb),'mismatches':0})
def write_csv(path,items):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=items[0].keys());w.writeheader();w.writerows(items)
write_csv(h/'raw_timings.csv',rows);write_csv(h/'raw_layer_timings.csv',layer_rows);write_csv(h/'comparison.csv',table)
aggregate={k:statistics.median(t[k] for t in table) for k in ('arm_median_ms','pl_median_ms','arm_conv21_median_ms','pl_conv21_median_ms')}
aggregate['speedup']=aggregate['arm_median_ms']/aggregate['pl_median_ms'];aggregate['conv21_speedup']=aggregate['arm_conv21_median_ms']/aggregate['pl_conv21_median_ms']
aggregate['pl_equivalent_inferences_per_second']=1000/aggregate['pl_median_ms'];aggregate['arm_equivalent_inferences_per_second']=1000/aggregate['arm_median_ms']
summary={'aggregate':aggregate,'cases':table,'arm_measured_runs':9,'pl_measured_runs':300,'int8_mismatches':0,'samplingUnit':'Repeated execution of 3 fixed inputs on one board; not independent boards or an accuracy population','estimator':'Median of the three per-input medians; speedup is ratio of matching aggregate medians','spread':'All raw repetitions; per-input observed minimum and maximum, no confidence interval','exclusions':'No measured samples excluded; predefined 1 ARM warmup on first input and 3 PL warmups per input are outside measured arrays','environment':env,'restoration':{'fresh':restored['state']['fresh'],'governor':restored['governor'],'sdIoError':restored['newSdIoError']}}
(h/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
provenance={'raw_data':'download/fixed_results.json; raw_timings.csv; raw_layer_timings.csv','raw_sha256':hashlib.sha256((d/'fixed_results.json').read_bytes()).hexdigest(),'transformations':['Nanoseconds / 1e6 to milliseconds','Per-input medians; equal-input median aggregation','Speedup = ARM latency / PL latency','No measured sample exclusion or smoothing'],'uncertainty':'Observed min/max plus all repetitions; no inferential confidence interval','sampling_unit':summary['samplingUnit'],'scope':plan['scope'],'font':'Microsoft YaHei (installed on rendering host)','software':{'python':platform.python_version(),'matplotlib':matplotlib.__version__,'numpy':np.__version__},'skill_reference':plan['softwareReference'],'destination':'Provisional engineering report/slide figure, no publisher requirements claimed'}
blue='#0072B2';orange='#D55E00';dark='#222222'
with style_context('default',palette_name='okabe_ito_on_white'):
    with plt.rc_context({'font.family':'Microsoft YaHei','font.size':10,'axes.titlesize':12,'axes.labelsize':10,'svg.fonttype':'none','pdf.fonttype':42,'axes.unicode_minus':False}):
        fig=plt.figure(figsize=(230/25.4,145/25.4),layout='constrained')
        grid=fig.add_gridspec(3,2,height_ratios=[.20,1,.23],width_ratios=[1.3,1])
        title=fig.add_subplot(grid[0,:]);title.axis('off');title.text(0,1,'无显示 / 无采集：纯推理加速对比',fontsize=17,fontweight='bold',va='top');title.text(0,0,'同一 Zynq-7020、CAPS-RGB-v1、固定输入；Linux 下完整 33 算子',fontsize=10,color='#444444',va='bottom')
        ax=fig.add_subplot(grid[1,0]);bx=fig.add_subplot(grid[1,1])
        rng=np.random.default_rng(20261026)
        for j,case in enumerate(result['cases']):
            for path,delta,color,marker in [('cpu',-.15,blue,'o'),('pl',.15,orange,'D')]:
                values=np.array([v['totalNs']/1e6 for v in case[path]]);y=j+delta
                ax.scatter(values,y+rng.uniform(-.045,.045,len(values)),s=10 if path=='pl' else 21,marker=marker,color=color,alpha=.25 if path=='pl' else .65,zorder=2)
                ax.hlines(y,values.min(),values.max(),color=color,lw=2)
                med=float(np.median(values));ax.scatter([med],[y],s=45,marker=marker,color=color,edgecolor='white',linewidth=.6,zorder=4)
                ax.annotate(f'{med:,.2f} ms',(med,y),xytext=(6,-16 if path=='pl' else 7),textcoords='offset points',fontsize=9,color=blue if path=='cpu' else dark)
        allv=[row['total_ms'] for row in rows];ax.set_xscale('log');ax.set_xlim(min(allv)*.68,max(allv)*2.1);ax.set_ylim(2.65,-.7)
        ax.set_yticks(range(3),[labels[c['name']]+'\n'+c['name'] for c in result['cases']]);ax.set_xlabel('完整推理延时 / ms（对数刻度）');ax.set_title('(a) 全部重复、观察范围与中位数',loc='left',pad=14);ax.grid(axis='x',which='major',color='#dddddd');ax.grid(axis='y',visible=False)
        handles=[Line2D([0],[0],marker='o',color=blue,lw=0,label='ARM：既有单核标量'),Line2D([0],[0],marker='D',color=orange,lw=0,label='PL：关闭显示与采集')];ax.legend(handles=handles,loc='upper left',fontsize=8,frameon=False)
        speeds=[t['speedup'] for t in table]+[aggregate['speedup']];yy=np.arange(4)
        bx.barh(yy,speeds,color=[blue]*3+[orange],edgecolor=dark,height=.57,hatch=['','','','//'])
        for y,v in zip(yy,speeds):bx.text(v+max(speeds)*.025,y,f'{v:.2f}×',va='center',fontsize=11,fontweight='bold' if y==3 else 'normal')
        bx.set_yticks(yy,[labels[t['input']] for t in table]+['汇总']);bx.invert_yaxis();bx.set_xlim(0,max(speeds)*1.28);bx.set_xlabel('ARM 中位延时 / PL 中位延时');bx.set_title('(b) 相对既有 ARM 标量基线的加速比',loc='left',pad=14);bx.grid(axis='x',color='#dddddd');bx.grid(axis='y',visible=False)
        footer=fig.add_subplot(grid[2,:]);footer.axis('off');footer.text(0,1,'ARM：Cortex-A9 CPU1 / 666.667 MHz，既有 O3 标量 INT8，不使用 NEON。\nPL：48×8 INT8 / 125 MHz；计入 PS 寄存器配置与轮询，排除两端装载、预处理和输出提取。\n每输入 ARM n=3、PL n=100；3 个回放输入，全部测量保留；不是摄像头端到端 FPS。',fontsize=8.8,va='top',linespacing=1.5)
        export_figure(fig,figdir/'headless_arm_pl',formats=['png','svg','pdf'],dpi=600,bbox_inches=None,provenance=provenance,write_manifest=True,overwrite=True)
        plt.close(fig)
        fig,ax=plt.subplots(figsize=(230/25.4,112/25.4),layout='constrained')
        for path,color,marker,label in [('cpu',blue,'o','ARM：既有单核标量'),('pl',orange,'D','PL：关闭显示与采集')]:
            values=[statistics.median(statistics.median(v['layerNs'][i]/1e6 for v in c[path]) for c in result['cases']) for i in range(33)]
            assert min(values)>0;ax.plot(range(33),values,color=color,marker=marker,markersize=3.6,lw=1.5,linestyle='-' if path=='cpu' else '--',label=label)
        ax.set_yscale('log');ax.set_xticks(range(0,33,2));ax.set(xlabel='算子编号（从 0 开始，全部 33 个）',ylabel='逐算子延时 / ms（对数刻度）');fig.suptitle('逐算子延时：先取各输入中位数，再对三个输入等权取中位数',fontsize=12,x=.08,ha='left');ax.legend(loc='lower left',bbox_to_anchor=(0,1.005),ncol=2,frameon=False,fontsize=9);ax.grid(axis='y',which='major',color='#dddddd')
        fig.supxlabel('同一模型、同一固定输入；全部 33 个算子均保留；连线仅辅助阅读，无测量排除。',fontsize=9)
        export_figure(fig,figdir/'layer_latency',formats=['png','svg','pdf'],dpi=600,bbox_inches=None,provenance=provenance,write_manifest=True,overwrite=True);plt.close(fig)
report=['# 无显示与采集条件下的 ARM / PL 纯推理对比','',f"完整 33 算子：既有 ARM 标量基线 **{aggregate['arm_median_ms']:.3f} ms**，PL **{aggregate['pl_median_ms']:.3f} ms**，中位延时之比 **{aggregate['speedup']:.2f}×**。",'', '![延时与加速比](figures/headless_arm_pl.png)','', '| 固定输入 | ARM 中位数 / ms | PL 中位数 / ms | 加速比 | ARM 观察范围 / ms | PL 观察范围 / ms | INT8 差异 |','|---|---:|---:|---:|---|---|---:|']
for t in table:report.append(f"| {t['input']}（{labels[t['input']]}） | {t['arm_median_ms']:.3f} | {t['pl_median_ms']:.3f} | {t['speedup']:.2f}× | {t['arm_min_ms']:.3f}–{t['arm_max_ms']:.3f} | {t['pl_min_ms']:.3f}–{t['pl_max_ms']:.3f} | 0 / 8085 |")
report+=['','| 统计范围 | ARM / ms | PL / ms | 中位延时比 |','|---|---:|---:|---:|',f"| 全部 33 算子（主结果） | {aggregate['arm_median_ms']:.3f} | {aggregate['pl_median_ms']:.3f} | {aggregate['speedup']:.2f}× |",f"| 其中 21 条卷积命令 | {aggregate['arm_conv21_median_ms']:.3f} | {aggregate['pl_conv21_median_ms']:.3f} | {aggregate['conv21_speedup']:.2f}× |",'', '## 测量边界','', '- 当前模型 CAPS-RGB-v1-20261022，3×224×224 INT8；模型 SHA-256 `'+result['modelSha256']+'`。MAC 数 '+str(result['macs'])+'。', '- ARM 与 PL 使用同一份输入张量和模型，33 个算子全部执行。输入为既有照片序列预先固定的前三份，不是分类精度验证集。','- 复用原 benchmark ELF，SHA-256 `'+plan['binarySha256']+'`；ARM 源码及编译选项未修改。它是既有 O3 单核标量直接卷积基线，原基准明确禁用自动向量化，不代表最优 ARM/NEON 库。','- 两端均绑定 CPU1，CPU 当前频率 '+env['cpuCurrentKHz']+' kHz、governor=performance；PL 时钟 125 MHz。测试前停止 engine/panel/manager，卸载 framebuffer 驱动，确认 HDMI 与采集 DMA 的运行位均为 0，并令传感器 PWDN 有效。','- “纯 PL”在这里指 Linux 下关闭显示/采集的纯算子加速路径，不是脱离 PS 的裸机程序。PL 计时包括 PS 写寄存器和完成轮询；两端都排除模型装载、输入准备/复制和输出提取。','- 每输入 ARM 3 次、PL 100 次；首输入 ARM 预热 1 次，各输入 PL 预热 3 次。预热不纳入数组；全部 9/300 次测量均保留，无事后异常值删除、平滑或截断。每个 ARM 前向（含预热）及重复 PL 输出均对拍通过。','- 汇总先计算各输入的中位数，再对三个输入等权取中位数；加速比为匹配统计范围的 ARM / PL。图中范围为观察到的最小/最大值，不是置信区间。重复来自同一板卡，不是独立板卡样本。','- 此范围的倒数仅为等效纯推理吞吐：ARM '+f"{aggregate['arm_equivalent_inferences_per_second']:.4f}"+' 次/s、PL '+f"{aggregate['pl_equivalent_inferences_per_second']:.3f}"+' 次/s，不是实时采集/显示 FPS。先前实时 16.24 FPS 属于另一运行条件。','- 本次 PL 纯算子计时使用原 fixed_bench，不能把它和先前 board_bench 的 52.544 ms 卷积区间混为一个范围；主结果统计完整 33 算子。','- 测试数据和脚本放在任务目录，板端输入/输出位于 /run 临时内存；没有更改正式源码、ELF、bitstream、QSPI 或 SD 启动文件。测试后恢复全部服务、25 Hz HDMI 与原 governor='+restored['governor']+'，模型/产品/计数和持久文件哈希一致，预览 fresh=true，未新增 SD I/O 错误。','', '## 图像说明与复现','', '主图左侧显示全部重复（ARM 圆点、PL 菱形），横线是每输入的观察范围，较大标记为中位数；横轴为明确标注的对数刻度。右侧加速比条形从 0 起；汇总采用橙色斜线纹理。两图都有原始 CSV 数据替代。','', '![逐层延时](figures/layer_latency.png)','', '数据：`download/fixed_results.json`、`raw_timings.csv`、`raw_layer_timings.csv`、`comparison.csv`；元数据：`plan.json`、`summary.json`、`download/environment.json`、`download/restored.json`；绘图代码：`analyze_plot.py`。','', '在当前 Python 环境运行 `python -X utf8 analyze_plot.py` 可复现；包版本与来源位于图的 `.export.json`。导出 PNG/SVG/PDF，PNG 为 600 DPI，主图宽 230 mm，供一般工程报告/展示使用；未声称符合某出版社规范。','', '## 软件方法引用','', plan['softwareReference']]
(h/'report.md').write_text('\n'.join(report)+'\n',encoding='utf8')
print(json.dumps(aggregate,indent=2))
