<script setup lang="ts">
import { watch } from "vue";
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
import { session } from "./state";
import { syncQueue } from "./queue";
import { startLive, stopLive } from "./live";
onLaunch(() => {
  uni.onNetworkStatusChange((state) => {
    session.online = state.isConnected;
    if (state.isConnected) {
      if (session.token) {
        void syncQueue();
        startLive();
      }
    }
  });
  if (session.token) startLive();
});
// 实时画面是登录态的一部分：有 token 就保持一条预览连接，退出即断开。
watch(
  () => session.token,
  (token) => {
    if (token) startLive();
    else stopLive();
  },
);
onShow(() => {
  if (session.token) {
    startLive();
    void syncQueue();
  }
});
onHide(() => stopLive());
</script>
<style>
page {
  background: #f1f0ed;
  color: #151715;
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  font-size: 14px;
}
view,
text,
button,
input,
textarea {
  box-sizing: border-box;
}
button {
  font-size: 14px;
  border-radius: 8px;
  background: #e4e2dd;
  color: #1f4d3a;
  line-height: 1.5;
  padding: 13px 16px;
  margin: 0;
}
/* 触屏没有 hover，按压态是唯一的即时反馈 */
button:active:not([disabled]) {
  background: #d6d3cc;
}
button[disabled] {
  opacity: 0.5;
  color: #7c807c;
}
/* 等待中的按钮：与 Web 端同一套约定，用 .busy 或 aria-busy 标记 */
button.busy,
button[aria-busy="true"] {
  opacity: 0.72;
}
/* 主操作按下时给一点位移，手感上有回应 */
.large-action:active,
.primary:active:not([disabled]) {
  opacity: 0.88;
}
button::after {
  border: 0;
}
.primary {
  background: #1f4d3a;
  color: #fff;
}
.muted {
  color: #7c807c;
}
.mono {
  font-family: Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
.page {
  padding: 24px 20px 32px;
}
.eyebrow {
  font-size: 12px;
  letter-spacing: 0;
  color: #7c807c;
  display: block;
  margin-bottom: 10px;
}
.title {
  font-size: 26px;
  font-weight: 600;
  display: block;
  line-height: 1.3;
  margin-bottom: 10px;
}
.subtitle {
  font-size: 12px;
  color: #7c807c;
  display: block;
  line-height: 1.8;
  margin-bottom: 25px;
}
.card {
  padding: 20px;
  background: #fbfaf8;
  border: 1px solid #c9c6bf;
  border-radius: 8px;
  margin-bottom: 16px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 26px 0 14px;
}
.section-head text:first-child {
  font-size: 17px;
  font-weight: 600;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.field {
  display: block;
  margin: 18px 0;
}
.field > text {
  display: block;
  color: #7c807c;
  font-size: 12px;
  margin-bottom: 8px;
}
input,
textarea {
  border: 1px solid #c9c6bf;
  padding: 12px;
  border-radius: 6px;
  background: #fbfaf8;
  width: 100%;
  font-size: 14px;
}
input {
  height: 45px;
}
textarea {
  height: 100px;
}
.tag {
  display: inline-block;
  padding: 5px 8px;
  border: 1px solid #d8bd85;
  background: #f5ead2;
  border-radius: 4px;
  color: #8f5f00;
  font-family: monospace;
  font-size: 12px;
}
.status {
  font-size: 12px;
  display: inline-block;
  color: #7c807c;
}
/* 与 Web 共用 packages/shared 的 statusTone；移动端此前没有琥珀档，
   待复核会被渲染成普通绿点。 */
.status.ok {
  color: #3d6b4b;
}
.status.info {
  color: #3a5f86;
}
.status.warn {
  color: #8f5f00;
}
.status.crit {
  color: #a5321a;
}
.error {
  color: #a5321a;
  background: #f3e1da;
  border: 1px solid #d4a294;
  padding: 13px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.note {
  font-size: 12px;
  color: #7c807c;
  line-height: 1.8;
  display: block;
  margin: 12px 0;
}
.empty {
  padding: 28px 16px;
  text-align: center;
  color: #484c49;
  font-size: 13.5px;
  line-height: 1.8;
}
.empty text {
  display: block;
}
/* 提示比标题弱一档，但两者都要够对比度：浅底上 #484c49 约 8:1，#7c807c 约 4.4:1 */
.empty .hint {
  margin-top: 6px;
  font-size: 12.5px;
  color: #7c807c;
}
.list-item {
  padding: 16px 0;
  border-bottom: 1px solid #d6d3cc;
}
.list-item:last-child {
  border: 0;
}
.list-title {
  font-size: 14px;
  display: block;
  margin-bottom: 6px;
}
.list-caption {
  font-size: 12px;
  color: #7c807c;
  display: block;
  line-height: 1.7;
}
.progress {
  height: 4px;
  background: #c9c6bf;
  border-radius: 2px;
  margin-top: 14px;
}
.progress > view {
  height: 100%;
  background: #1f4d3a;
}
.large-action {
  padding: 24px;
  background: #1f4d3a;
  color: white;
  border-radius: 10px;
  margin: 20px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.large-action .title {
  font-size: 24px;
  margin-bottom: 7px;
}
.large-action .note {
  color: #e0e9ff;
  margin: 0;
}
.picker {
  padding: 13px;
  background: #fbfaf8;
  border: 1px solid #c9c6bf;
  border-radius: 6px;
}
.offline-banner {
  padding: 12px 20px;
  background: #f5ead2;
  color: #8f5f00;
  font-size: 12px;
}
.image {
  width: 100%;
  border-radius: 8px;
  background: #d6d3cc;
}
.stat-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 18px 0;
}
.stat-row > view {
  padding: 18px 0;
  border-top: 1px solid #c9c6bf;
  border-bottom: 1px solid #c9c6bf;
}
.stat-row .value {
  font-size: 25px;
  display: block;
  margin-bottom: 6px;
}
.stat-row .caption {
  font-size: 12px;
  color: #7c807c;
}
.bottom-space {
  height: 25px;
}
.review-options {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
}
.review-options > text {
  padding: 10px 12px;
  border: 1px solid #c9c6bf;
  border-radius: 6px;
  font-size: 12px;
}
.review-options > text.selected {
  background: #1f4d3a;
  color: white;
}
/* Field instrument surfaces */
page {
  background: #e9e9df;
  color: #283023;
  font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}
button {
  border-radius: 2px;
  background: #dedfd2;
  color: #3d4c31;
  min-height: 44px;
  font-size: 13px;
}
.primary,
.large-action {
  background: #dd5b2a;
  color: #fff8eb;
  border-radius: 2px;
}
.primary:active,
.large-action:active {
  background: #c64b1e;
}
.page {
  padding: 25px 20px 32px;
}
.title {
  font-size: 27px;
  font-weight: 550;
  letter-spacing: -1px;
}
.card {
  border: 0;
  border-top: 1px solid #b7bda9;
  border-bottom: 1px solid #b7bda9;
  border-radius: 0;
  background: #f7f6ee;
  padding: 18px;
  margin-bottom: 12px;
}
input,
textarea,
.picker {
  border-radius: 2px;
  border-color: #b8bfaa;
  background: #f8f7ef;
}
input {
  height: 47px;
}
.tag {
  border-radius: 2px;
  border-color: #c2ab76;
  background: #f5e7c4;
  color: #7a5a1c;
  font-size: 10px;
}
.muted,
.subtitle,
.note,
.list-caption {
  color: #6b775e;
}
.section-head {
  border-top: 2px solid #404c34;
  padding-top: 14px;
  margin-top: 25px;
}
.section-head text:first-child {
  font-size: 13px;
}
.large-action {
  padding: 25px 20px;
  min-height: 130px;
}
.large-action .title {
  font-size: 29px;
}
.large-action .note {
  color: #ffe8d1;
  font-size: 11px;
}
.progress {
  background: #d0d7c0;
  height: 3px;
  border-radius: 0;
}
.progress > view {
  background: #657d43;
}
.list-item {
  border-bottom-color: #cbd1be;
}
.review-options > text {
  border-radius: 2px;
  min-height: 44px;
}
.review-options > text.selected {
  background: #414f33;
}
.offline-banner {
  background: #f0dfb7;
  color: #806022;
  font-size: 11px;
}
.image {
  border-radius: 0;
}
.error {
  border-radius: 0;
  border-color: #d5a28e;
}
</style>
