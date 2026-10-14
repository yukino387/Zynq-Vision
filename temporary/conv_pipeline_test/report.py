"""Report a qualified clean pipeline candidate after board/live validation."""
import hashlib
import json
import re
import statistics
from pathlib import Path

build = Path(__file__).resolve().parent / 'build'
root = build.parents[2]
hardware = build / 'system_candidate/build'
result = json.loads((build / 'comparison.json').read_text(encoding='utf-8'))
assert result['golden_verified'] and result['pool_cases_verified'] == 6
assert result['baseline_network']['errors'] == result['candidate_network']['errors'] == 0
timing = (hardware / 'timing.rpt').read_text(encoding='utf-8')
assert 'All user specified timing constraints are met.' in timing
assert 'VIOLATED' not in (hardware / 'bus_skew.rpt').read_text(encoding='utf-8')
digest = hashlib.sha256((hardware / 'system_wrapper.bit').read_bytes()).hexdigest().upper()
assert digest == hashlib.sha256((root / 'hardware/camera/build/system_wrapper.bit').read_bytes()).hexdigest().upper()
status = json.loads((build / 'formal_reload_status.json').read_text(encoding='utf-8'))
assert status[3] & 1 == 0 and status[10] == 0

def resource(path, label):
    match = re.search(r'\|\s*' + re.escape(label) + r'\s*\|\s*([\d.]+)\s*\|', path.read_text(encoding='utf-8'))
    assert match, label
    return match.group(1)

old = statistics.median(result['baseline_forward_us'])
new = statistics.median(result['candidate_forward_us'])
before, after = result['baseline_network'], result['candidate_network']
lines = ['# 卷积输出流水化实测', '', '日期：2026-10-14。Zynq-7020，signed INT8 灰度 224×224，125 MHz。', '',
         '| 项目 | 基线 | 正式候选 |', '|---|---:|---:|',
         f'| 固定输入完整推理 | {old/1000:.3f} ms | {new/1000:.3f} ms |',
         f'| 摄像头、预测、预览周期中位数 | {before["cycle_median_us"]/1000:.3f} ms | {after["cycle_median_us"]/1000:.3f} ms |',
         f'| 上位机完整接收帧率 | {before["received_fps"]:.3f} FPS | {after["received_fps"]:.3f} FPS |', '',
         f'固定推理减少 {(old-new)/1000:.3f} ms（{(old-new)/old*100:.2f}%）；端到端短测吞吐增加 {(after["received_fps"]/before["received_fps"]-1)*100:.2f}%。', '',
         'UDP 基线引用上一阶段保存的同一正式 ELF 短测，并非同时采集；两次均开启摄像头、预测与预览。短测帧率存在波动，不等同于长期稳定性结论。', '',
         '## 修改', '',
         '正式计算源码仅修改 hardware/hls/src/std_conv.cpp。量化、64 位打包与四路 AXI 写回通过 FIFO 和 HLS DATAFLOW 重叠。7×7、14×14 输出按通道连续写，大图按 tile 行写，保持 CHW、padding、整数舍入/饱和、激活和地址布局。FIFO 使用 SRL。每组四通道参数在像素循环前锁存。', '',
         '这是同一次卷积输出阶段流水化，计算与输出 tile 仍顺序执行；没有跨网络层 streaming，也没有新增 MAC 引擎或修改 PS/模型/摄像头。构建最大 16 线程，同一时间一个重型构建。', '',
         '## 正确性', '',
         '早期约 71.6 ms 候选存在通道组首像素量化错误，不属于交付成果。修正后的诊断版本通过 35 阶段和两个输出，三次推理中位数 71.680 ms。21 层正常/关闭输出配对测试只用于归因：关闭输出通路仍包含输入、权重、计算与调度，不等于纯 MAC。', '',
         '移除诊断开关后的独立正式候选再经过三次真实权重黄金输出、padding、保护区检查；复用的六项池化测试通过。正式固件短测约五秒，完整接收两张量及 RGB565 预览，错误为零。长期稳定性测试仍暂停。', '',
         '## 实现资源', '', '| 项目 | 基线 | 正式候选 |', '|---|---:|---:|']
for label in ('DSPs', 'Block RAM Tile', 'Slice LUTs', 'Slice Registers'):
    lines.append(f'| {label} | {resource(build/"baseline/utilization.rpt", label)} | {resource(hardware/"utilization.rpt", label)} |')
lines += ['', '125 MHz setup/hold、pulse width 和摄像头 FIFO bus-skew 检查通过。资源以最终实现为准，BRAM 单位为 Tile。', '',
          '## 逐层计时', '', '| 调用 | 基线 ms | 正式候选 ms | 节省 ms |', '|---|---:|---:|---:|']
for row in result['layers']:
    lines.append(f'| {row["layer"]} | {row["baseline_us"]/1000:.3f} | {row["candidate_us"]/1000:.3f} | {row["saved_us"]/1000:.3f} |')
lines += ['', '## 证据与恢复', '',
          'comparison.json/csv 为 33 次调用对照；board/result.log 与输出 binary 为独立正式候选测试；profile_results.json、layer_profile.csv 与 board_profile/ 为诊断测试；short_udp_results.json 为端到端短测。', '',
          'build/baseline/ 保留 81.088 ms 硬件与实现报告。正式 bit/XSA/DCP/报告和 HLS IP 已更新，使用 vitis_live/run_live.tcl 重新加载核验后板卡暂停。', '',
          f'正式 bitstream SHA-256：{digest}。', '',
          'BasicConv3 的剩余时间主要在输入/权重/计算通路；小特征图和 loader 优化留作下一项，不包含在此次修改中。']
(build / 'optimization_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(build / 'optimization_report.md')
