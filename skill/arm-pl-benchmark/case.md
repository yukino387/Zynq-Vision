# 来源、失败观察与验证效果

来源：2026-10-27 ARM/PL 对照及同日离线文档核查。附带 [原始 CSV](../evidence/raw_trials.csv)、[运行元数据](../evidence/benchmark_meta.json)、[报告摘录](../evidence/benchmark_report_excerpt.txt) 和 [复核记录](../evidence/review_excerpt.txt)，源文件身份见 sources.json。

观察：原分析中 headline 的点估计与区间所对应估计量需要分开；把 NEON 微内核换算写成整网实测会夸大证据。逐层中位数求和也不能冒充整网中位数。

提炼：明确计时边界，分别计算逐输入等权与合并估计，微内核外推单列。本包新脚本不沿用旧 summary.json 里 headline 的混合字段。

历史主阶段为三输入，各 12 轮；每输入 ARM 12 次、PL 204 次，总计 ARM 36、PL 612 次。等权时延约 12013.944926 / 56.590492 ms，比值约 212.30；合并中位比约 212.29。这里是 ARM O3 标量对 PL 的无采集显示固定输入结果，不是 NEON 整网、生产 FPS 或当前板卡状态。

2026-11-04 用附带 CSV 实际运行本包脚本离线复算；结果在 validation.json，对真实数据的复算不等于新上板试验。CSV 的相同 SHA 仅是当时输出记录，包中不含输出张量，不能独立重验数值正确性；本包也未重建试验固件。
