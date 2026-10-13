from pathlib import Path
import struct,json,statistics,re,csv,hashlib,datetime
root=Path(__file__).resolve().parents[2]; test=Path(__file__).resolve().parent; build=test/'build'; board=build/'board'
log=(board/'result.log').read_text(); assert 'PASS:' in log and 'TEST ERROR:' not in log
heads={}
for name,count in [('out0',1617),('out1',6468)]:
 a=(board/(name+'.bin')).read_bytes()[:count]; e=(root/'temporary/int8_model_test/build/golden'/(name+'.bin')).read_bytes()
 assert a==e,name; heads[name]=hashlib.sha256(a).hexdigest()
def words(file,count): return struct.unpack('<'+str(count)+'I',file.read_bytes())
raw=words(board/'all_layer_us.bin',99); setup=words(board/'setup_us.bin',99)
commands=struct.unpack('<330i',(root/'camera/int8/metadata.bin').read_bytes()[:1320])
names=json.loads((root/'temporary/int8_rebuild_test/build/command_names.json').read_text())
live=words(build/'live_layer_us.bin',33); poll=words(build/'live_poll_window_us.bin',33); cpu_raw=words(build/'live_cpu.bin',9)
cpu=dict(zip(['camera_begin_us','input_copy_us','gray_horizontal_us','gray_vertical_us','register_setup_us','head_copy_us','completion_observation_window_us','input_flush_us','camera_finish_us'],cpu_raw))
kinds={3:'3×3 卷积',1:'1×1 卷积',2:'最大池化',0:'上采样',5:'分支重量化'}
layers=[]; logical=physical=0
for i,label in enumerate(names):
 ci,co,size,stride,k,act=commands[i*10+4:i*10+10]; out=size//stride if k in [1,3] else size//2 if k==2 else size*2 if k==0 else size
 vals=[raw[r*33+i] for r in range(3)]; med=statistics.median(vals)
 mac=ci*co*out*out*k*k if k in [1,3] else 0
 padded=((ci+7)//8*8)*((co+47)//48*48)*out*out*k*k if k in [1,3] else 0
 logical+=mac;physical+=padded
 layers.append(dict(index=i,name=label,operator=kinds[k],ci=ci,co=co,input_size=size,output_size=out,activation=act,
                    median_us=med,min_us=min(vals),max_us=max(vals),live_snapshot_us=live[i],observation_window_us=poll[i],
                    logical_mac=mac,padded_mac=padded))
total=sum(r['median_us'] for r in layers)
for row in layers:row['share_percent']=row['median_us']/total*100
cases=json.loads((test/'probes.json').read_text()); vals=words(board/'probe_us.bin',len(cases)*3)
probes=[dict(ci=c[0],co=c[1],size=c[2],stride=c[3],kernel=c[4],samples_us=list(vals[i*3:i*3+3]),median_us=statistics.median(vals[i*3:i*3+3])) for i,c in enumerate(cases)]
forward=[int(v,0) for v in re.search('FORWARD_US = (.*)',log).group(1).split()]
network=json.loads((build/'short_udp_results.json').read_text())
stats=[r['status'] for r in network['stats'] if r['phase']=='detect' and r['status'][1]==0 and r['status'][9]>0][3:]
assert stats and all(r[10]==0 for r in stats)
received=[r for r in network['frames'] if r[0]=='detect'][3:]
fps=(len(received)-1)/(received[-1][2]-received[0][2])
timing=dict(zip(['capture_us','reported_conversion_us','forward_us','transfer_us','cycle_us'],[statistics.median(r[i] for r in stats) for i in range(5,10)]))
groups=[dict(operator=kinds[k],count=sum(commands[i*10+8]==k for i in range(33)),us=sum(r['median_us'] for r in layers if r['operator']==kinds[k])) for k in [3,1,2,5,0]]
result=dict(clock_mhz=125,git_base='78bd8c2',method='PS timestamps, 3 repeated fixed-input forwards, 19 controlled probes repeated 3 times, 5-second camera+UDP sample; no hardware profiler bitstream used',
            heads_sha256=heads,quiet_forward_us=forward,quiet_operator_sum_us=total,quiet_register_setup_us=[sum(setup[r*33:(r+1)*33]) for r in range(3)],
            quiet_input_flush_us=words(board/'input_flush_us.bin',3),cpu_snapshot=cpu,live_timing_medians=timing,received_fps=fps,
            live_cycle_range_us=[min(r[9] for r in stats),max(r[9] for r in stats)],live_sample_count=len(stats),logical_mac=logical,padded_mac=physical,
            operators=groups,layers=layers,probes=probes)
(build/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (build/'layers.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(layers[0]));w.writeheader();w.writerows(layers)
with (build/'probes.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(probes[0]));w.writeheader();w.writerows(probes)
report=[]
def add(s=''):report.append(s)
add('# INT8 灰度模型运行耗时与瓶颈诊断报告')
add(f'\n日期：{datetime.date.today()}。工程：Zynq-7020 / Vitis 2026.1。代码基线：`78bd8c2`。')
add('\n## 1. 结论')
add('当前瓶颈不是 PS 启动各层的开销，也不能简单归结为 DDR 带宽不足。实测与 HLS 计划共同指向：深层小特征图卷积受权重准备限制；首层受输出处理影响明显；池化和分支重量化也占据可观时间。下一步应先优化现有引擎的加载、缓冲填充和输出流程，再评估双引擎或层间融合。')
add(f'\n- 固定输入完整 forward 三次：{", ".join(f"{v/1000:.3f}" for v in forward)} ms。')
add(f'- 33 个硬件调用耗时中位数之和：{total/1000:.3f} ms；PS 寄存器设置合计约 {statistics.median(result["quiet_register_setup_us"])/1000:.3f} ms。')
add(f'- 带软件诊断的摄像头＋预测＋预览短测：{fps:.3f} FPS，周期中位数 {timing["cycle_us"]/1000:.3f} ms。正常版本此前约 9.40 FPS；本轮诊断不是新的提速版本。')
add('- 测试没有修改网络、量化结果、正式 HLS 算子或正式 bitstream。测试结束后已恢复正式应用，短测仅预测张量约 9.402 FPS，随后暂停运行。')
add('\n## 2. 测量范围与方法')
add('使用当前已验证的 125 MHz bitstream。软件时间来自 ARM 全局定时器，按 BSP 的 `COUNTS_PER_SECOND` 换算。硬件计数器尝试因布局布线代价较高而停止，未下载到板卡，未作为结论依据。')
add('\n1. 固定输入、真实权重完整运行三次，记录每层启动到观察到完成的时间，以及寄存器设置时间。验证 35 个中间阶段、填充数据和保护区。')
add('2. 执行 19 组受控卷积，每组重复三次。输入填 1，权重为 0，bias 为 16，量化乘数为 1、右移 1；逻辑输出必须为 8，行尾填充必须为 0，保护区不变。代码没有零权重跳过机制，运算循环仍执行。')
add('3. 正常摄像头、真实权重和 UDP 开启时运行约五秒，记录完整收到的帧率；另保存最后一次完整推理的 PS 分段时间和逐层完成观察窗口。')
add('4. 对照实际代码和 HLS 综合报告的启动间隔（II）。推算项目与实测项目分开标注。')
add('\n每层时间包含该算子的读取、运算、量化、写回和完成观察，不能称为纯计算时间。PS 快照不是长期均值；三次样本和五秒短测不能代替稳定性测试。')
add('\n## 3. 当前运行架构')
add('```text\n摄像头 RGB565 416×416 → PL 采集/DMA → DDR 双缓冲\n                                      ↓\nPS 核 0：灰度、双三次缩放、INT8 输入准备\n                                      ↓\nPL：单个 48×8 算子引擎，逐层执行 → DDR 特征缓冲\n                                      ↓\nPS：预测张量和可选画面通过 UDP 发送\n                                      ↓\n上位机：解码、NMS、显示\n```')
add('\n网络输入为 1×224×224；输出为 33×7×7 和 33×14×14。INT8 乘法、INT32 累加、INT64 重量化。PL 资源为 DSP 213/220、BRAM 111/140；125 MHz 的正式实现已通过时序。')
add('\n帧间已重叠：PL 推理当前帧时，PS 准备下一帧并发送当前帧预览。层间仍通过 DDR 交接，未实现跨层流式计算。卷积内部加载与计算可重叠，输出处理与计算仍有串行部分。')
add('\n## 4. 完整帧与 PS 开销')
add('\n下表中的软件快照来自诊断短测结束前的一次完整 forward；UDP 和周期来自短测中位数。并行阶段不能相加。')
add('\n| 项目 | 耗时 ms | 口径 |\n|---|---:|---|')
for label,key,note in [('灰度转换＋水平缩放','gray_horizontal_us','PS 快照，与 PL 重叠'),('垂直缩放＋输入量化','gray_vertical_us','PS 快照，与 PL 重叠'),('启动下一次采集','camera_begin_us','含摄像头缓冲缓存清理'),('完成采集缓冲处理','camera_finish_us','主要含缓存失效处理，与 PL 重叠'),('当前帧输入排列复制','input_copy_us','PS 快照'),('输入缓存刷新','input_flush_us','PL 使用当前输入前'),('33 层寄存器设置','register_setup_us','PS 快照'),('输出失效处理与 CHW 整理','head_copy_us','PS 快照')]: add(f'| {label} | {cpu[key]/1000:.3f} | {note} |')
add(f'| 完整 forward | {timing["forward_us"]/1000:.3f} | 现场中位数，含软件与并行工作的影响 |')
add(f'| UDP 发送 | {timing["transfer_us"]/1000:.3f} | 现场中位数，预览发送与推理重叠 |')
add(f'| 完整帧周期 | {timing["cycle_us"]/1000:.3f} | 现场中位数 |')
add(f'\n真实预处理快照为 {(cpu["gray_horizontal_us"]+cpu["gray_vertical_us"])/1000:.3f} ms。状态包 `conversion_us` 中位数 {timing["reported_conversion_us"]/1000:.3f} ms 还包含采集启动和当前输入复制，不能全部称为灰度/缩放计算。')
add(f'\n短测有效状态样本 {len(stats)} 个，周期范围 {result["live_cycle_range_us"][0]/1000:.3f}～{result["live_cycle_range_us"][1]/1000:.3f} ms，错误计数为 0。摄像头等待字段接近 0 表示下一帧已在推理期间完成，不表示采集或曝光没有延迟。')
add(f'\n现场逐层快照合计 {sum(live)/1000:.3f} ms，固定输入逐层中位数合计 {total/1000:.3f} ms，差 {((sum(live)-total)/1000):.3f} ms。各层最后一次“未观察到完成”到“观察到完成”的窗口合计 {sum(poll)/1000:.3f} ms；这是完成时刻的不确定窗口，不是全部可节省的时间。该差值可能同时包含 PS 调度、内存竞争和样本差异，不能单独归因给 ARM。')
add('\n## 5. 算子类别汇总')
add('\n比例以 33 个调用中位数之和为分母，不包含寄存器设置。')
add('\n| 类别 | 调用数 | 合计 ms | 占比 |\n|---|---:|---:|---:|')
for g in groups:add(f'| {g["operator"]} | {g["count"]} | {g["us"]/1000:.3f} | {g["us"]/total*100:.2f}% |')
add(f'\n池化与分支重量化合计 {(groups[2]["us"]+groups[3]["us"])/1000:.3f} ms，占 {(groups[2]["us"]+groups[3]["us"])/total*100:.2f}%。上采样仅 0.081 ms，不是当前优化重点。')
add('\n![算子耗时概览](cost_overview.png)')
add('\n## 6. 全部逐层实测')
add('\n尺寸为逻辑尺寸，特征存储采用 CHW 和对齐行宽。`min～max` 为三次固定输入样本范围。')
add('\n| # | 层 / 调用 | 类型 | 通道 in→out | 尺寸 in→out | 中位数 ms | min～max ms | 占比 |\n|---:|---|---|---|---|---:|---:|---:|')
for r in layers:add(f'| {r["index"]+1} | {r["name"]} | {r["operator"]} | {r["ci"]}→{r["co"]} | {r["input_size"]}→{r["output_size"]} | {r["median_us"]/1000:.3f} | {r["min_us"]/1000:.3f}～{r["max_us"]/1000:.3f} | {r["share_percent"]:.2f}% |')
add('\n`cat/join/P4` 条目是分支量化尺度转换，不是简单 memcpy。部分切片和拼接通过地址偏移表达，不会形成独立硬件调用。')
add('\n## 7. 受控实验与瓶颈证据')
add('\n### 7.1 深层小特征图受准备端限制')
add(f'固定 CI=512、CO=4、3×3、stride=1：7×7 为 {probes[0]["median_us"]/1000:.3f} ms，14×14 为 {probes[3]["median_us"]/1000:.3f} ms。逻辑乘加增加四倍，时间只增加约 {(probes[3]["median_us"]/probes[0]["median_us"]-1)*100:.2f}%。两种尺寸都只有一个空间块，权重分块数相同。输入读取和输出量也增加，因此这不是单独测计算模块，但足以说明该配置没有随计算量线性增长，权重准备是强候选瓶颈。')
add('\nHLS 报告确认：计算主循环 II=1；权重填充循环 II=2。每个 3×3 权重块、每条并行 lane 包含 12×8×9=864 次填充，稳态计划约 1728 周期。512→512、7×7 卷积有 11 个输出块、64 个输入块：')
add('```text\n11 × 64 × 864 × 2 / 125 MHz ≈ 9.732 ms\n```')
add('这是依据代码循环次数和 HLS 计划推算的填充工作量，约为该层 13.653 ms 的 71%；不是硬件计数器拆项实测。它包含本地缓冲/缓存填充的计划循环，不能全部称为 DDR 等待；它可能与计算重叠，不能再与计算时间相加。')
add('\n### 7.2 首层输出处理开销明显')
add('固定 CI=1、输入 224×224、3×3、stride=2，CO=4、32、48 均只占一个 48 通道计算块，计算循环数量相同。实测分别为 3.076、6.491、8.441 ms。')
add('\nCO=4→48 的边际成本约 121.93 μs/通道。线性对照估算 CO=32 时，输出相关的可变成本约 3.90 ms，约占首层 60%。这里包含与 CO 相关的参数读入、量化、输出行处理和写回，不能把 3.90 ms 全部归为 DDR 写入。三组结果近似线性，说明增加乘法器并不能解决这部分耗时。')
add('\n### 7.3 单通道没有自动让首层快三倍')
add('固定输入尺寸、CO=32 和输出布局，CI=1、3、8 时分别为 6.491、6.500、7.054 ms。CI=1 与 3 都只需要一个 8 路输入块；当前计算循环仍展开 8 路，并对无效通道填零。单通道降低有效乘加和部分读取量，但在此架构下不会按 1/3 缩短计算周期，输出处理也不随 CI 减少。此实验使用合成权重，不是比较两套真实模型准确率。')
add('\n### 7.4 权重缓存策略有影响，但尚未精确拆出 DDR 时间')
add(f'在 28×28、CO=4、3×3 下，CI=128 为 {probes[15]["median_us"]/1000:.3f} ms，CI=136 为 {probes[16]["median_us"]/1000:.3f} ms。通道数增加 6.25%，时间增加约 {(probes[16]["median_us"]/probes[15]["median_us"]-1)*100:.1f}%；代码同时在 CI>128 时关闭 3×3 权重缓存。结果与缓存切换带来的额外读取一致，但两个因素同时变化，不能把差值直接当作精确 DDR 耗时。')
add('\n### 7.5 池化和分支重量化的结构性开销')
add('三个池化调用约 3.994、3.558、3.405 ms。输出元素数量逐级减半，但每层都有 3584 次输出行处理（128×28、256×14、512×7）。代码对每行依次执行两行读取、比较、输出，存在大量短流程和短传输。重复行控制是合理优化方向，尚未单独计量其所占百分比。')
add('\n八个分支重量化合计 8.480 ms。当前实现按 512 字节块依次读取、逐字节转换、写回。内部转换循环虽然 II=1，但每次只处理一个字节。可优先考虑矢量化或与生产者输出处理融合，必须保留模型原有两次舍入和截断语义。')
add('\n![对照实验](probe_comparison.png)')
add('\n### 7.6 全部对照实验结果')
add('\n| CI | CO | 输入边长 | stride | kernel | 三次耗时 μs | 中位数 ms |\n|---:|---:|---:|---:|---:|---|---:|')
for r in probes:add(f'| {r["ci"]} | {r["co"]} | {r["size"]} | {r["stride"]} | {r["kernel"]} | {", ".join(map(str,r["samples_us"]))} | {r["median_us"]/1000:.3f} |')
add('\n## 8. 理论吞吐与实际耗时')
add(f'\n有效乘加：{logical:,} MAC/帧。依据 48×8 分块循环计算的补齐乘加：{physical:,} MAC/帧，比有效量多 {(physical/logical-1)*100:.2f}%。')
add(f'\n384 路×125 MHz 的峰值为 48 GMAC/s；有效乘加对应理想时间 {logical/48e6:.3f} ms，考虑通道补齐后的循环工作量对应 {physical/48e6:.3f} ms。它们都没有计入加载、流水启动/排空、量化、控制和输出处理。')
add(f'\n按固定输入完整 forward 中位数计算，平均有效吞吐约 {logical/statistics.median(forward)/1000:.3f} GMAC/s，约为峰值的 {logical/statistics.median(forward)/1000/48*100:.2f}%。这不是实测 DSP 活动率，也不能把其余部分全部称为 DDR 等待。')
add('\n## 9. 下一步优化顺序')
add('\n| 优先级 | 方向 | 依据 | 验收方式 |\n|---|---|---|---|')
add('| 1 | 权重填充与本地缓存访问，检查 II=2 的端口/依赖/布局限制 | 深层尺寸扩大四倍而时间几乎不变；9.73 ms 填充计划量 | 保持现有阵列，先改一个加载循环；检查 HLS II、固定输出和逐层耗时 |')
add('| 2 | 输入块准备与输出行流程；减少串行拆包、短调用和短 burst | 首层 CO 对照显示约 3.90 ms 输出相关成本；1×1 合计 17.51 ms | 同样的受控探针和完整模型黄金比较 |')
add('| 3 | 池化连续读写、分支重量化并行化或局部融合 | 两类合计 19.44 ms，主要不是大规模乘加 | 保留数值语义、检查 BRAM/DSP/时序，再上板计时 |')
add('| 4 | 缩小阵列、双引擎、跨层 BRAM 流式交接 | 可能改善利用率，但会增加控制、量化和缓冲资源 | 先验证一对层；不能仅按理论峰值或总 DSP 数判断 |')
add('\n达到 10 FPS 需要将约 106.3 ms 的帧周期减少约 6.3 ms。按固定工作量推算，BasicConv3 和 headP5.conv1 的权重填充计划合计约 14.60 ms；II=2→1 会减半其稳态计划量，但不会保证整网直接少 7.30 ms，因为读取、计算与填充有重叠。应将其作为验证目标，不作为已实现的提速。')
add('\n## 10. 未测项目与交付文件')
add('\n尚未获得真实硬件的加载/计算/写回独立周期、DDR 控制器流量和 DSP 实际活动率。本报告没有给出伪精确的 DDR 占比。摄像头曝光、缓冲帧龄、PC 解码/NMS/显示和完整端到端延迟也不在本次计时范围。长时间稳定性测试未恢复。')
add('\n- `consumption_report.md`：本报告。\n- `layers.csv`：全部层的三次样本范围、快照、逻辑/补齐 MAC。\n- `probes.csv`：19 组受控实验。\n- `results.json`：原始统计、口径与输出 SHA-256。\n- `cost_overview.png`、`probe_comparison.png`：实测图。')
add('\n有效诊断测试源码在 `temporary/bottleneck_test/`，生成文件在其 `build/` 中；正式代码未修改。报告和构建产物未提交 Git。已停止的硬件计数器实验目录 `temporary/counter_test/` 暂时保留：自动审批拒绝清理命令，提示命令被策略阻止。该实验未下载到板卡，也不作为本报告测量依据。')
add('\n### 依据文件')
add('`hardware/hls/src/std_conv.cpp`、`maxpool.cpp`、`top.cpp`、`camera/int8/live_main.cpp`，以及 `hardware/hls/build/conv/hls/syn/report/` 下 compute、load_weight_lane、store_output、std_conv 的综合报告。')
(build/'consumption_report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
# Scientific plots use the recorded measurements, not inferred phase times.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams['font.family']=font.get_name();plt.rcParams['axes.unicode_minus']=False
fig,axes=plt.subplots(1,2,figsize=(13,6),gridspec_kw={'width_ratios':[1.4,1]});fig.patch.set_facecolor('#f7f9fc')
top=sorted(layers,key=lambda r:r['median_us'],reverse=True)[:10][::-1]
axes[0].barh([r['name'] for r in top],[r['median_us']/1000 for r in top],color='#0078d4')
axes[0].set_title('耗时最高的 10 个调用',fontproperties=font);axes[0].set_xlabel('ms / frame')
for i,r in enumerate(top):axes[0].text(r['median_us']/1000+.15,i,f'{r["median_us"]/1000:.3f}',va='center',fontsize=9)
axes[0].set_xlim(0,16)
axes[1].barh([g['operator'] for g in groups][::-1],[g['us']/1000 for g in groups][::-1],color=['#9b9b9b','#8764b8','#00a36c','#56a8e9','#0078d4'])
axes[1].set_title('算子类别合计',fontproperties=font);axes[1].set_xlabel('ms / frame');axes[1].set_xlim(0,80)
for i,g in enumerate(groups[::-1]):axes[1].text(g['us']/1000+.8,i,f'{g["us"]/1000:.3f}  ({g["us"]/total*100:.1f}%)',va='center',fontsize=9)
for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
fig.suptitle('固定输入，真实权重，125 MHz；每层三次取中位数',fontproperties=font,fontsize=12)
fig.tight_layout();fig.savefig(build/'cost_overview.png',dpi=160);plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,5))
axes[0].plot([4,32,48],[3.076,6.491,8.441],marker='o',color='#0078d4');axes[0].set_title('首层：计算块相同，增加输出通道',fontproperties=font);axes[0].set_xlabel('Output channels');axes[0].set_ylabel('ms')
for x,y in zip([4,32,48],[3.076,6.491,8.441]):axes[0].annotate(f'{y:.3f}',(x,y),xytext=(5,6),textcoords='offset points')
deep_times=[probes[0]['median_us']/1000,probes[3]['median_us']/1000]
axes[1].bar(['7×7','14×14'],deep_times,color=['#0078d4','#00a36c']);axes[1].set_title('CI=512, CO=4：乘加量增加四倍',fontproperties=font);axes[1].set_ylabel('ms');axes[1].set_ylim(0,1.5)
for i,y in enumerate(deep_times):axes[1].text(i,y+.03,f'{y:.3f}',ha='center')
for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15);ax.set_axisbelow(True)
fig.suptitle('受控上板实验：零权重、非零 bias，输出与保护区验证通过',fontproperties=font,fontsize=11)
fig.tight_layout();fig.savefig(build/'probe_comparison.png',dpi=160);plt.close(fig)
print(json.dumps({'quiet_us':forward,'operator_sum_us':total,'fps':fps,'live_timing':timing,'cpu':cpu,'report':str(build/'consumption_report.md')},ensure_ascii=False,indent=2))
