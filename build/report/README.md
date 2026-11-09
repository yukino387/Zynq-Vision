# 综合与实现报告

本目录是提交给评测的「综合与实现报告」原件，不是摘要：所有数值可直接在对应文件中核对。

| 文件 | 内容 | 生成工具与时间 |
|---|---|---|
| [utilization.rpt](utilization.rpt) | 资源占用（LUT / FF / BRAM / DSP） | Vivado 2026.1，2026-10-26 21:36:58，Routed |
| [timing.rpt](timing.rpt) | 时序摘要（WNS / WHS / 失败端点） | Vivado 2026.1，2026-10-26 21:37:03，Routed |
| [clocks.rpt](clocks.rpt) | 时钟定义与周期（125 MHz / 100 MHz / 显示时钟） | Vivado 2026.1，2026-10-26 21:36:57 |
| [bus_skew.rpt](bus_skew.rpt) | 总线偏斜检查 | Vivado 2026.1，2026-10-26 |
| [hls_conv_csynth.rpt](hls_conv_csynth.rpt) | HLS 顶层 `conv` 综合报告（延迟、II、资源估计） | Vitis HLS 2026.1 |

## 关键结论

- 器件 `xc7z020clg400-2`，设计状态 Routed，顶层 `system_wrapper`。
- 主时钟 `clk_fpga_0` = 8.000 ns（125 MHz）；`clk_fpga_1` = 10.000 ns（100 MHz）；
  显示像素时钟 32.323 ns（≈30.94 MHz），TMDS 串行时钟 6.465 ns（≈154.69 MHz）。
- WNS +0.045 ns、WHS +0.050 ns，失败端点 0；DSP 217/220（98.64%），LUT 45,289/53,200（85.13%）。
- 资源接近上限是设计约束的直接结果：列并行为 DSP 上限下的取舍，不是「堆资源换性能」。

## 口径与限制

- 报告是 **Routed 实现**结果，不是板上实时采样；板级状态需现场确认。
- 时序数值通过，但 I/O 约束并非完整签核（`no_input_delay` / `no_output_delay` 端点仍存在），
  因此不宣称「所有接口已完全签核」。
- 报告中的 `Command` / 路径字段保留了原始构建机的绝对路径，属于工具输出原文，未做改写。
- HLS 报告里的资源是**估计值**，与上面的 Vivado 实现值不是同一口径，不能互相替代。

## 如何重新生成

```powershell
# HLS：hardware/hls/build.ps1 → hardware/hls/build/conv/hls/syn/report/
# 实现：hardware/camera/build.ps1 → hardware/camera/build/terminal/
```

重新生成后，把新报告覆盖到本目录，并同步更新上表的日期。
