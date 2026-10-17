---
name: fpga-engineering-tools
description: 使用只读 Python 工具汇总 FPGA 工程 Git 状态、构建日志、Vivado/HLS 报告及逐层性能对照，减少重复查询和大日志上下文。适用于 FPGA 工程状态恢复、构建检查和性能诊断；不负责自动综合、下载、修改硬件或上板控制。
---

# FPGA 工程精简诊断工具

先运行脚本获得摘要，再有针对性地读取异常证据。不要默认加载整个历史、源代码、报告或日志。

## 入口

以本 skill 的目录定位 `scripts/inspect.py`，使用可用的 Python 3。所有脚本只读，不启动厂商构建、网络会话或板卡操作。路径显式提供，不依赖 shell 当前目录；不要猜测工程或自动递归搜遍磁盘。

```text
python <skill-dir>/scripts/inspect.py status --root <repo> --log <current-log> --artifact <bit-or-elf>
python <skill-dir>/scripts/inspect.py build --timing <timing.rpt> --utilization <utilization.rpt> --bus-skew <bus_skew.rpt> --hls <top_csynth.xml> --hls <selected_pipeline_csynth.xml>
python <skill-dir>/scripts/inspect.py perf --comparison <comparison.json>
python <skill-dir>/scripts/verify_tensor.py --reference <golden.bin> --actual <out.bin> --dtype int8 --count <elements>
```

可选参数只传当前任务需要的文件。`status` 默认列最多 12 项 Git 差异及日志尾部关键事件，`perf` 默认返回最慢 5 层、收益最大和回退最大各 3 层；输出是短 JSON。不传文件的指标保持缺失，解析不到的指标报告 unknown，不把它当作零或通过。用 `--limit` 调整列表上限，最大 20。大日志只读末尾 64 KiB；摘要注明范围，不能据此保证整个构建无错误。

## 判断边界

- 产物存在/新旧时间、最后日志事件，不证明进程仍在运行或板卡加载了它；需要时另查具体进程或工具 session。
- Vivado 报告带来源路径、文件时间及报告自身 Design State/Date；不同构建的报告不能拼成同一次通过。默认不推断产物和报告来自相同源码。
- 时序数字通过只证明报告里的 setup/hold/pulse-width；报告中未约束路径或 CDC/bus-skew 必须另看，摘要不是完整时序签核。
- HLS clock/资源是估计，post-route 才是实际实现；BRAM18K 与 Tile 不混用。流水函数的 Interval 不等于整网吞吐。
- 性能工具读取本项目已有 comparison JSON：`baseline_forward_us`、`candidate_forward_us`、`layers`，每层含 `layer/baseline_us/candidate_us`。没有数据不补造；`golden_verified` 必须为 true 才标记性能可讨论，但工具并不重新验证该标志。
- 张量校验要求同类型、同长度和已去除 padding；只比较当前输入，不能替代边界/稳定性测试。

## 本机工程提示

这是可更新的定位提示，不是通用板卡参数：开发仓库 `C:/00_workplace/fpga/cnn_accelerator`，不是原参考资料目录。正式入口 `vitis_live/run_live.tcl`；正式实现报告在 `hardware/camera/build/`，文件名为 `timing.rpt`、`utilization.rpt`、`bus_skew.rpt`。源项目池化性能对照在 `temporary/pool_burst_test/build/comparison.json`。

先用 `status` 确认当前事实，不把提示中的基线数字当最新状态。要展开 HLS 时只选 top 和当前瓶颈的 pipeline XML，不加载所有接口展开内容。

## 上下文卫生

把原始数据留在文件中，回复仅保留：来源/版本、关键指标、异常、下一项验证。只在异常无法从摘要定位时展开对应范围；不要把长日志粘贴进进度消息。验证失败、构建完成、上板通过分别报告，不能互相代替。

这份技能负责快速查事实，优化方法和竞赛材料不默认注入。需要时才读取项目中的工作流包。不会自动提交 Git、发布、重新安装其他技能或改变主机配置。

## 自检与维护

`python scripts/test_inspect.py` 运行隔离测试，不访问板卡。修改解析器后执行自检，并用当前实际报告验证；不支持的格式报错或 unknown，按任务增加实际需要的字段。不要为了设想的未来兼容扩展 schema。
