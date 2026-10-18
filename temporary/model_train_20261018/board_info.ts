import { ZynqUdpTransport } from "../../apps/server/src/devices/zynq.js";

async function main() {
const t = new ZynqUdpTransport("169.254.140.110", 5001, 5003);
try {
  await t.connect();
  const status = t.getStatus();
  console.log(JSON.stringify({
    runtimeState: status.runtimeState,
    currentModel: t.getCurrentModel(),
    reported: status.reportedState,
    capabilities: t.capabilities,
    telemetry: status.telemetry && {
      frame: status.telemetry.frameId,
      fps: status.telemetry.fps,
      inferenceUs: status.telemetry.inferenceUs,
      errorCode: status.telemetry.errorCode,
    },
  }, null, 2));
} finally {
  await t.disconnect();
}
}
main().catch((error) => { console.error(error); process.exit(1); });
