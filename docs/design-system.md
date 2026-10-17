# Industrial Editorial / Precision Instrument

共享色彩变量在 `packages/design-tokens/tokens.css`，状态到色调的映射在 `packages/shared/src/status.ts`。Warm White / Light Gray / Graphite / Ink 为基础，**Deep Forest Green 为界面强调**，Amber 表示待复核，Orange Red 表示故障，钢蓝留给处理信息（`--info`）。

## 色彩只承担语义

屏幕以灰度为主，饱和色只留给需要人处理的状态。合格是预期状态，在屏幕上占多数，因此渲染为灰色的安静样式——否则健康产线会是一屏绿墙，把唯一一行异常淹掉。这是 ISA-101 的做法，也是判断改版是否成功的标准：眯眼看屏幕，跳出来的只应该是「待复核」和「不通过」。

| 色调 | 含义 | 令牌 | 典型值 |
| --- | --- | --- | --- |
| `quiet` | 正常，不需要注意力 | `--muted` | PASS, COMPLETED, REVIEWED, SYNCED, UNKNOWN |
| `ok` | 设备肯定地报告为正常 | `--green` / `--ok-bg` | ONLINE, READY, RUNNING, VERIFIED, ACTIVE |
| `info` | 进行中 | `--info` / `--info-bg` | QUEUED, DOWNLOADING, ACTIVATING, SELF_TEST |
| `warn` | 需要人处理 | `--amber` / `--warn-bg` | REVIEW, PENDING, DRAFT, DESYNCED, STALE |
| `crit` | 失败或下线 | `--red` / `--crit-bg` | FAIL, FAILED, FAULT, OFFLINE, ROLLED_BACK |

`--forest` 是**界面强调**，只出现在：选中的导航项、每屏唯一的主按钮、焦点环、检测框描边。它**永远不作状态色**。

`--forest`（亮色 `#1f4d3a`）与 `--info`（`#3a5f86`）**必须是两个能分辨的颜色**：前者是强调，后者是"进行中"状态。历史上两者曾指向同一个值，导致主操作与"进行中"共色、强调层塌陷——改任何一个之前先确认另一个不受影响。

**移动端有一部分颜色无法走变量**：uni-app 在任何 CSS 存在之前就编译 `pages.json`，所以 tabBar 与导航栏底色只能手写；`apps/mobile/src/App.vue` 的全局样式同理。改配色时这些值必须手工同步，`node scripts/check-theme.mjs` 会把它们和令牌逐项比对（不一致时退出码 1）。

强调色的色相是可替换的（本项目在绿与蓝之间摇摆过）。本节的规则约束的是**用在哪**，不是**是什么颜色**，所以换色相不需要改这一节；但换完要保证：`--forest` 与 `--info` 可分辨、`--forest` 上的文字用 `--forest-ink` 而不是写死 `#fff`、暗色主题下的强调色单独给值（不能沿用亮色值）。

`UNKNOWN`（未上报）映射为 `quiet` 而不是 `warn`：`Device.firmwareVersion` 永远为 null，把它标成异常等于给每台设备挂一个永久警告。表中没有的非空值给 `warn`——那是"我们还没有规则"，值得看一眼。

## 分屏色彩纪律

`meta.discipline` 决定一屏受哪套约束：

- **`hmi`**（检测相关：产线总览、检测工作台、单件详情与复核、设备诊断）——严格灰度。`--forest` 只用于选中与主操作；`--ok` 不出现在表体；`--warn`/`--crit` 只出现在要人处理的东西上；无圆角胶囊、无渐变、无阴影；设备 ID、版本、耗时、帧号一律等宽字体加 `tabular-nums`。
- **`business`**（数据管理、训练与发布、系统管理、检测记录）——同一套令牌，但允许正常的色彩层次，链接与进度条可以用 `--forest` 和 `--info`。

## 导航与信息架构

导航**按角色分流**，不是固定的实体菜单。路由表 `apps/web/src/navigation.ts` 是唯一真源：侧栏、顶栏标题、视图内 tab 条、角色可见性全部从它派生。落地页由 `landingFor(role)` 决定——管理员与工程师进「产线总览」，操作工进「检测工作台」。

| 角色 | 侧栏 |
| --- | --- |
| ADMIN | 检测工作台 · 产线总览 · 检测记录 · 数据管理 · 训练与发布 · 设备诊断 · 系统管理 |
| ENGINEER | 同上（系统管理内隐藏用户与操作审计） |
| OPERATOR | 检测工作台 · 检测记录 · 数据管理 · 设备诊断 |

角色同时在前端与 Server 两端校验：前端隐藏入口，Server 的 `@Roles` 才是真正闸门。后端对某角色不可读的数据，接口返回 `null` 而不是 `0`，界面显示为不可用，避免暴露一个点进去就 403 的计数。

## 组件与页面

公共组件：`Status`（带 `chip` 变体）、`AsyncState`、`Drawer`、`ImageViewer`、`AnnotationEditor`、`InspectionDetail`。图像支持缩放/拖动、Fit/1:1、框显示、Preview/重建输入切换、原始资产下载。标注支持画框/移动/调整、类别修改、Delete/Ctrl+S、上一张/下一张及本地草稿。

Web 主要验收尺寸为 1920×1080、1440×900、1280×720，并支持跟随系统 / 浅色 / 深色三态主题（顶栏切换，持久在 `localStorage["vision.theme"]`）。移动端独立 uni-app 四个底部入口：首页、任务、采样、记录。移动采样为相机主界面，板端/手机/同步模式分开，大快门、轻量 IMU 状态、离线队列。

## 空态与诚实标注

空记录、加载、错误、无权限、设备离线、No Capability 都使用明确文字。所有模拟设备/推理/模型/部署明确显示 SIMULATED。**没有测量来源的硬件指标不生成占位百分比**——显示「未上报」。固件确实不提供的能力（如模型上传、双槽回滚）列在「固件当前未提供」里，而不是显示成 0 或 100%。
