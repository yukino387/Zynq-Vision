// 移动端没有令牌层，颜色全是字面量。这里把旧调色板整体映射到新调色板。
// 相机取景页的暗色系（#171c26 一族）刻意保留——取景器本来就该是暗面。
import fs from "node:fs";
import path from "node:path";

const ROOT = "C:/00_workplace/fpga/cnn_accelerator/apps/mobile/src";

// 旧值 -> 新值（新调色板见 packages/design-tokens/tokens.css 的亮色段）
const MAP = [
  ["#165dff", "#1f4d3a"], // 主强调：蓝 -> 深森林绿
  ["#4080ff", "#2a6349"],
  ["#eef3ff", "#e4e2dd"], // 次级面
  ["#86909c", "#7c807c"], // 三级文字
  ["#1d2129", "#151715"], // 正文
  ["#4e5969", "#484c49"], // 次级文字
  ["#f5f7fa", "#f1f0ed"], // 页底
  ["#f7f8fa", "#e4e2dd"],
  ["#eef0f3", "#d6d3cc"],
  ["#e2e6dc", "#d6d3cc"],
  ["#e5e6eb", "#c9c6bf"], // 隔线
  ["#00875a", "#3d6b4b"], // 合格（降饱和）
  ["#b57600", "#8f5f00"], // 待复核
  ["#d6c18f", "#d8bd85"],
  ["#f6efd9", "#f5ead2"],
  ["#f0e3bf", "#f5ead2"],
  ["#79591e", "#8f5f00"],
  ["#d03050", "#a5321a"], // 故障
  ["#f3e7df", "#f3e1da"],
  ["#dfc7b5", "#d4a294"],
  ["#ffffff", "#fbfaf8"], // 面板；在森林绿上作前景也仍然可读
];

const files = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(vue|ts|json)$/.test(e.name)) files.push(p);
  }
})(ROOT);

let touched = 0,
  total = 0;
for (const file of files) {
  const before = fs.readFileSync(file, "utf8");
  let after = before;
  const hits = [];
  for (const [from, to] of MAP) {
    const re = new RegExp(from.replace("#", "#"), "gi");
    const n = (after.match(re) ?? []).length;
    if (!n) continue;
    after = after.replace(re, to);
    hits.push(`${from}->${to} x${n}`);
    total += n;
  }
  if (after !== before) {
    fs.writeFileSync(file, after);
    touched++;
    console.log(`[ok] ${path.relative(ROOT, file)}  ${hits.join("  ")}`);
  }
}
console.log(`\n改动 ${touched} 个文件，替换 ${total} 处。`);
