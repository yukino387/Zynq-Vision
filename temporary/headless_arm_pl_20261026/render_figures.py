from pathlib import Path
import sys,json,statistics,hashlib,csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
h=Path(__file__).resolve().parent;f=h/'figures';s=json.loads((h/'summary.json').read_text());raw=json.loads((h/'download/fixed_results.json').read_text());plan=json.loads((h/'plan.json').read_text())
sys.path.insert(0,'C:/Users/YUKINO/.codex/skills/scientific-visualization/scripts')
from figure_export import export_figure
from style_presets import style_context
blue='#0072B2';orange='#D55E00';dark='#222222';names={'photo_23':'纸箱','photo_02':'瓶盖','photo_15':'瓶子'}
commands=json.loads((h/'command_layout.json').read_text());conv=[i for i,c in enumerate(commands) if c[8] in (1,3)]
provenance={'raw_data':'download/fixed_results.json','raw_sha256':hashlib.sha256((h/'download/fixed_results.json').read_bytes()).hexdigest(),'analysis':'analyze_plot.py; render_figures.py','transformations':['ns / 1e6 = ms','Per-input medians, followed by equal-input median aggregation','Speedup = matching ARM median / PL median','SD uses ddof=1; observed min/max include all measured samples'],'measured_samples':{'arm':9,'pl':300,'inputs':3},'exclusions':'Predefined warmups only; no measured exclusions','scope':plan['scope'],'arm_baseline':plan['cpu'],'skill_reference':plan['softwareReference'],'destination':'Engineering report and presentation; no publisher-specific requirements'}
def export(fig,name):
    export_figure(fig,f/name,formats=['png','svg','pdf'],dpi=600,bbox_inches=None,write_manifest=True,overwrite=True,provenance=provenance);plt.close(fig)
stats=[]
for c in raw['cases']:
    for path in ('cpu','pl'):
        x=np.array([v['totalNs']/1e6 for v in c[path]])
        stats.append({'input':c['name'],'method':path,'n':len(x),'mean_ms':float(x.mean()),'sd_ms':float(x.std(ddof=1)),'median_ms':float(np.median(x)),'min_ms':float(x.min()),'p05_ms':float(np.quantile(x,.05)),'p95_ms':float(np.quantile(x,.95)),'max_ms':float(x.max())})
(h/'descriptive_statistics.json').write_text(json.dumps(stats,indent=2)+'\n',encoding='utf8')
with (h/'descriptive_statistics.csv').open('w',newline='',encoding='utf-8-sig') as stream:
    writer=csv.DictWriter(stream,fieldnames=stats[0].keys());writer.writeheader();writer.writerows(stats)
with style_context('default'):
 with plt.rc_context({'font.family':'Microsoft YaHei','font.size':12,'axes.titlesize':14,'axes.labelsize':12,'pdf.fonttype':42,'svg.fonttype':'none','axes.unicode_minus':False}):
    a=s['aggregate'];fig,(ax,bx)=plt.subplots(1,2,figsize=(250/25.4,125/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.3,1]})
    fig.suptitle('ARM 单核标量与 PL 纯推理性能',fontsize=19,fontweight='bold')
    scope=['完整 33 算子','21 条卷积命令'];arm=[a['arm_median_ms'],a['arm_conv21_median_ms']];pl=[a['pl_median_ms'],a['pl_conv21_median_ms']];y=np.arange(2)
    ax.barh(y-.19,arm,height=.33,color=blue,label='ARM 单核标量',edgecolor=dark)
    ax.barh(y+.19,pl,height=.33,color=orange,label='PL',edgecolor=dark,hatch='//')
    for j,(v,w) in enumerate(zip(arm,pl)):
        ax.text(v+180,j-.19,f'{v:,.3f}',va='center',fontsize=11)
        ax.text(w+180,j+.19,f'{w:.3f}',va='center',fontsize=11,fontweight='bold')
    ax.set_yticks(y,scope);ax.invert_yaxis();ax.set_xlim(0,max(arm)*1.35);ax.set_xlabel('中位延时 / ms');ax.set_title('推理延时',loc='left');ax.legend(loc='lower right',fontsize=11,frameon=False);ax.grid(axis='x',color='#dddddd');ax.grid(axis='y',visible=False)
    ratios=[a['speedup'],a['conv21_speedup']];bx.barh(y,ratios,color=orange,edgecolor=dark,hatch='//',height=.55)
    for j,v in enumerate(ratios):bx.text(v+6,j,f'{v:.2f}×',va='center',fontsize=14,fontweight='bold')
    bx.set_yticks(y,scope);bx.invert_yaxis();bx.set_xlim(0,max(ratios)*1.32);bx.set_xlabel('加速比：ARM / PL');bx.set_title('实测加速比',loc='left');bx.grid(axis='x',color='#dddddd');bx.grid(axis='y',visible=False)
    export(fig,'headless_arm_pl')
    fig,ax=plt.subplots(figsize=(250/25.4,110/25.4),layout='constrained')
    for path,color,marker,label in [('cpu',blue,'o','ARM 单核标量'),('pl',orange,'D','PL')]:
        values=[statistics.median(statistics.median(v['layerNs'][i]/1e6 for v in c[path]) for c in raw['cases']) for i in range(33)]
        ax.plot(range(33),values,color=color,marker=marker,markersize=4.5,lw=1.8,linestyle='-' if path=='cpu' else '--',label=label)
    ax.set_yscale('log');ax.set_xticks(range(0,33,2));ax.set(xlabel='算子编号',ylabel='中位延时 / ms（对数刻度）');fig.suptitle('全部 33 个算子延时',fontsize=18,fontweight='bold');ax.legend(loc='lower left',bbox_to_anchor=(0,1.005),ncol=2,fontsize=12,frameon=False);ax.grid(axis='y',which='major',color='#dddddd');export(fig,'layer_latency')
    fig,(ax,bx)=plt.subplots(1,2,figsize=(250/25.4,115/25.4),layout='constrained');fig.suptitle('全部重复测量分布',fontsize=18,fontweight='bold');rng=np.random.default_rng(20261026)
    for axis,path,color,marker,label in [(ax,'cpu',blue,'o','ARM 单核标量：9 次'),(bx,'pl',orange,'D','PL：300 次')]:
        for j,c in enumerate(raw['cases']):
            x=np.array([v['totalNs']/1e6 for v in c[path]])
            axis.scatter(x,j+rng.uniform(-.09,.09,len(x)),s=24 if path=='cpu' else 12,color=color,marker=marker,alpha=.8 if path=='cpu' else .45)
            axis.hlines(j,x.min(),x.max(),color=color,lw=2);axis.scatter([np.median(x)],[j],color=dark,marker='|',s=150,lw=2,zorder=4)
        axis.set_yticks(range(3),[names[c['name']] for c in raw['cases']]);axis.invert_yaxis();axis.set_xlabel('完整 33 算子延时 / ms');axis.set_title(label,loc='left');axis.grid(axis='x',color='#dddddd');axis.grid(axis='y',visible=False);axis.margins(x=.15,y=.25)
    export(fig,'repeat_distribution')
    fig,ax=plt.subplots(figsize=(300/25.4,105/25.4),layout='constrained');ax.axis('off');fig.suptitle('完整 33 算子统计表',fontsize=19,fontweight='bold')
    columns=['输入','ARM 中位 / ms','PL 中位 / ms','加速比','ARM 均值 ± SD / ms','PL 均值 ± SD / ms','次数 ARM / PL'];cells=[]
    for c,t in zip(raw['cases'],s['cases']):
        v={p:next(q for q in stats if q['input']==c['name'] and q['method']==p) for p in ('cpu','pl')}
        cells.append([names[c['name']]+' '+c['name'],f"{t['arm_median_ms']:,.3f}",f"{t['pl_median_ms']:.3f}",f"{t['speedup']:.2f}×",f"{v['cpu']['mean_ms']:,.3f} ± {v['cpu']['sd_ms']:.3f}",f"{v['pl']['mean_ms']:.3f} ± {v['pl']['sd_ms']:.3f}",'3 / 100'])
    table=ax.table(cellText=cells,colLabels=columns,cellLoc='center',loc='center',colWidths=[.16,.13,.12,.10,.20,.19,.10]);table.auto_set_font_size(False);table.set_fontsize(11);table.scale(1,2.8)
    for (row,col),cell in table.get_celld().items():
        cell.set_edgecolor('#bbbbbb')
        if row==0:cell.set_facecolor('#e8eff5');cell.set_text_props(fontweight='bold')
        elif row%2:cell.set_facecolor('#f5f7f9')
    export(fig,'statistics_table')
report=h/'report.md'
if report.exists():
    text=report.read_text(encoding='utf8')
    old='主图左侧显示全部重复（ARM 圆点、PL 菱形），横线是每输入的观察范围，较大标记为中位数；横轴为明确标注的对数刻度。右侧加速比条形从 0 起；汇总采用橙色斜线纹理。两图都有原始 CSV 数据替代。'
    new='主图用从零开始的共同线性坐标展示完整 33 算子与 21 条卷积命令的中位延时及匹配加速比。重复分布图保留全部 ARM 圆点、PL 菱形，横线为观察范围，黑色短线为中位数；两个面板各自标注延时坐标。统计表包含次数、中位数、均值和样本标准差（SD，ddof=1）。'
    text=text.replace(old,new).replace('运行 `python -X utf8 analyze_plot.py` 可复现','运行 `python -X utf8 analyze_plot.py` 后运行 `python -X utf8 render_figures.py` 可复现').replace('主图宽 230 mm','主图宽 250 mm')
    if '![统计表]' not in text:text+='\n![统计表](figures/statistics_table.png)\n\n![全部重复分布](figures/repeat_distribution.png)\n'
    report.write_text(text,encoding='utf8')
print('CLEAN_FIGURES_EXPORTED: summary, layers, repetitions, statistics')
