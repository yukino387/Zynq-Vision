import hashlib
import json
import re
import statistics
from pathlib import Path

build = Path(__file__).resolve().parent / 'build'
result = json.loads((build / 'comparison.json').read_text(encoding='utf-8'))
hardware = build / 'system_bram/build'
assert result['golden_verified'] and result['exhaustive_byte_checks'] == 4096
assert result['baseline_network']['errors'] == result['candidate_network']['errors'] == 0
assert hashlib.sha256((hardware / 'system_wrapper.bit').read_bytes()).digest() == hashlib.sha256(
    (build.parents[2] / 'hardware/camera/build/system_wrapper.bit').read_bytes()).digest()
reload_status = json.loads((build / 'formal_reload_status.json').read_text())
assert reload_status[3] & 1 == 0 and reload_status[10] == 0
timing = (hardware / 'timing.rpt').read_text()
assert 'All user specified timing constraints are met.' in timing
assert 'VIOLATED' not in (hardware / 'bus_skew.rpt').read_text()

def resource(path, label):
    match = re.search(r'\|\s*' + re.escape(label) + r'\s*\|\s*([\d.]+)\s*\|', path.read_text())
    assert match, label
    return match.group(1)

old_us = statistics.median(result['baseline_forward_us'])
new_us = statistics.median(result['candidate_forward_us'])
before = result['baseline_network']
after = result['candidate_network']
lines = ['# 分支重量化优化结果', '', '日期：2026-10-13。Zynq-7020，INT8 灰度 224×224 模型，125 MHz。', '',
         '## 结果', '', '| 项目 | 上一版 | 新版 |', '|---|---:|---:|',
         f'| 固定输入完整推理 | {old_us/1000:.3f} ms | {new_us/1000:.3f} ms |',
         f'| 八次分支重量化合计 | {result["requant_baseline_us"]/1000:.3f} ms | {result["requant_candidate_us"]/1000:.3f} ms |',
         f'| 摄像头＋预测＋预览周期中位数 | {before["cycle_median_us"]/1000:.3f} ms | {after["cycle_median_us"]/1000:.3f} ms |',
         f'| 完整接收帧率 | {before["received_fps"]:.3f} FPS | {after["received_fps"]:.3f} FPS |', '',
         f'固定输入整网减少 {(old_us-new_us)/1000:.3f} ms；同软件短测吞吐变化 {(after["received_fps"]/before["received_fps"]-1)*100:.2f}%。', '',
         '## 修改', '', '本轮修改 top.cpp 的 kernel=5 分支：每次调用用原 requant 函数生成 256 项结果表，复制为八个读银行；每周期并行转换一个 64 位字并写回。先缓存输入块，再写输出，保持原地转换行为。', '',
         '查表按输入的原始字节索引，建表时将其解释为有符号 INT8。乘法、舍入、负数和 [-127,127] 截断均沿用原规则；没有合并生产者与分支的两次量化。网络、权重、PS 应用和摄像头配置保持原样。', '',
         '表使用 BRAM。初版 LUTRAM 的布局布线拥塞较重，未加载到板卡，改用 BRAM 后重新验收。实现按实际 125 MHz 约束，并限制四个线程；这一构建设置已同步到正式 build.tcl，HLS 仍以 7 ns 综合。实际运行频率始终为 125 MHz。', '',
         '本轮正式源码修改：hardware/hls/src/top.cpp、hardware/camera/build.tcl。上一轮 std_conv.cpp 的权重加载优化继续保留。新增测试仅在 temporary/requant_test：board.cpp、build_board.ps1、build_hls.ps1、build_hardware.ps1、run_board.tcl、measure_udp.py、compare.py、report.py。', '',
         '## 资源', '', '| 项目 | 上一版 | 新版 |', '|---|---:|---:|']
for label in ['DSPs', 'Block RAM Tile', 'Slice LUTs', 'Slice Registers']:
    lines.append(f'| {label} | {resource(build/"baseline/utilization.rpt", label)} | {resource(hardware/"utilization.rpt", label)} |')
lines += ['', '全部时序及摄像头 FIFO bus-skew 检查通过。', '', '## 验证', '',
          '- 固定输入、真实权重完整运行三次；35 个中间阶段、两个检测输出、行尾填充和保护区与原版一致。',
          '- 八组真实重量化参数，分别覆盖 256 种输入字节值，并测试分离输入输出及原地写回。结果与独立 ARM 整数计算一致。',
          '- 正式应用 ELF 保持不变；摄像头、两个预测张量与 RGB565 预览共同运行约五秒。测试错误计数为零。',
          '- 长时间稳定性测试保持暂停；短测 FPS 不是长期稳定性保证。', '', '## 全部重量化调用', '',
          '| 调用 | 上一版 ms | 新版 ms | 节省 ms |', '|---|---:|---:|---:|']
for row in result['layers']:
    if row['kernel'] == 5:
        lines.append(f'| {row["layer"]} | {row["baseline_us"]/1000:.3f} | {row["candidate_us"]/1000:.3f} | {row["saved_us"]/1000:.3f} |')
digest = hashlib.sha256((hardware / 'system_wrapper.bit').read_bytes()).hexdigest().upper()
lines += ['', '## 交付', '',
          'comparison.csv：全部 33 个硬件调用的新旧耗时。comparison.json：统计结果。board/result.log、baseline_udp_results.json、short_udp_results.json：原始依据。', '',
          f'新版 bitstream SHA-256：{digest}。', '',
          '通过验证的硬件更新至 hardware/camera/build 和 HLS IP 目录，使用现有 Vitis 加载入口。原版硬件保存在本测试目录 build/baseline。报告和生成产物留在临时 build 目录，未提交 Git。', '',
          '下一步优先优化池化的连续读取和写回，之后检查小特征图卷积的输入搬运与输出处理。']
(build / 'optimization_report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(build / 'optimization_report.md')
