import { readFileSync, writeFileSync } from "node:fs";
import { ZynqUdpTransport } from "../../apps/server/src/devices/zynq.js";
import type { CapturedFrame } from "../../apps/server/src/devices/transport.js";

const DIR = "C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018/delivery";
const VERSION = "INT8-EARPHONE-20261018-B";

async function main() {
  const t = new ZynqUdpTransport("169.254.140.110", 5001, 5003);
  const frames: CapturedFrame[] = [];
  t.subscribePreview((type, payload) => {
    if (type === "device.preview.frame") frames.push(payload as CapturedFrame);
  });
  try {
    await t.connect();
    console.log("before:", t.getCurrentModel(), t.getStatus().reportedState.models);
    const manifest = JSON.parse(readFileSync(`${DIR}/manifest.json`, "utf8"));
    const weights = readFileSync(`${DIR}/model.bin`);
    const receipt = await t.deployModel(VERSION, manifest, weights, async (stage) => {
      console.log("stage:", stage, new Date().toISOString());
    });
    console.log("receipt:", JSON.stringify(receipt));
    console.log("after:", t.getCurrentModel(), t.getStatus().reportedState.models);
    frames.length = 0;
    await t.sendCommand("START_INSPECTION");
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 100));
      const fresh = frames.at(-1);
      if (fresh && fresh.modelState.modelVersion === VERSION && fresh.detections) {
        console.log("frame:", JSON.stringify({
          frameId: fresh.frameId,
          modelVersion: fresh.modelState.modelVersion,
          telemetry: fresh.telemetry && {
            inferenceUs: fresh.telemetry.inferenceUs,
            cycleUs: fresh.telemetry.cycleUs,
            errorCode: fresh.telemetry.errorCode,
            brightness: fresh.telemetry.brightness,
          },
          detections: fresh.detections.map((b) => ({
            classId: b.classId, label: b.label, confidence: Number(b.confidence.toFixed(3)),
            x1: Math.round(b.x1), y1: Math.round(b.y1), x2: Math.round(b.x2), y2: Math.round(b.y2),
          })),
        }, null, 2));
        writeFileSync(`${DIR}/board_frame.jpg`, fresh.preview);
        console.log("saved board_frame.jpg");
        return;
      }
    }
    console.log("no fresh frame after model switch");
  } finally {
    await t.disconnect();
  }
}
main().catch((error) => { console.error(error); process.exit(1); });
