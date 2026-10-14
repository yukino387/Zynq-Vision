import csv
import hashlib
import json
import re
import statistics
import struct
from pathlib import Path

test = Path(__file__).resolve().parent
root = test.parents[1]
build = test / 'build'
board = build / 'board'
baseline = json.loads((build / 'baseline/comparison.json').read_text(encoding='utf-8'))
golden = json.loads((root / 'temporary/bottleneck_test/build/results.json').read_text(encoding='utf-8'))
log = (board / 'result.log').read_text(encoding='utf-8')
assert 'PASS:' in log and 'TEST ERROR' not in log
assert re.search(r'test_errors\s*=\s*test_errors\s*:\s*0\b', log)
for name, count in [('out0', 1617), ('out1', 6468)]:
    assert hashlib.sha256((board / f'{name}.bin').read_bytes()[:count]).hexdigest() == golden['heads_sha256'][name]
values = struct.unpack('<297I', (board / 'profile_us.bin').read_bytes())
commands = struct.unpack('<330i', (root / 'temporary/int8_rebuild_test/build/metadata.bin').read_bytes()[:1320])
rows = []
for layer, info in enumerate(baseline['layers']):
    if commands[layer * 10 + 8] not in (1, 3):
        continue
    normal, raw, compute = [statistics.median(values[layer * 9 + run * 3 + mode] for run in range(3)) for mode in range(3)]
    rows.append(dict(layer=info['layer'], ci=commands[layer * 10 + 4], co=commands[layer * 10 + 5],
                     size=commands[layer * 10 + 6], kernel=commands[layer * 10 + 8],
                     baseline_us=info['candidate_us'], normal_us=normal, raw_output_us=raw,
                     compute_path_us=compute, output_total_delta_us=normal-compute,
                     requant_delta_us=normal-raw, packed_write_delta_us=raw-compute))
assert len(rows) == 21
forward = [int(x) for x in re.search(r'FORWARD_US = (.*)', log).group(1).split()]
summary = dict(baseline_full_forward_us=baseline['candidate_forward_us'], profile_full_forward_us=forward,
               sums={key: sum(row[key] for row in rows) for key in ['normal_us', 'compute_path_us',
                     'output_total_delta_us', 'requant_delta_us', 'packed_write_delta_us']},
               golden_verified=True, no_output_unchanged=True, layers=rows)
(build / 'results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
with (build / 'layer_profile.csv').open('w', encoding='utf-8-sig', newline='') as output:
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
lines = ['# 卷积输出差分 profiling', '',
         '临时诊断硬件保留同一卷积计算通路，用 act 高位选择正常、原始累加值低字节输出或关闭输出。正式算子没有这些诊断分支。', '',
         '正常模式先运行三次真实权重完整推理，验证 35 个阶段、两个预测张量、padding 和保护区；21 个卷积层各测三次三种模式，关闭输出时验证输出内存保持不变。', '',
         f'完整推理中位数：正式基线 {statistics.median(summary["baseline_full_forward_us"])/1000:.3f} ms；诊断硬件正常模式 {statistics.median(forward)/1000:.3f} ms。', '',
         '计算通路包含偏置初始化、输入与权重搬运、MAC 和调度，不能解释为纯 MAC 时间。差分包括对应路径的控制开销和 DDR 竞争变化，作为优化方向依据，不是逐周期独立计数。配对测试中各层的输入数据可能已由前面的诊断调用更新；循环次数、权重及尺寸相同，完整正确性由诊断前的三次整网运行验证。', '',
         '| 层 | 正常 ms | 计算通路 ms | 输出差分 ms | 量化差分 ms | 读出/打包/写回差分 ms |',
         '|---|---:|---:|---:|---:|---:|']
for row in rows:
    lines.append(f'| {row["layer"]} | {row["normal_us"]/1000:.3f} | {row["compute_path_us"]/1000:.3f} | {row["output_total_delta_us"]/1000:.3f} | {row["requant_delta_us"]/1000:.3f} | {row["packed_write_delta_us"]/1000:.3f} |')
lines += ['', '合计：' + json.dumps(summary['sums'], ensure_ascii=False) + '（单位 µs）。', '',
          '原始计时：board/profile_us.bin。详细统计：results.json、layer_profile.csv。']
(build / 'profiling_report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(json.dumps({key: value for key, value in summary.items() if key != 'layers'}, ensure_ascii=False, indent=2))
print('Largest output deltas:', sorted(rows, key=lambda row: row['output_total_delta_us'], reverse=True)[:5])
