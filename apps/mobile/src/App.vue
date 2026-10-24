<script setup lang="ts">
import { watch } from "vue";
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
import { session } from "./state";
import { syncQueue } from "./queue";
import { startLive, stopLive, live } from "./live";
let foreground = true;
onLaunch(() => {
  uni.getNetworkType({
    success: (state) => {
      session.online = state.networkType !== "none";
      if (!session.online) stopLive();
    },
  });
  uni.onNetworkStatusChange((state) => {
    session.online = state.isConnected;
    stopLive();
    if (state.isConnected && foreground) {
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
    if (token) {
      if (foreground) startLive();
    }
    else {
      stopLive();
      live.devices = [];
      live.frame = null;
      live.frames = [];
      live.telemetry = null;
      live.fps = 0;
      live.lastFrameAt = 0;
    }
  },
);
onShow(() => {
  foreground = true;
  if (session.token) {
    startLive();
    void syncQueue();
  }
});
onHide(() => {
  foreground = false;
  stopLive();
});
</script>
<style>
page {
  --ink: #17343e;
  --muted: #637d87;
  --brand: #087f82;
  --line: #dce6e9;
  --surface: #ffffff;
  background: #f3f6f7;
  color: #17343e;
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  font-size: 14px;
  line-height: 1.6;
}
view,
text,
button,
input,
textarea {
  box-sizing: border-box;
}
button {
  margin: 0;
  padding: 13px 18px;
  min-height: 48px;
  border-radius: 14px;
  background: #e8f0f2;
  color: #365661;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
}
button::after {
  border: 0;
}
button:active:not([disabled]) {
  opacity: 0.8;
  transform: translateY(1px);
}
button[disabled] {
  opacity: 0.48;
}
.primary {
  background: #087f82;
  color: white;
  box-shadow: 0 5px 14px #087f8218;
}
.primary:active:not([disabled]) {
  background: #076b6e;
}
.primary[disabled] {
  box-shadow: none;
}
.page {
  padding: 24px 20px calc(32px + env(safe-area-inset-bottom));
}
.eyebrow {
  display: block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.5px;
  color: #087f82;
  margin-bottom: 7px;
}
.title {
  display: block;
  font-size: 27px;
  font-weight: 700;
  letter-spacing: -0.7px;
  line-height: 1.35;
  margin-bottom: 10px;
}
.subtitle {
  display: block;
  color: #637d87;
  font-size: 13px;
  line-height: 1.8;
  margin: 0 0 24px;
}
.muted {
  color: #637d87;
}
.mono {
  font-family: "SFMono-Regular", Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
.card {
  padding: 18px;
  border: 1px solid #e4ecef;
  background: white;
  border-radius: 18px;
  margin-bottom: 14px;
  box-shadow: 0 4px 18px #17343e04;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin: 26px 0 14px;
}
.section-head text:first-child {
  font-size: 16px;
  font-weight: 650;
}
.section-head .muted {
  font-size: 13px;
  padding: 8px 0 8px 12px;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.row > text {
  min-width: 0;
  overflow-wrap: anywhere;
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
  color: #637d87;
  font-size: 13px;
  margin-bottom: 8px;
}
.field.row {
  display: flex;
}
.field.row > text {
  margin: 0;
}
input,
textarea {
  border: 1px solid #dce6e9;
  padding: 12px 14px;
  border-radius: 12px;
  background: #f7fafb;
  width: 100%;
  font-size: 14px;
  color: #17343e;
}
input {
  height: 50px;
}
textarea {
  height: 112px;
  line-height: 1.7;
}
.tag {
  display: inline-block;
  padding: 5px 9px;
  border: 1px solid #ead7b5;
  border-radius: 7px;
  background: #fff5e5;
  color: #8c651d;
  font-size: 11px;
}
.status {
  font-size: 12px;
  color: #637d87;
}
.status.ok {
  color: #087f82;
}
.status.info {
  color: #3679aa;
}
.status.warn {
  color: #9a6a1e;
}
.status.crit {
  color: #c74b45;
}
.error {
  display: block;
  color: #ab443f;
  background: #fff0ed;
  border: 1px solid #f1d2cc;
  padding: 13px 15px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.7;
  overflow-wrap: anywhere;
  margin-bottom: 12px;
}
.success-note {
  padding: 13px 15px;
  background: #e7f6f1;
  border: 1px solid #c8e8df;
  color: #087f82;
  font-size: 13px;
  border-radius: 12px;
  margin: 14px 0;
}
.note {
  display: block;
  font-size: 12px;
  color: #637d87;
  line-height: 1.8;
  margin: 12px 0;
}
.empty {
  padding: 36px 20px;
  color: #486571;
  font-size: 14px;
  line-height: 1.8;
  text-align: center;
  background: #ffffff;
  border: 1px dashed #dce6e9;
  border-radius: 18px;
  margin: 14px 0;
}
.empty text {
  display: block;
}
.empty .hint {
  margin-top: 6px;
  color: #7a9098;
  font-size: 12px;
}
.list-item {
  padding: 16px 0;
  border-bottom: 1px solid #edf2f4;
}
.list-item:last-child {
  border: 0;
}
.list-title {
  display: block;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
}
.list-caption {
  display: block;
  color: #637d87;
  font-size: 12px;
  line-height: 1.7;
}
.progress {
  height: 5px;
  background: #e1eded;
  border-radius: 5px;
  margin-top: 14px;
  overflow: hidden;
}
.progress > view {
  height: 100%;
  background: #18a79b;
  border-radius: 5px;
  transition: width 0.2s;
}
.picker {
  padding: 13px;
  border: 1px solid #dce6e9;
  border-radius: 12px;
  background: #f7fafb;
}
.offline-banner {
  padding: 12px 20px;
  background: #fff1da;
  color: #8c651d;
  font-size: 12px;
}
.image {
  width: 100%;
  border-radius: 12px;
  background: #e8f0f2;
}
.stat-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 18px 0;
}
.stat-row > view {
  padding: 14px 0;
}
.stat-row .value {
  display: block;
  font-size: 26px;
  font-weight: 600;
  margin-bottom: 5px;
}
.stat-row .caption {
  font-size: 12px;
  color: #637d87;
}
.review-options {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.review-options > text {
  padding: 10px 14px;
  border: 1px solid #dce6e9;
  border-radius: 12px;
  background: white;
  min-height: 44px;
  font-size: 13px;
}
.review-options > text.selected {
  background: #e5f5f2;
  border-color: #087f82;
  color: #087f82;
  font-weight: 600;
}
.bottom-space {
  height: 24px;
}
</style>
