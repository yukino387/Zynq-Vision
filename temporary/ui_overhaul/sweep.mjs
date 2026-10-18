// style.css 字面量清扫：把硬编码颜色与圆角换成令牌。
// 有序替换——上下文相关的用整块匹配，其余可安全全局替换。
// 每处替换断言必须命中，任何一条没命中就整体不写盘。
import fs from "node:fs";

const FILE = "C:/00_workplace/fpga/cnn_accelerator/apps/web/src/style.css";
const original = fs.readFileSync(FILE, "utf8");
let css = original;

// [说明, 查找, 替换, 期望次数]
const steps = [
  // ── 上下文相关：必须先做，否则会被后面的全局替换吃掉 ──
  ["primary 按钮文字（森林底）", "background: var(--forest);\n  color: #fff;", "background: var(--forest);\n  color: var(--forest-ink);", 1],
  ["primary hover 文字", "  color: #fff;\n}\n.danger {", "  color: var(--forest-ink);\n}\n.danger {", 1],
  ["检测框标签文字（森林底）", ".image-plane text {\n  fill: #fff;", ".image-plane text {\n  fill: var(--forest-ink);", 1],
  ["侧栏底色", "  width: 208px;\n  background: #fff;", "  width: 208px;\n  background: var(--surface-2);", 1],
  ["顶栏底色", "  justify-content: space-between;\n  background: #fff;\n  border-bottom: 1px solid var(--line);\n  font-size: 14px;", "  justify-content: space-between;\n  background: var(--surface-2);\n  border-bottom: 1px solid var(--line);\n  font-size: 14px;", 1],
  ["nav 悬停底", "nav a:hover {\n  background: #f5f7fa;\n}", "nav a:hover {\n  background: var(--surface-3);\n}", 1],
  ["登录页底", "  background: #f5f7fa;\n}\n.login-form {", "  background: var(--paper);\n}\n.login-form {", 1],

  // ── 整块重写：不只是换色，形状也变（ISA-101：选中用边条不用填充）──
  [
    "nav 选中项改为左侧边条",
    "nav a.selected {\n  background: #eaf1ff;\n  color: var(--forest);\n  font-weight: 600;\n}",
    "nav a.selected {\n  background: var(--surface);\n  box-shadow: inset 3px 0 0 var(--forest);\n  color: var(--ink);\n  font-weight: 600;\n}",
    1,
  ],
  [
    "tab 选中项改为下边条",
    ".tabs a.router-link-active {\n  border-bottom: 2px solid var(--forest);\n  color: var(--forest);\n  font-weight: 600;\n}",
    ".tabs a.router-link-active {\n  box-shadow: inset 0 -2px 0 var(--forest);\n  color: var(--ink);\n  font-weight: 600;\n}",
    1,
  ],
  [
    "模拟标记改用 warn 令牌",
    ".tag.simulated {\n  color: #b57600;\n  border-color: #ffe5b5;\n  background: #fff7e8;\n}",
    ".tag.simulated {\n  color: var(--amber);\n  border-color: var(--warn-line);\n  background: var(--warn-bg);\n}",
    1,
  ],
  [
    "错误框改用 crit 令牌",
    "  background: #fff2f0;\n  border: 1px solid #ffccc7;",
    "  background: var(--crit-bg);\n  border: 1px solid var(--crit-line);",
    1,
  ],
  [
    "登录卡去掉阴影",
    "  background: #fff;\n  box-shadow: 0 8px 40px #1d212908;\n}",
    "  background: var(--surface);\n}",
    1,
  ],
  [
    "抽屉阴影令牌化",
    "  box-shadow: -8px 0 32px #00000014;",
    "  box-shadow: var(--shadow-drawer);",
    1,
  ],
  [
    "浮层阴影令牌化",
    "  box-shadow: 0 4px 24px #00000018;",
    "  box-shadow: var(--shadow-toast);",
    1,
  ],

  // ── 全局替换：同一字面量在本文件里只有一个目标 ──
  ["标注框半透明填充", "#165dff12", "color-mix(in srgb, var(--forest) 7%, transparent)", 1],
  ["遮罩", "background: #1d212966;", "background: var(--scrim);", 1],
  ["次级文字", "#4e5969", "var(--ink-2)", 7],
  ["三级文字", "#86909c", "var(--muted)", 3],
  ["正文色", "#1d2129", "var(--ink)", 1],
  ["强调色", "#165dff", "var(--forest)", 2],
  ["强调悬停", "#4080ff", "var(--forest-hover)", 2],
  ["输入框描边", "#dcdfe6", "var(--line-strong)", 1],
  ["输入框悬停描边", "#a8b2c1", "var(--line-strong)", 1],
  ["按钮悬停描边", "#b7c1d1", "var(--line-strong)", 1],
  ["浅隔线", "#f0f1f4", "var(--line)", 4],
  ["更浅隔线", "#e5e6eb", "var(--line)", 1],
  ["次级面", "#f7f8fa", "var(--surface-2)", 4],
  ["行悬停", "#f9fbff", "var(--surface-2)", 1],
  ["图面与进度槽", "#eef0f3", "var(--surface-3)", 2],
  ["剩余按钮与面板底色", "#fff", "var(--surface)", 6],
  ["圆角统一", /border-radius:\s*(?:12px|10px|8px|6px|4px|2px|50%)/g, "border-radius: var(--radius)", 0],
];

const failures = [];
for (const [label, find, replace, expected] of steps) {
  const before = css;
  const hits = typeof find === "string" ? before.split(find).length - 1 : (before.match(find) ?? []).length;
  if (hits === 0) {
    failures.push(`${label}: 未命中`);
    continue;
  }
  if (expected && hits !== expected) {
    failures.push(`${label}: 命中 ${hits} 次，期望 ${expected} 次`);
    continue;
  }
  css = typeof find === "string" ? before.split(find).join(replace) : before.replace(find, replace);
  console.log(`✓ ${label}  ×${hits}`);
}

// 圆角里 50% 是圆形（连接点），不是卡片圆角，单独保留
const roundCount = (original.match(/border-radius:\s*(?:12px|10px|8px|6px|4px|2px)/g) ?? []).length;

if (failures.length) {
  console.error("\n未写盘，以下替换有问题：");
  for (const f of failures) console.error("  ✗ " + f);
  process.exit(1);
}

fs.writeFileSync(FILE, css);
const left = (css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).filter(
  (h) => !css.includes(`color-mix(in srgb, ${h}`) && !css.includes(`color-mix(in srgb, #`),
);
console.log(`\n圆角统一 ×${roundCount}`);
console.log(`写盘完成。剩余 hex 字面量 ${left.length} 处: ${[...new Set(left)].join(" ") || "（无）"}`);
