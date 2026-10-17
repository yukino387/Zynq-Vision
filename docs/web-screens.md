# Web 界面清单

前端信息架构的单一真源是 `apps/web/src/navigation.ts` 的路由表。侧栏（含二级项）、顶栏标题、角色可见性全部从它的 `meta` 派生——不要在视图里另写一份子页列表。

**子页在侧栏，不在页内。** 每个有 `tabs` 的路由，其子项以缩进形式挂在侧栏该组之下；只有当前所在的组展开，否则十九个子项会把侧栏撑爆。父项加粗表示"你在这一组"，子项带森林绿边条表示"就是这里"。页内不再有横向 tab 条。

**读可选参数要用 `||` 而不是 `??`。** `path: "/data/:tab?"` 在未提供参数时，vue-router 给的是**空字符串**；`??` 不为空串回退，会静默落到"没有匹配的子页"，导致顶栏和侧栏高亮同时失灵。视图里的默认值也统一吃 `meta.defaultTab`，不再各写一份字面量。

`meta` 字段：

| 字段 | 含义 |
| --- | --- |
| `title` | 侧栏标签与顶栏标题 |
| `nav` | 是否进侧栏（详情页与兜底路由为 `false`） |
| `order` | 侧栏排序；必须显式给值，路由注册顺序不保证稳定 |
| `roles` | 可见角色；省略表示全部 |
| `discipline` | `hmi` 严格灰度 / `business` 正常色彩层次 |
| `tabs` | **侧栏二级项**，每项可带自己的 `roles` |
| `defaultTab` | 不带 tab 参数时落在哪个子页；顶栏与侧栏高亮都据此判定 |

## 路由

| 路径 | 名称 | 层级 | 角色 | 纪律 |
| --- | --- | --- | --- | --- |
| `/overview` | `overview` | L1 概览 | ADMIN, ENGINEER | hmi |
| `/workbench` | `workbench` | L2 主操作 | 全部 | hmi |
| `/inspections/:id` | `inspection` | L3 详情 | 全部 | hmi |
| `/records/:tab?` | `records` | 记录 | 全部 | business |
| `/data/:tab?` | `data` | 业务 | 按 tab | business |
| `/models/:tab?` | `models` | 业务 | ADMIN, ENGINEER | business |
| `/diagnostics/:tab?` | `diagnostics` | L4 诊断 | 全部（只读） | hmi |
| `/system/:tab?` | `system` | 业务 | ADMIN, ENGINEER | business |
| `/:pathMatch(.*)*` | `notFound` | 兜底 | — | business |

`/` 不渲染组件：守卫按角色重定向到 `landingFor(role)`。守卫生效的前提是 `auth.restore()` 已记忆化（`stores/auth.ts`），否则每次导航都会重新拉一次身份。

## 各屏职责

**产线总览**（`views/Overview.vue`）——管理员与工程师的落地页。首屏回答"现在什么状态、什么在等我、卡在哪一步"。数据来自 `GET /api/overview`（见 `api.md`）加设备 store，不轮询：由 `device.inspection.completed` / `device.status.changed` 等 WS 事件触发刷新。

其中**数据闭环**一条把采样 → 审核 → 数据集 → 训练 → 模型 → 部署 → 检测横向排开，每环给出已完成量与待人工处理量，有积压的一环用琥珀标出并可点进去。这是这一屏存在的主要理由：让下一步该去哪在界面上是自明的，而不是靠记住七个菜单的职责。

对 OPERATOR 该接口的 `pipeline`、`firmwareGaps`、`loop` 均为 `null`（那几环的接口对他是 403），界面上不渲染这些块。

**检测工作台**（`views/Operations.vue`）——操作工的落地页，判定优先。实时画面为主列；右列自上而下是判定带（当前帧有没有检出候选）、检出目标、交叉链接。操作收在标题栏一排：设备、关联任务、连接设备、采样当前帧。最近检测按分诊排序（待处理在前）。采样成功后**不跳转**：新记录落到列表顶部并发一条提示，操作工留在实时画面上。

**设备诊断**（`views/Devices.vue`）——四个 tab：设备、工位、设备事件、实时事件。顶部常显「最近一帧耗时」（采集/预处理/推理/传输/帧周期/帧率/错误码），这些是从工作台搬过来的：操作工不需要看，工程师需要常显。工位留在这里而不是移到系统屏：它是设备相邻的配置。

**单件详情与复核**（`views/InspectionDetail.vue`）——独立路由，可深链、可冷启动直接打开。取数在视图里，渲染复用 `components/InspectionDetail.vue`；该组件保持纯展示，因此仍可作为抽屉内容在别处使用。复核后的 `@saved` 事件触发本页重新取数。

**检测记录**（`views/Records.vue`）——两个 tab：待办（`result=REVIEW`）与全部。列表里的「证据 / 复核」是到详情路由的链接，不是抽屉。

**数据管理**（`views/Data.vue`）——六个 tab：采样任务、样本库、样本审核、标注（ENGINEER）、数据集（ENGINEER）、数据质量（ENGINEER）。数据集刻意留在这一屏而不是并入「训练与发布」：移动它要连带搬走冻结/克隆/导出的逻辑，没有功能收益。

**训练与发布**（`views/Models.vue`）——四个 tab：模型仓库、训练任务、模型评估、部署管理。

**设备诊断**（`views/Devices.vue`）——四个 tab：设备、工位、设备事件、实时事件。工位留在这里而不是移到系统屏：它是设备相邻的配置，跨文件搬运的收益不明确。

**系统管理**（`views/System.vue`）——五个 tab：系统健康、移动端配对、任务队列、用户（ADMIN）、操作审计（ADMIN）。

## 加一屏或加一个 tab

改 `navigation.ts` 一处即可。若新屏属于检测相关，给它 `discipline: "hmi"`；业务屏用 `"business"` 或不写。tab 若要限制角色，加 `roles` 数组，视图里的 `canAccess(t.roles, auth.user?.role)` 会自动过滤。
