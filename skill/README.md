# FPGA 工程协作技能包

本目录按 AMD 2026 自主选题赛道 3.3.5.2 整理，供陌生队伍复用工作流、模板、校验工具和失败经验。可整目录复制，不需安装 Codex。Python 工具只用标准库，建议 Python 3.10+；工作流也可直接阅读或把 prompt.md 交给其他助手。

## 快速开始

在包含 skill/ 的目录执行，无需原作者电脑或板卡：

```text
python skill/arm-pl-benchmark/scripts/summarize.py --csv skill/evidence/raw_trials.csv --phase main --baseline arm_novec --candidate pl
python skill/fpga-accelerator-workflow/scripts/verify_tensor.py --help
python skill/fpga-engineering-tools/scripts/inspect.py --help
```

性能示例应读出主阶段 ARM 36、PL 612 次，等权约 212.30 倍、合并约 212.29 倍。这是历史固定输入 ARM 标量基线的离线复算，不是当前板测或端到端 FPS。

## 每项范围、方法、效果与失效条件

| 技能 | 适用范围和使用方法 | 已验证效果及失效条件 |
|---|---|---|
| [arm-pl-benchmark](arm-pl-benchmark/SKILL.md) | CPU/加速器对照；填 plan.md，用 prompt.md 和 summarize.py 处理同 schema CSV | 附真实 CSV 实际离线复算；分开估计量与微内核外推。计时边界、任务或输出不一致时不能比较 |
| [zynq-linux-deploy](zynq-linux-deploy/SKILL.md) | Linux 终端更新；填 deployment.md，按 prompt.md 分 RAM、安装、启动验证 | 从按钮消失、异步列表和页面状态提炼；附历史部署结果及真实交互。冷启动未验证，I/O 异常停止写盘，设备接口必须适配 |
| [int8-model-integration](int8-model-integration/SKILL.md) | 固定图模型换型；填 contract.md，核查预处理/尺度/布局，再整数对拍 | 旧验收记录揭示 concat 与下游 bias 问题；本次测试比较器错误检出，未重验旧模型。缺尺度/布局契约或独立参考不能通过 |
| [fpga-architecture-diagrams](fpga-architecture-diagrams/SKILL.md) | 工程架构图；填 inventory.md，用 prompt.md 组织图表及覆盖 | 附旧工程覆盖结果，本次未重绘。版本混用、未知黑盒、未定义覆盖集合时不能称完整 |
| [fpga-accelerator-workflow](fpga-accelerator-workflow/SKILL.md)（既有） | 算子实现与优化；按 references/workflow.md，运行 verify_tensor.py | 历史优化及失败候选见 references/evidence.md、pitfalls.md；部分原始证据未随包交付，不据此独立证明旧性能 |
| [fpga-engineering-tools](fpga-engineering-tools/SKILL.md)（既有） | 只读 Git/报告/日志摘要；显式传路径，用 test_inspect.py 自检 | 解析不到为 unknown；摘要不代替时序签核，不证明板端加载相同产物 |

新增四项各自的 case.md 详细记录失败或观察、方法、效果与未验证边界；prompt.md 和记录模板可直接复制。既有两项保持原内容，其中本机路径只是案例线索，不是工具运行前提。整目录复用保留同级目录；单独复制 INT8 项时应携带它依赖的整数比较脚本。

## 提炼与验证证据

[来源清单](evidence/sources.json) 记录当前读取的源路径、SHA256、复制或摘录方式。哈希证明本次文件身份，不证明历史文件从未改动。工作流不靠缺失历史目录执行。

[真实交互摘录](evidence/demo_collaboration.json) 保留一轮按钮故障的用户提示和助手回答，可见排查与修正。它不是完整协作导出，不含工具日志；助手自述不当作独立验证。其他案例有文档/机器记录，但本包尚未导出对应完整原始对话，摘要不冒充逐字聊天。

[validation.json](evidence/validation.json) 在实际运行后生成，覆盖真实 CSV 复算、整数比较器边界、既有报告工具自检和脱离仓库副本运行。它不证明板卡正确、SD 稳定或陌生队伍已实测。

## 提交边界

本包对应指南要求的适用场景、使用方法、失效条件、已验证效果和失败/观察来源。技能可以是提示词工作流、案例模板、校验脚本和踩坑清单，不强制全部为自动化程序。文件和目录采用英文，保留明确要求的 README.md 和智能体入口 SKILL.md。

未实现或验证通用 PYNQ Overlay/DMA，不据此申报额外加分；未做跨板部署、第二工程制图或陌生队伍实测，不承诺同样收益。设计报告与完整交互记录、工程构建/板测/资源时序仍需在完整作品中提供，本包不能代替工程交付。

没有调整原工程布局、操作板卡或公开发布，也没有代选全工程和第三方材料的许可证。公开再分发前仍需核实代码、权重与数据各自授权。
