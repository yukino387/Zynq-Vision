# FPGA 加速器工作流技能包

## 精简诊断工具

`fpga-engineering-tools/` 是供智能体按需调用的只读工具包：工程状态、构建报告、性能对比与整数校验。默认返回有来源的短 JSON，不加载完整日志，不启动构建或控制板卡。该包已按用户授权安装在本机；原 `fpga-accelerator-workflow/` 保持项目交付副本，没有重新安装。使用方法见工具包 `SKILL.md`，`python scripts/test_inspect.py` 可执行隔离自检。

提炼自 CNN 加速器实现、摄像头接入、INT8 灰度适配和板级 profiling。交付可复用工作流、校验工具和经验边界，不含模型、bitstream 或固定板卡工程。

## 内容与范围

以下路径均相对 `fpga-accelerator-workflow/`：

| 文件 | 场景与使用方法 | 验证效果与边界 |
|---|---|---|
| `SKILL.md` | 交给智能体完成 HLS/RTL 实现与优化 | 源项目采用逐级验证和基线对照；陌生项目需建自己的基线 |
| `references/workflow.md` | 按阶段执行适配、量化适配、诊断、发布 | 方法不绑定 YOLO 或 7020，不提供通用板卡地址 |
| `scripts/verify_tensor.py` | 运行 `--help`，精确比对整数文件 | 相同输出、signed 范围、单点错误、长度错误经过隔离测试；不处理 padding/浮点容差 |
| `references/pitfalls.md` | 按现象排查 | 写明来源、失效条件和未验证推断；不能替代设备文档 |
| `references/evidence.md` | 查经验提炼来源 | 区分已验证优化和失败候选，提供原始证据相对路径 |
| `references/amd-submission.md` | 核对竞赛交付 | 依据所给指南，不代表后续公告 |

## 使用

复制 `fpga-accelerator-workflow/` 到 `~/.codex/skills/`，新会话使用 `$fpga-accelerator-workflow`。没有 Codex 时也能阅读工作流并运行 Python 标准库脚本，不依赖本队模型或 AMD 工具。

起始请求模板：

> 使用该技能分析我的 FPGA 加速器。确认仓库、接口、可恢复基线与测量条件；只在允许范围内修改一个瓶颈。以整数参考、最终实现报告和上板实测判断候选，不正确就保留基线。列出修改文件和证据。

## 来源与失效条件

来源、观察和已验证效果见 `references/evidence.md`，触发条件与排查见 `references/pitfalls.md`。缺失权重/黄金参考、布局或量化定义时不能宣布功能通过；模型/时钟/软件/通信条件不同的结果不能直接归因于某项优化。

本包不是已验证通用 PYNQ 实现，不宣称 PYNQ 加分资格。过程摘要不代替原始聊天导出；参赛仍需原始提示词、模型回答、自我纠错及完整工程证据。本次只新增技能包，没有自动发布开源、选择全工程许可证或整理原仓库。
