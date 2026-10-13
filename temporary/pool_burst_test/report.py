import hashlib
import json
import re
import statistics
from pathlib import Path

build = Path(__file__).resolve().parent / 'build'
result = json.loads((build / 'comparison.json').read_text(encoding='utf-8'))
hardware = build / 'system_bram/build'
assert result['golden_verified'] and result['pool_cases_verified'] == 6
assert result['baseline_network']['errors'] == result['candidate_network']['errors'] == 0
assert 'All user specified timing constraints are met.' in (hardware / 'timing.rpt').read_text()
assert 'VIOLATED' not in (hardware / 'bus_skew.rpt').read_text()
digest = hashlib.sha256((hardware / 'system_wrapper.bit').read_bytes()).hexdigest().upper()
assert digest == hashlib.sha256((build.parents[2] / 'hardware/camera/build/system_wrapper.bit').read_bytes()).hexdigest().upper()
reload_status = json.loads((build / 'formal_reload_status.json').read_text())
assert reload_status[3] & 1 == 0 and reload_status[10] == 0

def resource(path, label):
    match = re.search(r'\|\s*' + re.escape(label) + r'\s*\|\s*([\d.]+)\s*\|', path.read_text())
    assert match, label
    return match.group(1)

before = result['baseline_network']
after = result['candidate_network']
old_us = statistics.median(result['baseline_forward_us'])
new_us = statistics.median(result['candidate_forward_us'])
lines = ['# MaxPool 连续搬运优化结果', '',
         '日期：2026-10-13。Zynq-7020，INT8 灰度 224×224，125 MHz。', '',
         '| 项目 | 上一版 | 新版 |', '|---|---:|---:|',
         f'| 固定输入完整推理 | {old_us/1000:.3f} ms | {new_us/1000:.3f} ms |',
         f'| 三次池化合计 | {result["pool_baseline_us"]/1000:.3f} ms | {result["pool_candidate_us"]/1000:.3f} ms |',
         f'| 摄像头＋预测＋预览周期中位数 | {before["cycle_median_us"]/1000:.3f} ms | {after["cycle_median_us"]/1000:.3f} ms |',
         f'| 完整接收帧率 | {before["received_fps"]:.3f} FPS | {after["received_fps"]:.3f} FPS |', '',
         f'整网减少 {(old_us-new_us)/1000:.3f} ms；同软件短测接收吞吐变化 {(after["received_fps"]/before["received_fps"]-1)*100:.2f}%。', '',
         '## 修改范围', '',
         '正式源码仅修改 hardware/hls/src/maxpool.cpp。每个通道连续读取到小缓冲，保持每周期八个 INT8 输出的 2×2 signed max 比较，再连续写回整个通道。新增原始缓冲 448 个 64 位字及结果缓冲 112 个 64 位字，总计 4480 字节。输入缓冲分成两个双端口 BRAM 银行。通道地址用递增偏移，比较阶段使用一维连续循环，避免 HLS 自动合并二维循环时的计数乘法额外占用 DSP。', '',
         '支持当前模型实际使用的 56×56、28×28、14×14 池化输入；缓冲上限固定为 56×56 对应的带行尾填充布局。输出填充仍为零，保持 CHW、各特征偏移和三个池化调用。没有增加跨层流水线，读取、比较、写回仍按通道顺序执行。收益来源是合并短段访问。', '',
         '卷积、分支量化、网络、权重、PS 应用和摄像头配置沿用上一版。HLS 以 7 ns 综合，实际运行和实现检查均为 125 MHz。只运行一个硬件构建，Vivado 限制四个线程。', '',
         '## 资源', '', '| 项目 | 上一版 | 新版 |', '|---|---:|---:|']
for label in ['DSPs', 'Block RAM Tile', 'Slice LUTs', 'Slice Registers']:
    lines.append(f'| {label} | {resource(build/"baseline/utilization.rpt", label)} | {resource(hardware/"utilization.rpt", label)} |')
lines += ['', '全部时序和摄像头 FIFO bus-skew 检查通过。', '',
          '## 测试', '',
          '- 固定输入、真实权重完整运行三次；35 个中间阶段、两个检测输出、行尾填充和保护区均与原版一致。',
          '- 三种实际池化尺寸，各使用三个通道的固定 signed INT8 输入，分别测试独立输出和原地缩小写回；包含正负数、通道边界和故意填为 127 的输入 padding。所有有效输出、零 padding、保护区和独立模式的输入不变性均由 ARM 独立参考检查通过。',
          '- 同一正式应用 ELF，摄像头、两个预测张量及 RGB565 预览共同运行约五秒，错误为零。该结果属于短测，长时间稳定性测试仍暂停。',
          '- 通过现有 vitis_live/run_live.tcl 再次下载已更新的正式硬件和应用；UDP 确认错误为零，板卡已暂停。', '',
          '## 每次池化', '', '| 调用 | 上一版 ms | 新版 ms | 节省 ms |', '|---|---:|---:|---:|']
for row in result['layers']:
    if row['kernel'] == 2:
        lines.append(f'| {row["layer"]} | {row["baseline_us"]/1000:.3f} | {row["candidate_us"]/1000:.3f} | {row["saved_us"]/1000:.3f} |')
lines += ['', '## 交付', '',
          '测试独立位于 temporary/pool_burst_test：board.cpp、build_board.ps1、build_hls.ps1、build_hardware.ps1、run_board.tcl、measure_udp.py、compare.py、report.py。', '',
          '全部 33 次硬件调用的新旧耗时见 comparison.csv，汇总见 comparison.json，原始数据见 board/result.log、baseline_udp_results.json、short_udp_results.json。测试和报告未提交 Git。', '',
          f'正式 bitstream SHA-256：{digest}。', '',
          '验证后的 bit、XSA、DCP、报告及 HLS IP 已更新至现有 hardware 构建目录。上一版硬件和 maxpool.cpp 备份位于本测试的 build/baseline。', '',
          '下一步优先检查卷积输出的量化、打包与写回重叠，暂不扩大为 Conv-Pool 融合或双引擎。']
(build / 'optimization_report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(build / 'optimization_report.md')
