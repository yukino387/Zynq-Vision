// 移动端有一部分颜色无法走 CSS 变量：uni-app 在任何 CSS 存在之前就编译 pages.json，
// 所以 tabBar 配色只能手写。这个脚本把它们和设计令牌对齐检查，防止改配色时悄悄失配。
//
// 运行：node scripts/check-theme.mjs
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const read = (p) => fs.readFileSync(path.join(ROOT, p), "utf8");

/** 取 :root 块里的亮色令牌值。 */
function tokens() {
  const css = read("packages/design-tokens/tokens.css");
  const root = css.slice(css.indexOf(":root {"), css.indexOf("@media"));
  const out = {};
  for (const [, name, value] of root.matchAll(/--([\w-]+):\s*([^;]+);/g))
    out[name] = value.trim().toLowerCase();
  return out;
}

const t = tokens();
const pages = JSON.parse(read("apps/mobile/src/pages.json"));
const tab = pages.tabBar ?? {};

const checks = [
  ["pages.json tabBar.selectedColor", tab.selectedColor, t.forest, "--forest"],
  ["pages.json tabBar.color", tab.color, t.muted, "--muted"],
  ["pages.json tabBar.backgroundColor", tab.backgroundColor, t.surface, "--surface"],
  [
    "pages.json globalStyle.navigationBarBackgroundColor",
    pages.globalStyle?.navigationBarBackgroundColor,
    t.surface,
    "--surface",
  ],
];

// 移动端 App.vue 的全局样式也有一批手写值，抽出来一并对齐
const appVue = read("apps/mobile/src/App.vue");
const pageRule = appVue.match(/\npage\s*\{([^}]*)\}/)?.[1] ?? "";
const grab = (block, prop) =>
  block.match(new RegExp(`${prop}:\\s*(#[0-9a-fA-F]{3,8})`))?.[1]?.toLowerCase();
checks.push(
  ["mobile App.vue page background", grab(pageRule, "background"), t.paper, "--paper"],
  ["mobile App.vue page color", grab(pageRule, "color"), t.ink, "--ink"],
);

let failed = 0;
for (const [label, actual, expected, token] of checks) {
  const ok = actual && expected && actual === expected;
  if (!ok) failed++;
  console.log(
    `${ok ? "✓" : "✗"} ${label.padEnd(46)} ${actual ?? "(缺失)"} ${ok ? "=" : "≠"} ${expected ?? "(令牌缺失)"} ${token}`,
  );
}
if (failed) {
  console.error(
    `\n${failed} 处与设计令牌不一致。pages.json 无法用变量，必须手工同步；` +
      `App.vue 的手写值同理（uni-app 的运行时主题不可靠）。`,
  );
  process.exit(1);
}
console.log("\n移动端手写配色与设计令牌一致。");
