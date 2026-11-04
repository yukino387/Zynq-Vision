# 模型交付验收标准（Zynq-7020 · INT8 W8A8 · 固定计算图）

- 版本：v1.0
- 日期：2026-10-17
- 目标固件接口：CNC2-SD-25
- 适用链路：OV5640 → PL 采集 → DDR → PS 预处理 → PL 卷积 → PS UDP → 上位机

> **当前牛奶包判定：不通过。**
> 按包内参数直接转换上板会得到错误数值；需要集成方自行重定标、重算下游 bias 和输出尺度后才能运行。这部分适配应由交付方完成并提供验证证据。

---

## 1. 交付包必须包含的物项

| 文件 / 目录 | 内容 | 验收要求 |
|---|---|---|
| `README.md` | 目标硬件、量化方案、预处理、判定规则 | 写明适配的固件接口版本；不得引用已废弃的 Q6.9/int16 口径 |
| `quantization.json` | 逐层 ABI：shape、dtype、input/output scale、weight scale、multiplier/shift、negative 参数 | 唯一权威；与权重/bias 文件逐项一致 |
| `weights/*.weight_i8.bin` | 逐层 int8 权重，`[co][ci][k][k]` | 文件名与层名一一对应；字节数 = co×ci×k×k |
| `weights/*.bias_i32.bin` | 逐通道 int32 bias，小端 | 字节数 = co×4；量化尺度 = input_scale×weight_scale |
| `concat_contract.json` | 每个 concat 的分支角色与目标尺度 | **强制新增**：见 P0-04 |
| `golden/` | 至少两组输入 int8 与 out0/out1 int8 | 一组有检出、一组无检出；输入必须由板端同一套预处理产生 |
| `accuracy.json` | 留出集逐图分数、混淆矩阵、界距 | 留出集不参与训练和校准 |
| `delivery_manifest.json` | 文件清单 + SHA256 + 字节数 | 与实际文件一致 |
| `board_model/` | `weights.bin`、`metadata.bin`、`model.bin` | 板端布局产物；或提供可复现的转换脚本与整数参考 |
| `verify_golden.py` | 软件自检 | 输出与 golden 逐字节一致，不得只报「通过」 |

---

## 2. 板端运行契约

### 2.1 固定计算图

| 项 | 数值 | 说明 |
|---|---|---|
| 命令数 | 33 | 21 卷积、8 重定标（kernel=5）、3 池化（kernel=2）、1 上采样（kernel=0） |
| 层顺序 | BasicConv1 → BasicConv2 → RB1–RB3 → BasicConv3 → conv_forP5 → headP5 → out0 / upsample → headP4 → out1 | 必须与 `camera/training/graph.json` 完全一致 |
| 输入 | 1×224×224 int8，CHW | input_scale = 1/127，zero point = 0 |
| 输出 | out0 33×7×7；out1 33×14×14 | 通道顺序 anchor×11 + channel |
| 特征内存 | `plane = size × (size×8//7)` | 行对齐 8/16/32/64/128/256 字节 |
| 权重包大小 | 6,350,208 B | `[ci/8][co/48]` 分块转置打包 |
| metadata | 16,506 × int32 | 前 330 字为命令表 |

### 2.2 量化 ABI

- 权重 int8、激活 int8、bias int32；INT32 完整累加，不允许 16 位截断。
- 逐输出通道重定标：`out = (|acc × multiplier| + 2^(shift−1)) >> shift`，符号跟随 acc，结果夹到 ±127。
- `multiplier ∈ (0, 2^31)`；`shift ∈ [1, 62]`；负半轴 multiplier = 正半轴 × 0.1。
- bias 量化尺度必须严格等于 `input_scale × weight_scale[c]`；改输出尺度时 bias 不变，改输入尺度时必须同步重算 bias。
- 累加上界 `Σ|w|×127 + |bias| < 2^31`，交付方需逐层给出 `accumulator_abs_bound`。

### 2.3 包格式

| 偏移 | 字段 | 值 / 长度 |
|---|---|---|
| 0x00 | magic | 0x314E4E43 |
| 0x04 | format | 1 |
| 0x08 / 0x0C | weight_size / metadata_size | 6350208 / 66024 |
| 0x10 / 0x14 | generation / committed | 上传时 0 / 0 |
| 0x18 | version | ASCII 1–63 字节，不足补零 |
| 0x58 | payload SHA256 | 32 字节 |
| 0x78 | header CRC32 | 覆盖前 120 字节 |
| 0x80 | weights + metadata | 总包长 6,416,360 B |

---

## 3. 强制验收项

| 编号 | 要求 | 判定方式 | 级别 |
|---|---|---|---|
| P0-01 | 拓扑与每层 `(ci, co, k, stride, size, act)` 与固定图完全一致；权重形状逐一匹配 | 脚本比对，0 差异 | P0 |
| P0-02 | 输入 1×224×224 int8、CHW、zero point 0、input_scale = 1/127 | 读取 quantization.json | P0 |
| P0-03 | 预处理与板端一致（416×416 RGB565 → 灰度 → 224 → int8）；golden 必须由板端管线产生 | 逐像素差异为 0 | P0 |
| P0-04 | **Concat 尺度契约**：写明每个 concat 的目标尺度与分支角色；原地分支输出尺度必须等于目标尺度，否则交付尺度调整表（含下游 bias/乘移重算） | `concat_contract.json` + 板端整数参考 | P0 |
| P0-05 | 输出尺度与上位机一致：out0 = 0.11581249687615341，out1 = 0.15977688286248154 | 与 Postprocess 常量比对 | P0 |
| P0-06 | 板端布局产物可复现；整数参考与 golden 逐字节一致 | 哈希一致；mismatch = 0 | P0 |
| P0-07 | 包完整性：6,416,360 B、header、CRC32、payload SHA256 正确 | 板端 op3 校验 | P0 |
| P0-08 | 平台清单符合 manifestSchema；weights.sha256 为整个 model.bin 的 SHA256 | 服务端导入 | P0 |
| P1-01 | 留出集 ≥18 张，阈值 0.5 下召回/误报、最小次品分、最大好品分、界距（建议 ≥0.3） | accuracy.json | P1 |
| P1-02 | 板端自检通过；≤60 ms/帧；连续 10 分钟无 error | 状态包统计 | P1 |
| P1-03 | 6 个类别槽位的训练情况、二值判定与显示映射写明 | README | P1 |
| P2-01 | 锚框与上位机一致，或随包提供替换方式 | 逐值比对 | P2 |

---

## 4. 交付目录示例

```
milk_int8_w8a8_20261017/
├── README.md
├── delivery_manifest.json
├── quantization.json
├── concat_contract.json
├── accuracy.json
├── weights/
│   ├── BasicConv1.weight_i8.bin
│   ├── BasicConv1.bias_i32.bin
│   └── ...
├── golden/
│   ├── input_quantized.bin
│   ├── out0_quantized.bin
│   └── out1_quantized.bin
├── board_model/
│   ├── weights.bin
│   ├── metadata.bin
│   └── model.bin
└── tools/
    ├── pack_board_model.py
    └── verify_board_model.py
```

---

## 5. 验收流程

1. **包完整性**：文件、SHA256、字节数、版本号格式、逐层文件齐全。通过标准：全部存在且一致。
2. **结构与 ABI**：33 条命令、21 层形状、multiplier/shift 范围、bias 缩放关系、累加上界、concat 契约。通过标准：0 差异，8 个重定标点全覆盖。
3. **板端布局转换**：生成 weights.bin/metadata.bin，核对哈希，确认命令表未改。通过标准：哈希一致，前 330 字与固件模板逐字相同。
4. **整数参考对拍**：按板端内存布局跑 golden 输入，与 out0/out1 逐字节比较。通过标准：mismatch = 0。
5. **打包上板**：生成 model.bin，UDP 安装，自检通过后提交槽位。通过标准：版本身份一致、自检通过、槽位 committed。
6. **板端实测**：同一张 golden 实物图复现，记录分数、框、FPS、10 分钟错误。通过标准：分数偏差 ≤0.02，无饱和/超时/丢帧。

---

## 6. 当前牛奶包不符合项

| 编号 | 不符合项 | 现状 | 影响 | 需补内容 |
|---|---|---|---|---|
| C1 | P0-04 concat 原地分支尺度不满足 | RB1.inner_cat：conv2 0.148659 ≠ 0.161723；RB2.inner_cat：0.104392 ≠ 0.108808；RB2.join：0.097260 ≠ 0.117833 | 直接上板输出最大偏差约 ±13 LSB | 统一隐层尺度；或交付调整表与调整后产物 |
| C2 | P0-05 输出尺度不一致 | out0 0.121649 vs 0.115812；out1 0.131642 vs 0.159777 | 分数偏低约 5% / 17%，out1 框尺寸偏差约 21% | 对齐上位机常量，或同时交付上位机改动 |
| C3 | P0-03 预处理不一致 | 包要求中心裁方 + Pillow bicubic；板端为 416→224 固定系数 | golden 不代表板端输入，现场精度无证据 | 按板端预处理生成 golden 并复测 |
| C4 | 目标硬件口径错误 | README 面向 Q6.9/int16，未声明 CNC2-SD-25 / W8A8 | 交付说明不可作为依据 | 按当前固件重写 |
| C5 | P0-06 缺板端产物与参考实现 | 只有逐层权重；无 weights.bin/metadata.bin、无整数参考 | 板端正确性无法在交付侧证明 | 附转换脚本、产物与对拍结果 |
| C6 | P0-08 平台清单不符合 schema | 旧 source-manifest 字段不匹配；sha256 口径错误 | 无法通过平台导入 | 重新生成清单 |
| C7 | P1-03 类别语义未声明 | 仅 class 0 训练，其余占位；上位机显示 6 类钢名称 | 现场无法解释结果 | 明确二值判定与展示映射 |
| C8 | P1-02 无 FPGA 实测 | 包自述未在 FPGA 上执行 | 自检、时延、长期稳定性无证据 | 补板端自检与 10 分钟记录 |

**已通过的部分**：拓扑与 21 层形状完全匹配；权重 dtype/形状正确；锚框与上位机 `Postprocess.cs` 逐值一致；软件逻辑参考（无内存布局）与包内 golden 逐字节一致。

**集成方临时适配（不应由集成方承担）**：提高 RB1.conv2、RB2.conv2、RB2.conv1 输出尺度到 concat 目标；重算 RB1.conv3、RB2.conv2、RB2.conv3 的 bias 与乘移；out0/out1 输出尺度对齐上位机。适配后分数最大差 0.0023，框差 1–4 px。

---

## 7. 判定规则

- **通过**：P0 全部满足，P1 无未整改项。可上板、换型、现场演示。
- **有条件通过**：P0 全部满足，P1 有明确整改日期。仅限实验室验证。
- **不通过**：任一 P0 不满足，或整数参考与 golden 非逐字节一致。退回交付方。

---

## 附录：metadata 逐层参数布局

每条命令 10 个 int32：`[输入偏移, 输出偏移, 权重偏移, 参数偏移, ch_in, ch_out, fsize, stride, kernel, act]`。

| kernel | 含义 | 参数区 |
|---|---|---|
| 1 / 3 | 卷积 | bias[co] · 正 multiplier[co] · 正 shift[co] · 负 multiplier[co] · 负 shift[co] |
| 5 | concat 前重定标 | multiplier · shift |
| 2 | 2×2 maxpool | 无 |
| 0 | 2× 最近邻上采样 | 无 |

重定标：四舍五入远离零，夹到 ±127；concat 目标尺度取两分支较大者。

---

本标准以当前仓库的 `camera/training/graph.json`、`camera/int8/model.h`、`apps/server/src/models/zynq-profile.ts`、`camera/winui/Postprocess.cs` 为准；固件接口变更时同步升版。
