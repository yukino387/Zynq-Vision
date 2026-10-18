import dgram from "node:dgram";
import { FrameAssembler, WIRE, commandPacket } from "../../packages/device-protocol/src/index.js";

const BOARD = { address: "169.254.140.110", port: 5001 };
const LOCAL = 5003;
const DURATION = 10000;

async function main() {
  const socket = dgram.createSocket("udp4");
  const assembler = new FrameAssembler();
  let packets = 0;
  const ids: number[] = [];
  await new Promise<void>((resolve, reject) => {
    socket.once("error", reject);
    socket.bind(LOCAL, "0.0.0.0", () => { socket.off("error", reject); resolve(); });
  });
  socket.setRecvBufferSize(4 * 1024 * 1024);
  const started = Date.now();
  socket.on("message", (packet) => {
    if (packet.length <= 20 || packet.readUInt32LE(0) !== WIRE.frameMagic) return;
    packets++;
    const frame = assembler.push(packet, false);
    if (frame) ids.push(frame.frameId);
  });
  socket.send(commandPacket(1, 1, 0), BOARD.port, BOARD.address);
  await new Promise((r) => setTimeout(r, DURATION));
  socket.send(Buffer.from([0]), BOARD.port, BOARD.address); // release preview
  await new Promise((r) => setTimeout(r, 200));
  socket.close();
  const seconds = (Date.now() - started) / 1000;
  let missing = 0, maxGap = 0;
  const gaps: number[] = [];
  for (let i = 1; i < ids.length; i++) {
    const gap = ids[i] - ids[i - 1];
    if (gap > 1) { missing += gap - 1; gaps.push(gap); maxGap = Math.max(maxGap, gap); }
  }
  console.log(JSON.stringify({
    seconds: Number(seconds.toFixed(2)),
    packets,
    frames: ids.length,
    fps: Number((ids.length / seconds).toFixed(2)),
    first: ids[0], last: ids.at(-1),
    missingInGaps: missing,
    gapCount: gaps.length,
    gaps: gaps.slice(0, 30),
    maxGap,
    assemblerRejected: assembler.rejected,
  }, null, 2));
}
main().catch((error) => { console.error(error); process.exit(1); });
