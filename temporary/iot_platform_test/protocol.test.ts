import { test } from "node:test";
import assert from "node:assert/strict";
import {
  FrameAssembler,
  WIRE,
  commandPacket,
  readStatus,
  decodeRgb565,
  detect,
} from "../../packages/device-protocol/src/index.js";
import {
  connectionState,
  syncState,
  compatibility,
} from "../../packages/shared/src/index.js";
import { SimulatorTransport } from "../../apps/server/src/devices/simulator.js";
import {
  simulatorManifest,
  simulatedWeights,
} from "../../apps/server/src/models/profile.js";
import { modelInput } from "../../apps/server/src/assets/preprocess.js";
function packets(frame: number, kind: number) {
  const data = Buffer.alloc(WIRE.sizes[kind]!, kind === 2 ? 128 : 0),
    result: Buffer[] = [];
  for (let offset = 0; offset < data.length; offset += 1400) {
    const header = Buffer.alloc(20);
    [WIRE.frameMagic, frame, kind, data.length, offset].forEach((v, i) =>
      header.writeUInt32LE(v, i * 4),
    );
    result.push(Buffer.concat([header, data.subarray(offset, offset + 1400)]));
  }
  return result;
}
test("UDP parser reassembles out-of-order and duplicate fragments, rejects malformed sizes", () => {
  const assembler = new FrameAssembler();
  const chunks = [
    ...packets(3, 2),
    ...packets(3, 1),
    ...packets(3, 0),
  ].reverse();
  let result: ReturnType<FrameAssembler["push"]> = null;
  for (const packet of chunks) {
    result = assembler.push(packet) ?? result;
    assembler.push(packet);
  }
  assert.equal(result?.frameId, 3);
  assert.equal(result?.raw.length, 346112);
  assert.equal(result?.out1?.length, 6468);
  assert.equal(assembler.push(chunks[0]!), null);
  const malformed = Buffer.from(chunks[0]!);
  malformed.writeUInt32LE(0xffffffff, 12);
  assert.equal(assembler.push(malformed), null);
  assert.equal(assembler.rejected, 1);
});
test("incomplete and expired streams never produce a frame; preview-only supports frame counter wrap", () => {
  const a = new FrameAssembler();
  const chunks = packets(0xffffffff, 2);
  for (const packet of chunks.slice(0, -1))
    assert.equal(a.push(packet, true, 0), null);
  assert.equal(a.push(chunks.at(-1)!, true, 3000), null);
  let result = null;
  for (const packet of packets(0, 2))
    result = a.push(packet, true, 4000) ?? result;
  assert.equal(result?.frameId, 0);
});
test("status layout is 48 bytes LE and signed brightness; commands match firmware CNC1", () => {
  const command = commandPacket(5, 4, -3);
  assert.equal(command.length, 16);
  assert.equal(command.readUInt32LE(0), 0x31434e43);
  assert.equal(command.readInt32LE(12), -3);
  const b = Buffer.alloc(48);
  b.writeUInt32LE(WIRE.statusMagic);
  b.writeUInt32LE(WIRE.device, 8);
  b.writeInt32LE(-4, 44);
  assert.equal(readStatus(b)?.brightness, -4);
  assert.equal(readStatus(b.subarray(1)), null);
});
test("RGB565 decode and source integer preprocessing preserve black and white endpoints", () => {
  const black = Buffer.alloc(346112),
    white = Buffer.alloc(346112, 255);
  assert.deepEqual(
    decodeRgb565(white).subarray(0, 3),
    Buffer.from([255, 255, 255]),
  );
  assert.ok(modelInput(black).every((v) => v === 0));
  assert.ok(modelInput(white).every((v) => v === 127));
});
test("YOLO decode uses source scales, six classes and channel-major tensors", () => {
  const out0 = Buffer.alloc(1617, 128),
    out1 = Buffer.alloc(6468, 128);
  const cell = 20;
  for (const [channel, value] of [
    [0, 0],
    [1, 0],
    [2, 0],
    [3, 0],
    [4, 80],
    [10, 80],
  ])
    out0.writeInt8(value!, channel! * 49 + cell);
  const boxes = detect(out0, out1);
  assert.equal(boxes.length, 1);
  assert.equal(boxes[0]?.classId, 5);
  assert.equal(boxes[0]?.label, "划痕");
  assert.ok(boxes[0]!.confidence > 0.99);
  assert.ok(boxes[0]!.x2 <= 416);
});
test("offline does not imply hardware fault; unknown reported values never become synced", () => {
  assert.equal(connectionState(null, 40000, 10000, 30000), "OFFLINE");
  assert.equal(connectionState(0, 11000, 10000, 30000), "STALE");
  assert.equal(syncState({ modelVersion: "V5" }, {}), "UNKNOWN");
  assert.equal(
    syncState({ modelVersion: "V5" }, { modelVersion: "V4" }),
    "DESYNCED",
  );
  assert.equal(
    syncState({ modelVersion: "V5" }, { modelVersion: "V5" }),
    "SYNCED",
  );
  const weights = simulatedWeights("x"),
    manifest = simulatorManifest(weights);
  assert.deepEqual(compatibility(manifest, { ...manifest, classCount: 7 }), [
    "classCount",
  ]);
});
test("SimulatorTransport confirms deployment receipts and retains previous version on checksum failure", async () => {
  const t = new SimulatorTransport();
  try {
    await t.connect();
    const weights = simulatedWeights("SIM-V2"),
      manifest = simulatorManifest(weights),
      stages: string[] = [];
    const receipt = await t.deployModel(
      "SIM-V2",
      manifest,
      weights,
      async (s) => {
        stages.push(s);
      },
    );
    assert.equal(receipt.active, true);
    assert.equal(receipt.simulated, true);
    assert.deepEqual(stages, [
      "DOWNLOADING",
      "VERIFYING",
      "VERIFIED",
      "ACTIVATING",
      "SELF_TEST",
    ]);
    await t.sendCommand("FAULT", "CHECKSUM_ERROR");
    await assert.rejects(() =>
      t.deployModel("SIM-V3", manifest, weights, async () => {}),
    );
    assert.equal(t.getCurrentModel(), "SIM-V2");
    await t.sendCommand("FAULT", "NETWORK_LOST");
    await assert.rejects(() => t.captureOnce());
  } finally {
    await t.disconnect();
  }
});
