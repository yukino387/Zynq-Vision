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
board = build / 'board_profile'
baseline = json.loads((build / 'baseline/comparison.json').read_text(encoding='utf-8'))
golden = json.loads((root / 'temporary/bottleneck_test/build/results.json').read_text(encoding='utf-8'))
log = (board / 'result.log').read_text(encoding='utf-8')
assert 'PASS:' in log and 'TEST ERROR' not in log
assert re.search(r'test_errors\s*=\s*test_errors\s*:\s*0\b', log)
for name, count in [('out0', 1617), ('out1', 6468)]:
    assert hashlib.sha256((board / f'{name}.bin').read_bytes()[:count]).hexdigest() == golden['heads_sha256'][name]
values = struct.unpack('<198I', (board / 'profile_us.bin').read_bytes())
layer_values = struct.unpack('<99I', (board / 'all_layer_us.bin').read_bytes())
commands = struct.unpack('<330i', (root / 'temporary/int8_rebuild_test/build/metadata.bin').read_bytes()[:1320])
rows = []
for layer, info in enumerate(baseline['layers']):
    if commands[layer * 10 + 8] not in (1, 3):
        continue
    normal, compute = [statistics.median(values[layer * 6 + run * 2 + mode] for run in range(3)) for mode in range(2)]
    in_network = statistics.median(layer_values[run * 33 + layer] for run in range(3))
    rows.append(dict(layer=info['layer'], ci=commands[layer * 10 + 4], co=commands[layer * 10 + 5],
                     size=commands[layer * 10 + 6], kernel=commands[layer * 10 + 8],
                     baseline_in_network_us=info['candidate_us'], pipeline_in_network_us=in_network,
                     in_network_saved_us=info['candidate_us']-in_network,
                     pipeline_paired_normal_us=normal, compute_path_us=compute,
                     pipeline_output_delta_us=normal-compute))
assert len(rows) == 21
forward = [int(x) for x in re.search(r'FORWARD_US = (.*)', log).group(1).split()]
summary = dict(baseline_full_forward_us=baseline['candidate_forward_us'], pipeline_profile_forward_us=forward,
               sums={key: sum(row[key] for row in rows) for key in ['in_network_saved_us', 'compute_path_us',
                     'pipeline_output_delta_us']}, golden_verified=True, no_output_unchanged=True, layers=rows)
(build / 'profile_results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
with (build / 'layer_profile.csv').open('w', encoding='utf-8-sig', newline='') as output:
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
lines = ['# 卷积输出流水线及配对 profiling', '',
         '轻量诊断硬件使用已实现的 FIFO 输出流水线，以 act 高位选择正常或关闭输出。诊断开关只存在于临时源代码，待发布候选没有此开关。', '',
         '正常模式先运行三次真实权重完整推理，验证 35 个阶段、两个预测张量、padding 和保护区；21 个卷积层各测三次正常与关闭输出模式，关闭输出时验证输出内存保持不变。', '',
         f'完整推理中位数：正式基线 {statistics.median(summary["baseline_full_forward_us"])/1000:.3f} ms；流水线诊断版本 {statistics.median(forward)/1000:.3f} ms。', '',
         '计算通路包含偏置初始化、输入与权重搬运、MAC 和调度，不能解释为纯 MAC 时间。输出差分只测量优化后流水线中的量化、打包、写回及控制开销；优化前后整网数据来自两个硬件版本，不能把版本差异解释为逐周期输出计数。配对调用可能更新后续层输入数据，但循环、权重和尺寸保持相同；完整数值正确性在诊断前验证。', '',
         '| 层 | 基线整网内 ms | 流水线整网内 ms | 节省 ms | 配对计算通路 ms | 流水线输出差分 ms |',
         '|---|---:|---:|---:|---:|---:|']
for row in rows:
    lines.append(f'| {row["layer"]} | {row["baseline_in_network_us"]/1000:.3f} | {row["pipeline_in_network_us"]/1000:.3f} | {row["in_network_saved_us"]/1000:.3f} | {row["compute_path_us"]/1000:.3f} | {row["pipeline_output_delta_us"]/1000:.3f} |')
lines += ['', '合计：' + json.dumps(summary['sums'], ensure_ascii=False) + '（单位 µs）。', '',
          '原始计时：board_profile/profile_us.bin。详细统计：profile_results.json、layer_profile.csv。三路诊断原型因布线持续拥塞取消，未上板，也没有用于性能结论。']
(build / 'profiling_report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print(json.dumps({key: value for key, value in summary.items() if key != 'layers'}, ensure_ascii=False, indent=2))
print('Largest remaining compute paths:', sorted(rows, key=lambda row: row['compute_path_us'], reverse=True)[:5])
